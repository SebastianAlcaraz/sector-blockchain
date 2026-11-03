from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from invest.news import NewsItem
from invest.trading.advisor import Advice, Decision, RuleAdvisor
from invest.trading.broker import BrokerError, EToroDemoBroker, PaperBroker, Position
from invest.trading.config import BotConfig
from invest.trading.engine import Engine
from invest.trading.market import snapshot
from invest.trading.risk import RiskContext, check_buy, check_sell, stop_loss_hits
from invest.trading.store import Store


class FixedSource:
    """Precios controlados: una subida suave para AAA y BBB, editable entre llamadas."""

    def __init__(self):
        idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=300)
        self.df = pd.DataFrame({"AAA": np.linspace(50, 100, 300), "BBB": np.linspace(80, 100, 300), "SPY": np.linspace(400, 500, 300)}, index=idx)

    def closes(self, tickers, period="1y"):
        return self.df[[t for t in tickers if t in self.df]]

    def set_last(self, ticker, price):
        self.df.loc[self.df.index[-1], ticker] = price


class FixedAdvisor:
    name = "Fijo"

    def __init__(self, decisions):
        self.decisions = decisions

    def advise(self, snaps, cfg, cash_pct, strategy=None):
        return Advice(list(self.decisions), "Resumen de prueba", self.name)


def make_engine(tmp_path, decisions, **cfg_kw):
    base = dict(modo="simulacion", universo="lista", requiere_aprobacion=True)
    base.update(cfg_kw)
    cfg = BotConfig(lista_activos=["AAA", "BBB"], referencia="SPY", capital_inicial=10_000, diferencial_pct=0, **base)
    return Engine(tmp_path, cfg=cfg, source=FixedSource(), advisor=FixedAdvisor(decisions), news_fn=lambda t: [])


# ------------------------------------------------------------------ riesgo
def ctx(**kw):
    base = dict(equity=10_000, cash=10_000, positions={}, prices={"AAA": 100.0})
    base.update(kw)
    return RiskContext(**base)


def test_buy_is_capped_by_max_trade_and_position():
    cfg = BotConfig(lista_activos=["AAA"])
    v = check_buy(Decision("AAA", "comprar", importe_pct=50, confianza=0.9), ctx(), cfg)
    assert v.ok and v.amount == 500  # 5 % de 10.000
    held = ctx(positions={"AAA": Position(19, 100)})  # ya pesa un 19 %
    v = check_buy(Decision("AAA", "comprar", importe_pct=5, confianza=0.9), held, cfg)
    assert v.ok and v.amount == pytest.approx(100)


def test_buy_rejections():
    cfg = BotConfig(lista_activos=["AAA"])
    good = Decision("AAA", "comprar", importe_pct=5, confianza=0.9)
    assert not check_buy(Decision("ZZZ", "comprar", importe_pct=5, confianza=0.9), ctx(), cfg).ok
    assert not check_buy(Decision("AAA", "comprar", importe_pct=5, confianza=0.3), ctx(), cfg).ok
    assert not check_buy(good, ctx(paused=True), cfg).ok
    assert not check_buy(good, ctx(equity=9_600, equity_day_start=10_000), cfg).ok  # -4 % hoy
    assert not check_buy(good, ctx(trades_today=4), cfg).ok
    assert not check_buy(good, ctx(cash=1_000), cfg).ok  # el 10 % debe quedarse en efectivo


def test_sell_rules():
    cfg = BotConfig(lista_activos=["AAA"])
    held = ctx(positions={"AAA": Position(10, 90)})
    assert check_sell(Decision("AAA", "vender", fraccion_venta=0.5), held, cfg).units == 5
    assert check_sell(Decision("AAA", "vender", fraccion_venta=0.5), held, cfg, full_only=True).units == 10
    assert not check_sell(Decision("BBB", "vender", fraccion_venta=1), held, cfg).ok
    assert stop_loss_hits({"AAA": Position(1, 100, 92)}, {"AAA": 91}) == ["AAA"]


# ------------------------------------------------------------------ bróker simulado
def test_paper_broker_buy_sell_with_spread(tmp_path):
    b = PaperBroker(Store(tmp_path / "s.sqlite"), 1_000, spread_pct=1.0)
    f = b.buy("AAA", 500, 100)
    assert f.price == pytest.approx(100.5) and b.cash() == pytest.approx(500)
    f = b.sell("AAA", 100, 100)  # pide más de lo que tiene: vende todo
    assert f.units == pytest.approx(500 / 100.5) and "AAA" not in b.positions()
    with pytest.raises(BrokerError):
        b.buy("AAA", 5_000, 100)


def test_etoro_broker_refuses_non_demo_paths():
    class FakeClient:
        cache = {}

        def _request(self, *a, **k):
            raise AssertionError("no debería llamarse")

    b = EToroDemoBroker(client=FakeClient())
    with pytest.raises(BrokerError, match="demo"):
        b._call("POST", "/trading/execution/market-open-orders/by-amount", {})


# ------------------------------------------------------------------ motor completo
def test_cycle_creates_proposal_and_approval_executes(tmp_path):
    e = make_engine(tmp_path, [Decision("AAA", "comprar", 5, 0, 0.9, "Tendencia", "Riesgo"), Decision("BBB", "mantener")])
    r = e.run_cycle()
    assert r["ok"] and r["propuestas"] == 1
    [p] = e.store.proposals("pendiente")
    assert p["ticker"] == "AAA" and p["amount"] == 500
    assert e.store.trades() == []  # nada se ejecuta sin aprobación

    ok, msg = e.approve(p["id"])
    assert ok, msg
    pos = e.broker.positions()["AAA"]
    assert pos.units == pytest.approx(5) and pos.stop_price == pytest.approx(92)
    assert e.approve(p["id"])[0] is False  # no se puede aprobar dos veces


