from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from invest import news, sentiment


def test_lexicon_basic_polarity():
    lex = sentiment.LexiconAnalyzer()
    assert lex.score_text("Apple supera las previsiones y se dispara").label == "Positivo"
    assert lex.score_text("Tesla se desploma tras resultados peores de lo esperado").label == "Negativo"
    assert lex.score_text("Nvidia beats estimates, shares surge").label == "Positivo"
    assert lex.score_text("Oil plunges on recession fears").label == "Negativo"
    assert lex.score_text("La empresa celebrará su junta el próximo mes").label == "Neutral"


def test_lexicon_negation():
    lex = sentiment.LexiconAnalyzer()
    assert lex.score_text("Shares rise").score > 0
    assert lex.score_text("Shares did not rise").score < 0
    assert lex.score_text("La compañía no supera las previsiones").score < 0


def test_aggregate_weights_recent_news_more():
    now = datetime.now(timezone.utc)
    scored = [sentiment.Scored("a", 0.8, "Positivo"), sentiment.Scored("b", -0.8, "Negativo")]
    agg = sentiment.aggregate(scored, [now, now - timedelta(days=10)])
    assert agg.score > 0.5 and agg.label == "Alcista"
    assert (agg.positive, agg.negative, agg.total) == (1, 1, 2)
    assert sentiment.aggregate([]).label == "Sin datos"


def test_parse_yahoo_new_and_old_formats():
    new = {"content": {"title": "Gold rallies", "summary": "Prices up", "pubDate": "2026-10-30T12:00:00Z",
                       "provider": {"displayName": "Reuters"}, "canonicalUrl": {"url": "https://x.test/a"}}}
    old = {"title": "Gold falls", "publisher": "AP", "link": "https://x.test/b", "providerPublishTime": 1700000000}
    a, b = news.parse_yahoo_item(new, "GC=F"), news.parse_yahoo_item(old)
    assert (a.title, a.source, a.url, a.published.year) == ("Gold rallies", "Reuters", "https://x.test/a", 2026)
    assert a.text == "Gold rallies. Prices up"
    assert (b.title, b.source, b.published.year) == ("Gold falls", "AP", 2023)
    assert news.parse_yahoo_item({"content": {}}) is None


def test_demo_news_is_deterministic_and_sorted():
    a = news.demo_news("AAPL", "Apple", 10)
    b = news.demo_news("AAPL", "Apple", 10)
    assert [i.title for i in a] == [i.title for i in b]
    assert all("Apple" in i.title for i in a)
    assert [i.published for i in a] == sorted([i.published for i in a], reverse=True)


def test_etoro_parsing_is_tolerant():
    payload = {"data": {"items": [
        {"message": {"text": "Comprando más oro\nMe parece alcista"}, "owner": {"username": "ana"}, "created": "2026-10-30T10:00:00Z"},
        {"message": {"text": ""}},
    ]}}
    items = news.EToroClient._items(payload)
    assert len(items) == 2
    n = news.EToroClient._to_news(items[0], "GC=F")
    assert (n.title, n.summary, n.source) == ("Comprando más oro", "Me parece alcista", "ana")
    assert news.EToroClient._to_news(items[1]) is None
    assert news.to_etoro_symbol("GC=F") == "GOLD" and news.to_etoro_symbol("SAN.MC") == "SAN"


def test_etoro_configured_reads_env(monkeypatch):
    monkeypatch.delenv("ETORO_API_KEY", raising=False)
    assert not news.EToroClient.configured()
    monkeypatch.setenv("ETORO_API_KEY", "a")
    monkeypatch.setenv("ETORO_USER_KEY", "b")
    assert news.EToroClient.configured()


def test_claude_analyzer_maps_results_with_fake_client():
    captured = {}

    class FakeMessages:
        def parse(self, **kwargs):
            captured.update(kwargs)
            Result = kwargs["output_format"]
            Item = Result.model_fields["items"].annotation.__args__[0]
            parsed = Result(items=[Item(indice=1, sentimiento="negativo", puntuacion=-0.9, motivo="Caída")], resumen="Tono mixto.")
            return SimpleNamespace(stop_reason="end_turn", parsed_output=parsed)

    fake = SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages()))
    scored, summary = sentiment.ClaudeAnalyzer(client=fake).score_many(["Sube", "Cae"], "Oro")
    assert captured["model"] == "claude-opus-5-5"
    assert summary == "Tono mixto."
    assert scored[0].label == "Neutral" and scored[0].reason == "Sin clasificar"  # índice ausente
    assert scored[1].label == "Negativo" and scored[1].score == -0.9
