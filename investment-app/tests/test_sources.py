from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from invest import news
from invest.data import EToroSource, FallbackSource, make_source
from invest.news import EToroClient, NewsItem
from invest.trading.advisor import Advice, Decision
from invest.trading.config import BotConfig
from invest.trading.engine import Engine

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Apple supera las previsiones - Expansión</title><link>https://x.test/1</link>
<pubDate>Mon, 02 Nov 2026 10:00:00 GMT</pubDate><source url="https://expansion.com">Expansión</source></item>
<item><title>Apple beats estimates as iPhone sales surge - Reuters</title><link>https://x.test/2</link>
<pubDate>Mon, 02 Nov 2026 09:00:00 GMT</pubDate><source url="https://reuters.com">Reuters</source></item>
</channel></rss>"""


def test_parse_google_rss_strips_source_suffix():
    items = news.parse_rss(RSS, "AAPL", "Google News (es)")
    assert [i.title for i in items] == ["Apple supera las previsiones", "Apple beats estimates as iPhone sales surge"]
    assert items[0].source == "Expansión" and items[0].via == "Google News (es)" and items[0].published.year == 2026


def test_dedupe_merges_same_story_from_two_sources():
    now = datetime.now(timezone.utc)
    a = NewsItem("Apple beats estimates as iPhone sales surge", published=now, via="Yahoo Finance")
    b = NewsItem("Apple beats estimates as iPhone sales surge strongly", published=now - timedelta(hours=1), via="Google News (en)")
    c = NewsItem("Gold hits record high", published=now, via="Yahoo Finance")
    out = news.dedupe([a, b, c])
    assert len(out) == 2
    assert "Google News (en)" in [o for o in out if o.title.startswith("Apple")][0].via


def test_aggregate_survives_failing_sources(monkeypatch):
    monkeypatch.setattr(news, "yahoo_news", lambda t, n: [NewsItem("Apple sube", via="Yahoo Finance", published=datetime.now(timezone.utc))])
    def boom(*a, **k):
        raise TimeoutError()
    monkeypatch.setattr(news, "google_news", boom)
    errors = []
    general = [NewsItem("Apple and Microsoft lead the rally", via="eToro (noticias)"), NewsItem("Oil falls", via="eToro (noticias)")]
    out = news.aggregate_news("AAPL", "Apple", ["yahoo", "google_es", "etoro"], etoro_client=object(), etoro_general=general, errors=errors)
    assert {i.title for i in out} == {"Apple sube", "Apple and Microsoft lead the rally"}  # "Oil falls" no menciona Apple
    assert errors == ["Google News (es): TimeoutError"]


class FakeEToro(EToroClient):
    """Responde como la API de eToro sin red."""

    def __init__(self):
        super().__init__("k", "u", cache={})
        self.calls = []

    def _request(self, method, path, params=None, body=None):
        self.calls.append((method, path, params, body))
        if path == self.SEARCH_PATH:
            sym = params["internalSymbolFull"]
            table = {"AAPL": (1001, 5), "GOLD": (18, 9)}
            if sym in table:
                return {"items": [{"InstrumentID": table[sym][0], "internalSymbolFull": sym, "marketId": table[sym][1]}]}
            return {"items": []}
        if "/history/candles/" in path:
            days = pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=60)
            return {"candles": [{"instrumentID": 1, "candles": [{"fromDate": d.isoformat() + "Z", "close": 100 + i} for i, d in enumerate(days)]}]}
        if path == self.RATES_PATH:
            return {"rates": [{"instrumentId": 1001, "lastExecution": 222.0}, {"instrumentId": 18, "lastExecution": 2500.0}]}
        if path.startswith("/feeds/instrument/"):
            return {"discussions": [{"message": {"text": "Comprando más, muy alcista"}, "owner": {"username": "ana"}}]}
        raise AssertionError(path)


def test_etoro_source_candles_rates_and_missing():
    src = EToroSource(FakeEToro())
    df = src.closes(["AAPL", "GC=F", "ZZZ"], "3mo")
    assert list(df.columns) == ["AAPL", "GC=F"] and src.missing == ["ZZZ"]
    assert df["AAPL"].iloc[-1] == 222.0  # último precio en vivo
    assert df["AAPL"].iloc[-2] == 159.0  # último cierre diario


def test_community_posts_use_market_id():
    c = FakeEToro()
    posts = c.instrument_posts("AAPL")
    assert posts[0].via == "eToro (comunidad)" and posts[0].source == "ana"
    assert c.calls[-1][1] == "/feeds/instrument/5"


def test_fallback_source_fills_missing():
    class Main:
        name = "eToro"
        def closes(self, t, p):
            return pd.DataFrame({"AAPL": [1.0, 2.0]}, index=pd.bdate_range("2026-01-01", periods=2))

    class Backup:
        name = "Yahoo"
        def closes(self, t, p):
            assert t == ["MSFT"]
            return pd.DataFrame({"MSFT": [3.0, 4.0]}, index=pd.bdate_range("2026-01-01", periods=2))

    src = FallbackSource(Main(), Backup())
    df = src.closes(["AAPL", "MSFT"], "1y")
    assert list(df.columns) == ["AAPL", "MSFT"] and src.used_backup == ["MSFT"]


def test_make_source(monkeypatch):
    monkeypatch.delenv("ETORO_API_KEY", raising=False)
    assert make_source("etoro").name == "Yahoo Finance"  # sin claves, Yahoo
    monkeypatch.setenv("ETORO_API_KEY", "a")
    monkeypatch.setenv("ETORO_USER_KEY", "b")
    assert make_source("etoro").name.startswith("eToro")
    assert make_source("demo").name.startswith("Datos simulados")


class Picker:
    """Asesor que compra el mejor candidato que le llega, para comprobar la preselección."""
    name = "picker"

    def __init__(self):
        self.seen = []

    def advise(self, snaps, cfg, cash_pct, strategy=None):
        self.seen = [s.ticker for s in snaps]
        best = max(snaps, key=lambda s: s.puntuacion_estrategia)
        return Advice([Decision(best.ticker, "comprar", 5, 0, 0.9, "mejor puntuación")], "", "picker")


def test_autonomous_demo_bot_picks_from_catalog_and_executes(tmp_path, monkeypatch):
    monkeypatch.delenv("ETORO_API_KEY", raising=False)
    cfg = BotConfig(fuente_datos="demo", lista_activos=[], max_candidatos=5)  # valores por defecto: catálogo, sin aprobación, demo
    assert cfg.modo == "etoro_demo" and not cfg.requiere_aprobacion and cfg.universo == "catalogo"
    picker = Picker()
    e = Engine(tmp_path, cfg=cfg, advisor=picker, news_fn=lambda t: [])
    r = e.run_cycle()
    assert r["ok"]
    assert len(picker.seen) == 5  # solo los 5 mejores candidatos reciben estudio a fondo
    trades = e.store.trades()
    assert len(trades) == 1 and trades[0]["origin"] == "automatica" and trades[0]["ticker"] in picker.seen
    # Sin claves de eToro usa la simulación local y lo avisa.
    assert any("Faltan las claves de eToro" in ev["message"] for ev in e.store.events())


def test_no_real_money_mode_exists():
    assert BotConfig(modo="real").validate()  # cualquier modo distinto de simulación/demo es inválido
    from invest.trading import broker
    assert not hasattr(broker, "EToroRealBroker")
    for path in (broker.EToroDemoBroker.PORTFOLIO_PATH, broker.EToroDemoBroker.OPEN_BY_AMOUNT_PATH, broker.EToroDemoBroker.CLOSE_PATH):
        assert "/demo/" in path
