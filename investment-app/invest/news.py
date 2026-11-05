"""Fuentes de noticias y publicaciones de la comunidad.

- yahoo_news: titulares de Yahoo Finance (gratis, sin clave).
- demo_news: titulares simulados para el modo demo.
- EToroClient: noticias y publicaciones de la comunidad de eToro (EXPERIMENTAL, necesita claves).
"""

from __future__ import annotations

import json
import os
import random
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class NewsItem:
    title: str
    summary: str = ""
    url: str = ""
    source: str = ""
    published: datetime | None = None
    ticker: str = ""
    via: str = ""  # de qué servicio viene: Yahoo Finance, Google News, eToro...
    tags: list = field(default_factory=list)  # activos etiquetados (publicaciones de eToro)

    @property
    def text(self) -> str:
        return f"{self.title}. {self.summary}".strip(". ") if self.summary else self.title


def _parse_time(value) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, OSError):
        return None


# ------------------------------------------------------------------ Yahoo Finance
def parse_yahoo_item(raw: dict, ticker: str = "") -> NewsItem | None:
    """Admite el formato nuevo de yfinance ({'content': {...}}) y el antiguo (campos planos)."""
    c = raw.get("content") if isinstance(raw.get("content"), dict) else raw
    title = (c.get("title") or "").strip()
    if not title:
        return None
    url = ""
    for key in ("canonicalUrl", "clickThroughUrl"):
        if isinstance(c.get(key), dict) and c[key].get("url"):
            url = c[key]["url"]
            break
    url = url or c.get("link", "")
    provider = c.get("provider")
    source = provider.get("displayName", "") if isinstance(provider, dict) else c.get("publisher", "")
    published = _parse_time(c.get("pubDate") or c.get("displayTime") or c.get("providerPublishTime"))
    summary = (c.get("summary") or c.get("description") or "").strip()
    return NewsItem(title, summary, url, source, published, ticker, "Yahoo Finance")


