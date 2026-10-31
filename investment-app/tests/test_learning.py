from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from invest.data import DemoSource
from invest.trading import backtest, learning
from invest.trading.advisor import Advice, Decision
from invest.trading.config import BotConfig
from invest.trading.engine import Engine
from invest.trading.strategy import BOUNDS, StrategyParams, score_series

TICKERS = ["SPY", "AAPL", "GC=F", "MSFT"]


def demo_engine(tmp_path, asesor="reglas"):
    cfg = BotConfig(lista_activos=TICKERS, referencia="SPY", fuente_datos="demo", asesor=asesor, diferencial_pct=0.1)
    return Engine(tmp_path, cfg=cfg, news_fn=lambda t: [])


def test_params_are_clamped_to_bounds():
    p = StrategyParams.from_dict({"umbral_compra": 5, "umbral_venta": 3, "dias_minimos": 99.7, "peso_rsi": -1, "desconocido": 1})
    assert p.umbral_compra == BOUNDS["umbral_compra"][1]
    assert p.umbral_venta < p.umbral_compra
    assert p.dias_minimos == 30 and isinstance(p.dias_minimos, int)
    assert p.peso_rsi == 0


def test_score_series_follows_trend():
    idx = pd.bdate_range("2022-01-01", periods=400)
    up = pd.Series(np.linspace(50, 150, 400), index=idx)
    down = pd.Series(np.linspace(150, 50, 400), index=idx)
    p = StrategyParams(peso_rsi=0)  # el RSI de una recta es extremo; se aísla la tendencia
    assert score_series(up, p).iloc[-1] > 0.5
    assert score_series(down, p).iloc[-1] < -0.5


def test_backtest_runs_and_respects_cash_floor():
    closes = DemoSource().closes(TICKERS, "5y")
    cfg = BotConfig(lista_activos=TICKERS, referencia="SPY")
    res = backtest.evaluate(closes, StrategyParams(), cfg)
    assert set(res["dentro"]) >= {"rentabilidad", "referencia", "max_caida", "sharpe", "operaciones"}
    assert res["fuera"]["max_caida"] <= 0
    # Con todos los pesos a cero no hay señal no hay operaciones y la curva queda plana.
    flat = backtest.evaluate(closes, StrategyParams(peso_tendencia=0, peso_impulso=0, peso_rsi=0, peso_rendimiento_3m=0), cfg)
    assert flat["fuera"]["rentabilidad"] == pytest.approx(0, abs=1e-9)


def test_compare_flags_worse_candidate():
    cur = {"dentro": {"rentabilidad": 0.1}, "fuera": {"rentabilidad": 0.05, "max_caida": -0.1, "operaciones": 10}}
    worse = {"dentro": {"rentabilidad": 0.4}, "fuera": {"rentabilidad": 0.01, "max_caida": -0.2, "operaciones": 10}}
    better = {"dentro": {"rentabilidad": 0.12}, "fuera": {"rentabilidad": 0.08, "max_caida": -0.1, "operaciones": 8}}
    ok, reasons = backtest.compare(cur, worse)
    assert not ok and any("sobreajuste" in r for r in reasons)
    assert backtest.compare(cur, better)[0]


def test_decisions_are_journaled_and_evaluated(tmp_path):
    e = demo_engine(tmp_path)
    e.run_cycle()
    decisions = e.store.decisions()
    assert len(decisions) == len(TICKERS)  # una por activo, incluidas las de mantener
    assert all(d["features"]["puntuacion_estrategia"] is not None for d in decisions)
    # Se envejecen y se usa un precio de entrada conocido para comprobar el cálculo.
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    closes = DemoSource().closes(["AAPL", "SPY"], "1y")
    day = closes.index[closes.index >= pd.Timestamp(old[:10])][0]
    target = closes.index[closes.index >= (pd.Timestamp(old[:10]) + pd.Timedelta(days=14))][0]
    with e.store.conn() as c:
        c.execute("UPDATE decisions SET ts=?, price=?, bench_price=? WHERE ticker='AAPL'", (old, closes.at[day, "AAPL"], closes.at[day, "SPY"]))
    assert learning.evaluate_decisions(e) == 1
    d = [x for x in e.store.decisions(evaluated=True) if x["ticker"] == "AAPL"][0]
    assert d["fwd_return"] == pytest.approx(closes.at[target, "AAPL"] / closes.at[day, "AAPL"] - 1)


