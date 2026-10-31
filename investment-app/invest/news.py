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
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class NewsItem:
    title: str
    summary: str = ""
    url: str = ""
    source: str = ""
    published: datetime | None = None
    ticker: str = ""

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
    return NewsItem(title, summary, url, source, published, ticker)


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
        out.append(NewsItem(title, "", "", "Noticia simulada", now - timedelta(hours=rng.uniform(1, 24 * 7)), ticker))
    out.sort(key=lambda i: i.published, reverse=True)
    return out


# ------------------------------------------------------------------ eToro (experimental)
class EToroError(RuntimeError):
    pass


class EToroClient:
    """Cliente mínimo de la API pública de eToro.

    EXPERIMENTAL: las rutas y el formato de las respuestas proceden de la documentación pública
    de eToro y no se han podido probar con una cuenta real. Si algo falla, revisa
    https://api-portal.etoro.com y ajusta las rutas de abajo.

    Configura las claves como variables de entorno (nunca en el código):
      ETORO_API_KEY   clave de la aplicación
      ETORO_USER_KEY  clave de usuario
    """

    BASE = "https://public-api.etoro.com/api/v1"
    NEWS_PATH = "/feeds/news"
    INSTRUMENT_FEED_PATH = "/feeds/instrument/{instrument_id}"
    SEARCH_PATH = "/market-data/search"

    def __init__(self, api_key: str | None = None, user_key: str | None = None, timeout: float = 15):
        self.api_key = api_key or os.environ.get("ETORO_API_KEY", "")
        self.user_key = user_key or os.environ.get("ETORO_USER_KEY", "")
        self.timeout = timeout

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
            for key in ("items", "posts", "data", "results", "feed", "news", "discussions"):
                if key in payload:
                    return EToroClient._items(payload[key])
        return []

    @staticmethod
    def _to_news(raw: dict, ticker: str = "") -> NewsItem | None:
        msg = raw.get("message") if isinstance(raw.get("message"), dict) else raw
        text = next((str(msg[k]).strip() for k in ("title", "text", "body", "content", "message") if isinstance(msg.get(k), str) and msg[k].strip()), "")
        if not text:
            return None
        title, _, rest = text.partition("\n")
        owner = raw.get("owner") or raw.get("author") or raw.get("user") or {}
        source = (owner.get("username") or owner.get("userName") or "") if isinstance(owner, dict) else ""
        published = _parse_time(raw.get("created") or raw.get("createdAt") or raw.get("date") or raw.get("publishedAt"))
        url = raw.get("url") or raw.get("link") or ""
        return NewsItem(title[:300], rest.strip()[:500], url, source or "eToro", published, ticker)

    def news(self, limit: int = 20) -> list[NewsItem]:
        items = self._items(self._get(self.NEWS_PATH, {"take": limit}))
        return [n for n in (self._to_news(i) for i in items) if n][:limit]

    def find_instrument_id(self, symbol: str) -> int | None:
        payload = self._get(self.SEARCH_PATH, {"internalSymbolFull": symbol, "fields": "instrumentId,internalSymbolFull,displayname"})
        for item in self._items(payload):
            sym = str(item.get("internalSymbolFull") or item.get("symbol") or "").upper()
            if sym == symbol.upper() and item.get("instrumentId") is not None:
                return int(item["instrumentId"])
        return None

    def instrument_posts(self, symbol: str, limit: int = 30) -> list[NewsItem]:
        iid = self.find_instrument_id(to_etoro_symbol(symbol))
        if iid is None:
            raise EToroError(f"eToro: no se encontró el activo {symbol}.")
        items = self._items(self._get(self.INSTRUMENT_FEED_PATH.format(instrument_id=iid), {"take": limit}))
        return [n for n in (self._to_news(i, symbol) for i in items) if n][:limit]


# Equivalencias de símbolos Yahoo -> eToro para materias primas y cripto habituales.
_ETORO_SYMBOLS = {
    "GC=F": "GOLD", "SI=F": "SILVER", "HG=F": "COPPER", "PL=F": "PLATINUM", "CL=F": "OIL",
    "BZ=F": "OILBRENT", "NG=F": "NATGAS", "BTC-USD": "BTC", "ETH-USD": "ETH", "SOL-USD": "SOL",
    "^GSPC": "SPX500", "^IXIC": "NSDQ100", "^DJI": "DJ30", "EURUSD=X": "EURUSD",
}


def to_etoro_symbol(ticker: str) -> str:
    return _ETORO_SYMBOLS.get(ticker, ticker.split(".")[0])