def test_approval_fails_if_price_moved(tmp_path):
    e = make_engine(tmp_path, [Decision("AAA", "comprar", 5, 0, 0.9)])
    e.run_cycle()
    [p] = e.store.proposals("pendiente")
    e.source.set_last("AAA", 110)
    ok, msg = e.approve(p["id"])
    assert not ok and "precio se movió" in msg
    assert e.store.proposal(p["id"])["status"] == "fallida"


def test_rejected_decisions_are_recorded_with_reason(tmp_path):
    e = make_engine(tmp_path, [Decision("AAA", "comprar", 5, 0, 0.2)])
    e.run_cycle()
    [p] = e.store.proposals("descartada")
    assert "Confianza" in p["checks"][0]


def test_stop_loss_sells_automatically(tmp_path):
    e = make_engine(tmp_path, [Decision("AAA", "comprar", 5, 0, 0.9)])
    e.run_cycle()
    e.approve(e.store.proposals("pendiente")[0]["id"])
    e.source.set_last("AAA", 80)
    e._advisor = FixedAdvisor([])
    e.run_cycle()
    assert "AAA" not in e.broker.positions()
    assert e.store.trades()[0]["origin"] == "stop-loss"


def test_pause_stops_analysis(tmp_path):
    e = make_engine(tmp_path, [Decision("AAA", "comprar", 5, 0, 0.9)])
    e.store.set_paused(True)
    assert e.run_cycle().get("paused")
    assert e.store.proposals() == []


def test_proposals_expire(tmp_path):
    e = make_engine(tmp_path, [])
    pid = e.store.add_proposal("AAA", "comprar", 100, amount=100)
    with e.store.conn() as c:
        c.execute("UPDATE proposals SET created=? WHERE id=?", ((datetime.now(timezone.utc) - timedelta(hours=7)).isoformat(), pid))
    e.expire_proposals()
    assert e.store.proposal(pid)["status"] == "caducada"


def test_cycle_survives_advisor_errors(tmp_path):
    class Broken:
        def advise(self, *a):
            raise RuntimeError("sin red")

    e = make_engine(tmp_path, [])
    e._advisor = Broken()
    r = e.run_cycle()
    assert not r["ok"] and "sin red" in e.store.events()[0]["message"]


def test_rule_advisor_and_snapshot():
    close = pd.Series(np.linspace(50, 100, 300) + np.sin(np.arange(300)), index=pd.bdate_range("2025-01-01", periods=300))
    s = snapshot("AAA", close)
    s.sentimiento, s.sentimiento_veredicto = 0.3, "Alcista"
    from invest.trading.strategy import StrategyParams, score_snapshot

    s.puntuacion_estrategia = score_snapshot(s, StrategyParams())
    assert s.puntuacion_estrategia > 0.3
    loose = {"params": {**StrategyParams().as_dict(), "umbral_compra": 0.3}}
    adv = RuleAdvisor().advise([s], BotConfig(), 100, loose)
    assert adv.decisions[0].accion == "comprar"
    strict = {"params": {**StrategyParams().as_dict(), "umbral_compra": 0.9}}
    assert RuleAdvisor().advise([s], BotConfig(), 100, strict).decisions[0].accion == "mantener"


def test_config_validation(tmp_path):
    assert BotConfig().validate() == []
    bad = BotConfig(max_operacion_pct=30, max_posicion_pct=20, modo="real")
    errs = bad.validate()
    assert any("Modo" in e for e in errs) and any("max_operacion_pct" in e for e in errs)
    cfg = BotConfig(lista_activos=["AAA"])
    cfg.save(tmp_path / "c.json")
    assert BotConfig.load(tmp_path / "c.json").lista_activos == ["AAA"]


def test_claude_advisor_with_fake_client():
    from types import SimpleNamespace

    from invest.trading.advisor import ClaudeAdvisor

    seen = {}

    class FakeMessages:
        def parse(self, **kw):
            seen.update(kw)
            Result = kw["output_format"]
            Item = Result.model_fields["decisiones"].annotation.__args__[0]
            parsed = Result(
                decisiones=[
                    Item(ticker="AAA", accion="comprar", importe_pct=4, fraccion_venta=0, confianza=1.4, motivo="m", riesgos="r"),
                    Item(ticker="ZZZ", accion="comprar", importe_pct=4, fraccion_venta=0, confianza=0.9, motivo="m", riesgos="r"),
                ],
                resumen="ok",
            )
            return SimpleNamespace(stop_reason="end_turn", parsed_output=parsed)

    close = pd.Series(np.linspace(50, 100, 300), index=pd.bdate_range("2025-01-01", periods=300))
    adv = ClaudeAdvisor(client=SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages()))).advise([snapshot("AAA", close)], BotConfig(), 100)
    assert [d.ticker for d in adv.decisions] == ["AAA"]  # descarta activos fuera de la lista
    assert adv.decisions[0].confianza == 1.0  # recortada a [0, 1]
    assert seen["model"] == "claude-opus-5-5" and "AAA" in seen["messages"][0]["content"]
