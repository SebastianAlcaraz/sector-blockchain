"""Stop-loss según la volatilidad (ATR), tamaño por riesgo y velas completas."""

import numpy as np
import pandas as pd

from invest.data import DemoSource
from invest.indicators import atr
from invest.trading import backtest
from invest.trading.advisor import Decision
from invest.trading.config import BotConfig
from invest.trading.risk import RiskContext, check_buy, stop_pct_for
from invest.trading.store import Store
from invest.trading.strategy import StrategyParams

from test_trading import FixedAdvisor, FixedSource, make_engine


def ctx(**kw):
    base = dict(equity=10_000, cash=10_000, positions={}, prices={"AAA": 100.0})
    base.update(kw)
    return RiskContext(**base)


def test_atr_matches_hand_calculation():
    high = pd.Series([11.0, 12.0, 13.0])
    low = pd.Series([9.0, 10.0, 9.0])
    close = pd.Series([10.0, 11.0, 12.0])
    # Rangos verdaderos: 2 (primer día), max(2, 2, 1) = 2, max(4, 2, 2) = 4
    out = atr(high, low, close, period=2)
    assert np.isnan(out.iloc[0])
    assert out.iloc[1] == 2.0
    assert out.iloc[2] == 3.0  # Wilder: 2 + (4 - 2) / 2


def test_stop_follows_volatility_with_limits():
    cfg = BotConfig()
    assert stop_pct_for(cfg, 1.5)[0] == 3.0  # 2 × ATR
    assert stop_pct_for(cfg, 0.2)[0] == 1.0  # mínimo 1 %
    assert stop_pct_for(cfg, 12.0)[0] == 15.0  # tope stop_max_pct
    assert stop_pct_for(cfg, None) == (8.0, "fijo: no hay velas para calcular el ATR")
    assert stop_pct_for(BotConfig(tipo_stop="fijo"), 1.5)[0] == 8.0


def test_buy_is_sized_so_a_stop_loses_at_most_the_risk_limit():
    cfg = BotConfig(lista_activos=["AAA"], max_operacion_pct=20, max_posicion_pct=30, riesgo_operacion_pct=1.0)
    d = Decision("AAA", "comprar", importe_pct=20, confianza=0.9)
    # Activo volátil: stop al 10 % (2 × 5 %) -> como mucho 1 % / 10 % = 10 % de la cartera.
    v = check_buy(d, ctx(atr_pct={"AAA": 5.0}), cfg)
    assert v.ok and v.stop_pct == 10.0 and v.amount == 1000
    assert any("arriesgar como máximo un 1 %" in n for n in v.notes)
    # Activo tranquilo: stop al 2 % -> el límite de riesgo no recorta; manda el máximo por operación.
    v = check_buy(d, ctx(atr_pct={"AAA": 1.0}), cfg)
    assert v.ok and v.stop_pct == 2.0 and v.amount == 2000
    assert v.notes[-1] == "Si salta el stop se perdería un 0.40 % de la cartera."


def test_demo_source_candles_wrap_the_close():
    src = DemoSource()
    candles = src.ohlc(["SPY", "BTC-USD"], "6mo")
    for t, df in candles.items():
        assert (df["high"] >= df["close"]).all() and (df["low"] <= df["close"]).all()
        assert df["close"].equals(src.closes([t], "6mo")[t])
    a_spy = atr(**{k: candles["SPY"][k] for k in ("high", "low", "close")}).iloc[-1] / candles["SPY"]["close"].iloc[-1]
    a_btc = atr(**{k: candles["BTC-USD"][k] for k in ("high", "low", "close")}).iloc[-1] / candles["BTC-USD"]["close"].iloc[-1]
    assert a_btc > 2 * a_spy  # cripto se mueve mucho más que un ETF


class CandleSource(FixedSource):
    """Igual que FixedSource, con velas: AAA se mueve ±3 % al día."""

    def ohlc(self, tickers, period="6mo"):
        return {t: pd.DataFrame({"high": self.df[t] * 1.03, "low": self.df[t] * 0.97, "close": self.df[t]}) for t in tickers if t in self.df}


def test_cycle_uses_atr_stop_and_approval_places_it(tmp_path):
    eng = make_engine(tmp_path, [Decision("AAA", "comprar", importe_pct=5, confianza=0.9, motivo="sube")])
    eng._source = CandleSource()
    eng.run_cycle()
    p = eng.store.proposals("pendiente")[0]
    assert 11 < p["stop_pct"] < 13  # 2 × ATR (~6 %)
    ok, _ = eng.approve(p["id"])
    assert ok
    pos = eng.broker.positions()["AAA"]
    assert abs(pos.stop_price / 100 - (1 - p["stop_pct"] / 100)) < 1e-6


def test_cycle_without_candles_keeps_fixed_stop(tmp_path):
    eng = make_engine(tmp_path, [Decision("AAA", "comprar", importe_pct=5, confianza=0.9)])
    eng.run_cycle()
    p = eng.store.proposals("pendiente")[0]
    assert p["stop_pct"] == 8.0


def test_old_database_gets_stop_column(tmp_path):
    import sqlite3

    path = tmp_path / "bot.sqlite"
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE proposals (id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL, ticker TEXT NOT NULL, side TEXT NOT NULL, amount REAL, units REAL, price REAL NOT NULL, confidence REAL, reason TEXT, risks TEXT, checks TEXT, status TEXT NOT NULL, decided TEXT, result TEXT)")
    store = Store(path)
    pid = store.add_proposal("AAA", "comprar", 100.0, amount=500, stop_pct=4.0)
    assert store.proposal(pid)["stop_pct"] == 4.0


def test_backtest_runs_with_atr_and_fixed_stops():
    tickers = ["SPY", "QQQ", "GLD", "BTC-USD"]
    closes = DemoSource().closes(tickers, "5y")
    for tipo in ("atr", "fijo"):
        cfg = BotConfig(lista_activos=tickers, referencia="SPY", tipo_stop=tipo)
        r = backtest.evaluate(closes, StrategyParams(), cfg)
        assert r["fuera"]["operaciones"] >= 0 and -1 < r["fuera"]["max_caida"] <= 0


def test_etoro_candles_read_high_and_low():
    from invest.data import EToroSource
    from test_sources import FakeEToro

    class WithRanges(FakeEToro):
        def _request(self, method, path, params=None, body=None):
            if "/history/candles/" in path:
                days = pd.bdate_range(end="2026-10-30", periods=3)
                rows = [{"fromDate": d.isoformat() + "Z", "high": 105 + i, "low": 95 + i, "close": 100 + i} for i, d in enumerate(days)]
                rows[-1].pop("high")  # sin máximo: se usa el cierre
                return {"candles": [{"instrumentID": 1001, "candles": rows}]}
            return super()._request(method, path, params, body)

    out = EToroSource(WithRanges()).ohlc(["AAPL", "ZZZ"], "1mo")
    assert list(out) == ["AAPL"]
    df = out["AAPL"]
    assert df["high"].tolist() == [105.0, 106.0, 102.0] and df["low"].tolist() == [95.0, 96.0, 97.0]