def test_decision_stats():
    ev = "2026-01-01"
    ds = [
        {"action": "comprar", "fwd_return": 0.05, "bench_return": 0.01, "score": 0.6, "evaluated": ev},
        {"action": "comprar", "fwd_return": -0.02, "bench_return": 0.01, "score": 0.5, "evaluated": ev},
        {"action": "vender", "fwd_return": -0.05, "bench_return": 0.0, "score": -0.5, "evaluated": ev},
        {"action": "mantener", "fwd_return": 0.0, "bench_return": 0.0, "score": 0.0, "evaluated": None},
    ]
    st = learning.decision_stats(ds)
    assert st["evaluadas"] == 3
    assert st["por_accion"]["comprar"]["aciertos"] == 0.5
    assert st["por_accion"]["vender"]["aciertos"] == 1.0
    assert st["por_puntuacion"]["alta (> 0,3)"]["n"] == 2


def test_review_without_ai_creates_validated_candidate_and_adopt(tmp_path):
    e = demo_engine(tmp_path)
    v1 = learning.active_strategy(e)
    r = learning.review(e)
    cand = e.store.strategy(r["candidata"])
    assert cand["status"] == "candidata" and cand["origin"] == "optimizador"
    assert {"actual", "candidata", "motivos"} <= set(cand["metrics"])
    assert learning.active_strategy(e)["id"] == v1["id"]  # nada cambia sin tu decisión
    learning.adopt(e, cand["id"])
    assert learning.active_strategy(e)["id"] == cand["id"]
    assert e.store.strategy(v1["id"])["status"] == "retirada"
    learning.adopt(e, v1["id"])  # volver atrás
    assert learning.active_strategy(e)["id"] == v1["id"]


def test_review_with_fake_claude(tmp_path):
    e = demo_engine(tmp_path, asesor="claude")
    seen = {}

    class FakeMessages:
        def parse(self, **kw):
            seen.update(kw)
            Review = kw["output_format"]
            Params = Review.model_fields["parametros"].annotation
            params = {k: v for k, v in StrategyParams(umbral_compra=0.5).as_dict().items()}
            params["peso_rsi"] = 9  # fuera de rango: debe recortarse
            parsed = Review(diagnostico="d", lecciones=["Evitar RSI alto"], parametros=Params(**params), manual="1. Nuevo manual", cambios="Sube el umbral")
            return SimpleNamespace(stop_reason="end_turn", parsed_output=parsed)

    r = learning.review(e, client=SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages())))
    cand = e.store.strategy(r["candidata"])
    assert cand["origin"] == "IA" and cand["lessons"] == ["Evitar RSI alto"] and cand["playbook"] == "1. Nuevo manual"
    assert cand["params"]["peso_rsi"] == BOUNDS["peso_rsi"][1]
    assert seen["model"] == "claude-opus-5-5" and "rangos_permitidos" in seen["messages"][0]["content"]


def test_claude_advisor_receives_playbook_and_lessons(tmp_path):
    e = demo_engine(tmp_path)
    captured = {}

    class Spy:
        name = "spy"

        def advise(self, snaps, cfg, cash_pct, strategy=None):
            captured["strategy"] = strategy
            captured["scores"] = [s.puntuacion_estrategia for s in snaps]
            return Advice([Decision(s.ticker, "mantener") for s in snaps], "", "spy")

    e._advisor = Spy()
    e.run_cycle()
    assert captured["strategy"]["playbook"] and captured["strategy"]["status"] == "activa"
    assert all(s is not None for s in captured["scores"])
