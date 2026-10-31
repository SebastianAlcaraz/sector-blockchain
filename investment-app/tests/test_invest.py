import numpy as np
import pandas as pd
import pytest

from invest import analysis, portfolio, simulator
from invest.catalog import asset_class, label
from invest.data import DemoSource
from invest.indicators import macd, rsi, sma


def series(values, start="2020-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_sma():
    s = series([1, 2, 3, 4, 5])
    assert sma(s, 3).tolist()[2:] == [2, 3, 4]
    assert sma(s, 3).isna().sum() == 2


def test_rsi_extremes():
    assert rsi(series(range(1, 40))).iloc[-1] == 100
    assert rsi(series(range(40, 1, -1))).iloc[-1] == pytest.approx(0)
    assert rsi(series([5] * 30)).iloc[-1] == 50


def test_macd_positive_in_uptrend():
    m = macd(series(np.linspace(100, 200, 100) ** 1.01))
    assert m["macd"].iloc[-1] > 0


def test_metrics():
    s = series([100, 110, 99, 120])
    assert analysis.total_return(s) == pytest.approx(0.2)
    assert analysis.max_drawdown(s) == pytest.approx(-0.1)
    yearly = pd.Series([100.0, 121.0], index=pd.to_datetime(["2020-01-01", "2022-01-01"]))
    assert analysis.cagr(yearly) == pytest.approx(0.1, abs=1e-3)


def test_outlook_direction():
    up = series(np.linspace(50, 150, 300) + np.sin(np.arange(300)))
    down = series(np.linspace(150, 50, 300) + np.sin(np.arange(300)))
    assert analysis.technical_outlook(up).score > 0
    assert analysis.technical_outlook(down).score < 0
    assert analysis.technical_outlook(series([1, 2])).verdict == "Datos insuficientes"


def test_catalog():
    assert asset_class("GC=F") == "Materias primas"
    assert asset_class("XYZ=F") == "Materias primas"
    assert asset_class("DOGE-USD") == "Criptomonedas"
    assert asset_class("UNKNOWN") == "Acciones"
    assert label("GC=F") == "Oro (GC=F)"


def test_portfolio_valuation_and_rebalance(tmp_path):
    pos = pd.DataFrame(
        [
            {"ticker": " aapl ", "cantidad": 10, "precio_medio": 100},
            {"ticker": "GC=F", "cantidad": 1, "precio_medio": 1000},
            {"ticker": "", "cantidad": 5, "precio_medio": 1},
            {"ticker": "BAD", "cantidad": -1, "precio_medio": 1},
        ]
    )
    v = portfolio.valuate(pos, {"AAPL": 150, "GC=F": 500})
    assert v["ticker"].tolist() == ["AAPL", "GC=F"]
    assert v["ganancia"].tolist() == [500, -500]
    assert v["peso"].sum() == pytest.approx(1)

    reb = portfolio.rebalance(v, {"Acciones": 0.5, "Materias primas": 0.5}).set_index("clase")
    assert reb.loc["Acciones", "ajuste"] == pytest.approx(-500)
    assert reb.loc["Materias primas", "ajuste"] == pytest.approx(500)

    f = tmp_path / "c.json"
    portfolio.save_positions(pos, f)
    assert portfolio.load_positions(f)["ticker"].tolist() == ["AAPL", "GC=F"]


def test_simulator():
    close = pd.Series(10.0, index=pd.bdate_range("2021-01-01", "2021-06-30"))
    d = simulator.dca(close, 100)
    assert d.invested == 600  # 6 meses
    assert d.final_value == pytest.approx(600)
    ls = simulator.lump_sum(close * np.linspace(1, 2, len(close)), 600)
    assert ls.final_value == pytest.approx(1200)


def test_demo_source_reproducible():
    a = DemoSource().closes(["AAPL", "GC=F", "BTC-USD"], "1y")
    b = DemoSource().closes(["AAPL", "GC=F", "BTC-USD"], "1y")
    assert list(a.columns) == ["AAPL", "GC=F", "BTC-USD"]
    assert len(a) > 200 and (a > 0).all().all()
    pd.testing.assert_frame_equal(a, b)


def test_demo_last_price_does_not_depend_on_period():
    a = DemoSource().closes(["AAPL", "GC=F"], "1mo").iloc[-1]
    b = DemoSource().closes(["AAPL", "GC=F"], "5y").iloc[-1]
    pd.testing.assert_series_equal(a, b)