def yahoo_news(ticker: str, limit: int = 20) -> list[NewsItem]:
    import yfinance as yf

    t = yf.Ticker(ticker)
    try:
        raw = t.get_news(count=limit)
    except TypeError:  # versiones antiguas sin `count`
        raw = t.news
    items = [parse_yahoo_item(r, ticker) for r in (raw or [])]
    items = [i for i in items if i]
    items.sort(key=lambda i: i.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items[:limit]


# ------------------------------------------------------------------ Demo
_DEMO_POS = [
    "{n} supera las previsiones de beneficios del trimestre",
    "Los analistas elevan el precio objetivo de {n}",
    "{n} se dispara tras anunciar un acuerdo estratégico",
    "Fuerte demanda impulsa las ventas de {n}",
    "{n} marca máximos históricos con el apoyo de los inversores",
    "{n} anuncia una recompra de acciones",
]
_DEMO_NEG = [
    "{n} cae tras unos resultados peores de lo esperado",
    "Un banco rebaja la recomendación de {n} a vender",
    "Temores regulatorios presionan a {n}",
    "{n} se desploma por la recogida de beneficios",
    "Los aranceles generan preocupación sobre {n}",
    "{n} recorta previsiones para el año",
]
_DEMO_NEU = [
    "{n} celebrará su junta de accionistas el próximo mes",
    "Qué esperar de {n} esta semana",
    "{n} presenta su informe anual de sostenibilidad",
    "Cinco datos sobre {n} que conviene conocer",
]


def demo_news(ticker: str, name: str, limit: int = 12) -> list[NewsItem]:
    rng = random.Random(zlib.crc32(ticker.encode()) + datetime.now().toordinal())
    bias = rng.uniform(-0.5, 0.5)  # cada activo tiene un tono distinto
    now = datetime.now(timezone.utc)
    out = []
    for i in range(limit):
        r = rng.random()
        pool = _DEMO_POS if r < 0.35 + bias * 0.5 else _DEMO_NEG if r < 0.75 else _DEMO_NEU
        title = rng.choice(pool).format(n=name)
        out.append(NewsItem(title, "", "", "Noticia simulada", now - timedelta(hours=rng.uniform(1, 24 * 7)), ticker, "Demo"))
    out.sort(key=lambda i: i.published, reverse=True)
    return out


# ------------------------------------------------------------------ eToro (experimental)
class EToroError(RuntimeError):
    pass


class EToroClient:
    """Cliente de la API pública de eToro.

    Rutas tomadas de la documentación pública de eToro (api-portal.etoro.com y builders.etoro.com).
    NO se han podido probar con una cuenta real: si algo falla, ajusta las rutas de esta clase.

    Claves como variables de entorno (nunca en el código):
      ETORO_API_KEY   clave de la aplicación
      ETORO_USER_KEY  clave de usuario
    """

    BASE = "https://public-api.etoro.com/api/v1"
    NEWS_PATH = "/feeds/news"
    INSTRUMENT_FEED_PATH = "/feeds/instrument/{market_id}"
    SEARCH_PATH = "/market-data/search"
    CANDLES_PATH = "/market-data/instruments/{instrument_id}/history/candles/{direction}/{interval}/{count}"
    RATES_PATH = "/market-data/instruments/rates"

    def __init__(self, api_key: str | None = None, user_key: str | None = None, timeout: float = 15, cache: dict | None = None):
        self.api_key = api_key or os.environ.get("ETORO_API_KEY", "")
        self.user_key = user_key or os.environ.get("ETORO_USER_KEY", "")
        self.timeout = timeout
        self.cache = cache if cache is not None else {}  # ticker -> {"instrumentId", "marketId", "symbol"}

    @classmethod
    def configured(cls) -> bool:
        return bool(os.environ.get("ETORO_API_KEY") and os.environ.get("ETORO_USER_KEY"))

    def _get(self, path: str, params: dict | None = None):
        return self._request("GET", path, params)

    def _request(self, method: str, path: str, params: dict | None = None, body: dict | None = None):
        url = self.BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
        headers = {
            "x-api-key": self.api_key,
            "x-user-key": self.user_key,
            "x-request-id": str(uuid.uuid4()),
            "Accept": "application/json",
        }
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            msg = {401: "claves no válidas", 403: "sin permiso", 404: "ruta no encontrada", 429: "límite de consultas superado (espera un minuto)"}.get(e.code, f"error HTTP {e.code}")
            raise EToroError(f"eToro: {msg}.") from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise EToroError(f"eToro: no se pudo conectar ({e}).") from e

    @staticmethod
    def _items(payload) -> list[dict]:
        """Encuentra la lista de elementos aunque venga envuelta ({'items': [...]}, {'data': ...})."""
        if isinstance(payload, list):
            return [p for p in payload if isinstance(p, dict)]
        if isinstance(payload, dict):
            for key in ("items", "posts", "data", "results", "feed", "news", "discussions", "instruments", "rates", "candles"):
                if key in payload:
                    return EToroClient._items(payload[key])
        return []

    @staticmethod
    def _field(d: dict, *names):
        """Lee un campo admitiendo variantes de mayúsculas (instrumentId / InstrumentID)."""
        lower = {k.lower(): v for k, v in d.items()}
        for n in names:
            if n.lower() in lower and lower[n.lower()] is not None:
                return lower[n.lower()]
        return None

    @staticmethod
    def _to_news(raw: dict, ticker: str = "", via: str = "eToro", focus: tuple[str, ...] = ()) -> NewsItem | None:
        """Convierte una publicación de eToro. Formato real: {"post": {"message": {"text"}, "owner", "created", "tags"}}.

        Muchas publicaciones repasan varios activos a la vez: con `focus` (símbolos o nombres) se quedan
        solo los párrafos que hablan del activo, para no mezclar el tono de otras noticias.
        """
        post = raw.get("post") if isinstance(raw.get("post"), dict) else raw
        msg = post.get("message") if isinstance(post.get("message"), dict) else post
        text = next((str(msg[k]).strip() for k in ("title", "text", "body", "content", "message") if isinstance(msg.get(k), str) and msg[k].strip()), "")
        if not text:
            return None
        tags = []
        for t in post.get("tags") or []:
            market = t.get("market") if isinstance(t, dict) else None
            if isinstance(market, dict) and market.get("symbolName"):
                tags.append(str(market["symbolName"]).upper())
        if focus and len(tags) > 1:
            paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
            keys = [f.lower() for f in focus if f]
            relevant = [p for p in paragraphs if any(k in p.lower() for k in keys)]
            if relevant:
                text = "\n".join(relevant)
        title, _, rest = text.partition("\n")
        owner = post.get("owner") or post.get("author") or post.get("user") or {}
        source = (owner.get("username") or owner.get("userName") or "") if isinstance(owner, dict) else ""
        published = _parse_time(post.get("created") or post.get("createdAt") or post.get("date") or post.get("publishedAt"))
        url = post.get("url") or post.get("link") or ""
        return NewsItem(title[:300], rest.strip()[:600], url, source or "eToro", published, ticker, via, tags)

    # ---------------------------------------------------------- instrumentos
    def find_instrument(self, ticker: str) -> dict | None:
        """Busca el activo en eToro (primero el símbolo completo, después la equivalencia). Se guarda en caché."""
        if ticker in self.cache:
            return self.cache[ticker]
        for symbol in dict.fromkeys([_ETORO_SYMBOLS.get(ticker, ticker), to_etoro_symbol(ticker)]):
            payload = self._get(self.SEARCH_PATH, {"internalSymbolFull": symbol, "fields": "instrumentId,internalSymbolFull,displayname,marketId", "pageSize": 5})
            for item in self._items(payload):
                sym = str(self._field(item, "internalSymbolFull", "symbol") or "").upper()
                iid = self._field(item, "instrumentId")
                if sym == symbol.upper() and iid is not None:
                    found = {"instrumentId": int(iid), "marketId": self._field(item, "marketId"), "symbol": sym}
                    self.cache[ticker] = found
                    return found
        return None

    def find_instrument_id(self, symbol: str) -> int | None:
        found = self.find_instrument(symbol)
        return found["instrumentId"] if found else None

    # ---------------------------------------------------------- precios
    def candles(self, instrument_id: int, count: int = 400, interval: str = "OneDay"):
        """Velas diarias -> pd.Series de cierres indexada por fecha (sin zona horaria)."""
        return self.candles_ohlc(instrument_id, count, interval)["close"]

    def candles_ohlc(self, instrument_id: int, count: int = 400, interval: str = "OneDay"):
        """Velas diarias -> pd.DataFrame con máximo, mínimo y cierre, indexado por fecha.

        Si una vela no trae máximo o mínimo, se usa el cierre (el ATR saldrá algo más bajo).
        """
        import pandas as pd

        payload = self._get(self.CANDLES_PATH.format(instrument_id=instrument_id, direction="asc", interval=interval, count=min(int(count), 1000)))
        rows = self._candle_rows(payload)
        data = {}
        for r in rows:
            close = self._field(r, "close", "closeRate", "c")
            when = _parse_time(self._field(r, "fromDate", "date", "time", "timestamp", "toDate"))
            if close is None or when is None:
                continue
            ts = pd.Timestamp(when)
            if ts.tzinfo is not None:
                ts = ts.tz_convert(None)
            high = self._field(r, "high", "highRate", "h")
            low = self._field(r, "low", "lowRate", "l")
            close = float(close)
            data[ts.normalize()] = (
                max(float(high), close) if high is not None else close,
                min(float(low), close) if low is not None else close,
                close,
            )
        df = pd.DataFrame.from_dict(data, orient="index", columns=["high", "low", "close"], dtype=float)
        return df.sort_index()

    @classmethod
    def _candle_rows(cls, payload) -> list[dict]:
        """Las velas pueden venir anidadas ({"candles": [{"instrumentID": .., "candles": [...]}]})."""
        rows = cls._items(payload)
        out = []
        for r in rows:
            inner = r.get("candles") if isinstance(r, dict) else None
            if isinstance(inner, list):
                out.extend(x for x in inner if isinstance(x, dict))
            else:
                out.append(r)
        return out

    def rates(self, instrument_ids: list[int]) -> dict[int, float]:
        """Último precio de varios instrumentos (una petición por instrumento si no admite listas)."""
        out: dict[int, float] = {}

        def parse(payload):
            for r in self._items(payload):
                iid = self._field(r, "instrumentId")
                price = self._field(r, "lastExecution", "lastPrice", "bid")
                if iid is not None and price is not None:
                    out[int(iid)] = float(price)

        try:
            parse(self._get(self.RATES_PATH, {"instrumentIds": ",".join(str(i) for i in instrument_ids)}))
        except EToroError:
            pass
        for iid in instrument_ids:
            if iid not in out:
                try:
                    parse(self._get(self.RATES_PATH, {"instrumentIds": str(iid)}))
                except EToroError:
                    continue
        return out

    # ---------------------------------------------------------- noticias y comunidad
    def news(self, limit: int = 50) -> list[NewsItem]:
        """Feed de noticias de eToro. Son publicaciones seleccionadas de inversores (no artículos de prensa),
        etiquetadas con los activos de los que hablan."""
        items = self._items(self._get(self.NEWS_PATH, {"take": limit}))
        return [n for n in (self._to_news(i, via="eToro (feed de noticias)") for i in items) if n][:limit]

    def instrument_posts(self, ticker: str, limit: int = 30, name: str = "") -> list[NewsItem]:
        found = self.find_instrument(ticker)
        if not found:
            raise EToroError(f"eToro: no se encontró el activo {ticker}.")
        market_id = found.get("marketId") or found["instrumentId"]  # en eToro coinciden con el instrumentId
        focus = (found.get("symbol", ""), f"${found.get('symbol', '')}", name)
        items = self._items(self._get(self.INSTRUMENT_FEED_PATH.format(market_id=market_id), {"take": limit}))
        return [n for n in (self._to_news(i, ticker, "eToro (comunidad)", focus) for i in items) if n][:limit]


# Equivalencias de símbolos Yahoo -> eToro.
_ETORO_SYMBOLS = {
    "GC=F": "GOLD", "SI=F": "SILVER", "HG=F": "COPPER", "PL=F": "PLATINUM", "CL=F": "OIL",
    "BZ=F": "OILBRENT", "NG=F": "NATGAS", "ZC=F": "CORN", "ZW=F": "WHEAT", "ZS=F": "SOYBEANS",
    "KC=F": "COFFEE", "SB=F": "SUGAR", "BTC-USD": "BTC", "ETH-USD": "ETH", "SOL-USD": "SOL",
    "^GSPC": "SPX500", "^IXIC": "NSDQ100", "^DJI": "DJ30", "^STOXX50E": "EUSTX50",
    "EURUSD=X": "EURUSD", "USDMXN=X": "USDMXN",
}


def to_etoro_symbol(ticker: str) -> str:
    return _ETORO_SYMBOLS.get(ticker, ticker.split(".")[0])


# ------------------------------------------------------------------ Google News (RSS, sin clave)
_GOOGLE_EDITIONS = {"es": {"hl": "es", "gl": "ES", "ceid": "ES:es"}, "en": {"hl": "en-US", "gl": "US", "ceid": "US:en"}}


def parse_rss(xml_text: str, ticker: str = "", via: str = "Google News") -> list[NewsItem]:
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        source_el = item.find("source")
        source = (source_el.text or "").strip() if source_el is not None else ""
        if source and title.endswith(" - " + source):  # Google añade " - Medio" al final del titular
            title = title[: -len(" - " + source)]
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
        except (TypeError, ValueError):
            published = None
        out.append(NewsItem(title, "", (item.findtext("link") or "").strip(), source, published, ticker, via))
    return out


# Términos de búsqueda de materias primas en cada idioma: "Oro" en inglés encuentra "Cagayan de Oro".
_COMMODITY_TERMS = {
    "GC=F": ("precio del oro", "gold price"), "SI=F": ("precio de la plata", "silver price"),
    "HG=F": ("precio del cobre", "copper price"), "PL=F": ("precio del platino", "platinum price"),
    "CL=F": ("petróleo WTI", "WTI crude oil"), "BZ=F": ("petróleo Brent", "Brent crude oil"),
    "NG=F": ("precio del gas natural", "natural gas prices"), "ZC=F": ("precio del maíz", "corn futures"),
    "ZW=F": ("precio del trigo", "wheat futures"), "ZS=F": ("precio de la soja", "soybean futures"),
    "KC=F": ("precio del café", "coffee futures"), "SB=F": ("precio del azúcar", "sugar futures"),
}


def google_news_query(ticker: str, name: str, edition: str = "es") -> str:
    from .catalog import asset_class

    cls = asset_class(ticker)
    if ticker in _COMMODITY_TERMS:
        es, en = _COMMODITY_TERMS[ticker]
        return f'"{es if edition == "es" else en}"'
    if cls == "Materias primas":
        return f'"{name}" precio' if edition == "es" else f'"{name}" price'
    if cls == "Criptomonedas":
        return f'"{name}"'
    if cls in ("Acciones", "ETF"):
        return f'"{name}" OR {ticker.split(".")[0]} ' + ("acciones" if edition == "es" else "stock")
    return f'"{name}"'


def google_news(ticker: str, name: str, edition: str = "es", limit: int = 15, timeout: float = 10) -> list[NewsItem]:
    params = {"q": google_news_query(ticker, name, edition) + " when:7d", **_GOOGLE_EDITIONS[edition]}
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (asistente-inversion)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        items = parse_rss(resp.read().decode("utf-8", "replace"), ticker, f"Google News ({edition})")
    return items[:limit]


# ------------------------------------------------------------------ varias fuentes a la vez
NEWS_SOURCES = {
    "yahoo": "Yahoo Finance",
    "google_es": "Google News (español)",
    "google_en": "Google News (inglés)",
    "etoro": "eToro (feed de noticias)",
}


def _norm_title(t: str) -> set[str]:
    import re
    import unicodedata

    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return {w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 2}


def dedupe(items: list[NewsItem], threshold: float = 0.7) -> list[NewsItem]:
    """Quita titulares repetidos entre fuentes (misma noticia en Yahoo y Google, por ejemplo)."""
    kept: list[tuple[set[str], NewsItem]] = []
    for it in sorted(items, key=lambda i: i.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        words = _norm_title(it.title)
        dup = None
        for w, k in kept:
            if words and w and len(words & w) / len(words | w) >= threshold:
                dup = k
                break
        if dup is None:
            kept.append((words, it))
        elif it.via and it.via not in dup.via:
            dup.via = f"{dup.via}, {it.via}"
    return [k for _, k in kept]


def mentions(item: NewsItem, ticker: str, name: str) -> bool:
    if item.tags:  # publicaciones de eToro: etiquetas exactas de los activos
        return to_etoro_symbol(ticker).upper() in item.tags or ticker.upper() in item.tags
    text = f" {item.title} {item.summary} ".lower()
    base = ticker.split(".")[0].split("=")[0].split("-")[0].lower()
    return name.lower() in text or (len(base) >= 3 and f" {base} " in text) or f"${base}" in text


def aggregate_news(ticker: str, name: str, sources: list[str] | None = None, limit: int = 25, etoro_client: EToroClient | None = None,
                   etoro_general: list[NewsItem] | None = None, errors: list[str] | None = None) -> list[NewsItem]:
    """Titulares de varias fuentes, sin duplicados y ordenados por fecha. Una fuente que falla no detiene al resto."""
    sources = sources or list(NEWS_SOURCES)
    collected: list[NewsItem] = []

    def safe(label, fn):
        try:
            collected.extend(fn())
        except Exception as exc:  # red, límites, formato cambiado...
            if errors is not None:
                errors.append(f"{label}: {type(exc).__name__}")

    if "yahoo" in sources:
        safe("Yahoo Finance", lambda: yahoo_news(ticker, 15))
    if "google_es" in sources:
        safe("Google News (es)", lambda: google_news(ticker, name, "es"))
    if "google_en" in sources:
        safe("Google News (en)", lambda: google_news(ticker, name, "en"))
    if "etoro" in sources and (etoro_client or EToroClient.configured()):
        def etoro_items():
            general = etoro_general if etoro_general is not None else (etoro_client or EToroClient()).news()
            return [NewsItem(n.title, n.summary, n.url, n.source, n.published, ticker, n.via, n.tags) for n in general if mentions(n, ticker, name)]

        safe("eToro", etoro_items)
    return dedupe(collected)[:limit]
