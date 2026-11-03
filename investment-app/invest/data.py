"""Fuentes de cotizaciones.

- YahooSource: datos reales de Yahoo Finance (gratuito, sin clave de API).
- DemoSource: precios simulados y reproducibles, para usar la app sin conexión.
"""

import zlib

import numpy as np
import pandas as pd

PERIOD_DAYS = {"1mo": 31, "3mo": 92, "6mo": 183, "1y": 365, "2y": 730, "5y": 1826, "10y": 3652}


class YahooSource:
    name = "Yahoo Finance"

    def closes(self, tickers: list[str], period: str = "2y") -> pd.DataFrame:
        """Cierres ajustados, una columna por símbolo."""
        import yfinance as yf

        tickers = list(dict.fromkeys(t for t in tickers if t))
        if not tickers:
            return pd.DataFrame()
        raw = yf.download(tickers, period=period, auto_adjust=True, progress=False, threads=True)
        if raw is None or raw.empty:
            return pd.DataFrame()
        if isinstance(raw.columns, pd.MultiIndex):
            out = raw["Close"]
        else:
            out = raw[["Close"]].rename(columns={"Close": tickers[0]})
        if isinstance(out, pd.Series):
            out = out.to_frame(tickers[0])
        out = out.reindex(columns=[t for t in tickers if t in out.columns])
        out.index = pd.to_datetime(out.index).tz_localize(None)
        # Los mercados tienen calendarios distintos (cripto cotiza a diario): rellenamos huecos hacia delante.
        return out.ffill().dropna(how="all").dropna(axis=1, how="all")


class DemoSource:
    """Paseo aleatorio geométrico con parámetros según la clase de activo."""

    name = "Datos simulados (demo)"

    _PARAMS = {  # (rentabilidad anual esperada, volatilidad anual, precio inicial aproximado)
        "Acciones": (0.10, 0.30, 150.0),
        "ETF": (0.08, 0.17, 300.0),
        "Materias primas": (0.04, 0.28, 80.0),
        "Criptomonedas": (0.25, 0.70, 20000.0),
        "Índices": (0.08, 0.18, 5000.0),
        "Divisas": (0.00, 0.08, 1.1),
    }

    def closes(self, tickers: list[str], period: str = "2y") -> pd.DataFrame:
        from .catalog import asset_class

        tickers = list(dict.fromkeys(t for t in tickers if t))
        if not tickers:
            return pd.DataFrame()
        end = pd.Timestamp.today().normalize()
        # Se genera siempre la serie completa y se recorta: así el último precio no depende del periodo pedido.
        idx = pd.bdate_range(end=end, periods=int(PERIOD_DAYS["10y"] * 252 / 365))
        keep = max(int(PERIOD_DAYS.get(period, 730) * 252 / 365), 2)
        # Factor de mercado común para que haya correlaciones realistas.
        market = np.random.default_rng(12345).normal(0, 1, len(idx))
        out = {}
        for t in tickers:
            mu, sigma, p0 = self._PARAMS[asset_class(t)]
            rng = np.random.default_rng(zlib.crc32(t.encode()))
            beta = 0.6 if asset_class(t) in ("Acciones", "ETF", "Índices") else 0.2
            shocks = beta * market + np.sqrt(1 - beta**2) * rng.normal(0, 1, len(idx))
            dt = 1 / 252
            log_ret = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * shocks
            start = p0 * rng.uniform(0.3, 1.7)
            out[t] = start * np.exp(np.cumsum(log_ret))
        return pd.DataFrame(out, index=idx).iloc[-keep:]


class EToroSource:
    """Precios de eToro: velas diarias + último precio. Necesita ETORO_API_KEY y ETORO_USER_KEY.

    Sin probar con una cuenta real (rutas según la documentación pública de eToro).
    """

    name = "eToro"

    def __init__(self, client=None):
        from .news import EToroClient

        self.client = client or EToroClient()
        self.missing: list[str] = []  # activos que eToro no devolvió en la última llamada

    def closes(self, tickers: list[str], period: str = "2y") -> pd.DataFrame:
        from .news import EToroError

        tickers = list(dict.fromkeys(t for t in tickers if t))
        count = max(int(PERIOD_DAYS.get(period, 730) * 252 / 365) + 5, 30)  # eToro admite hasta 1000 velas
        series, ids, self.missing = {}, {}, []
        for t in tickers:
            try:
                found = self.client.find_instrument(t)
                if not found:
                    self.missing.append(t)
                    continue
                s = self.client.candles(found["instrumentId"], count)
                if s.empty:
                    self.missing.append(t)
                    continue
                series[t], ids[t] = s, found["instrumentId"]
            except EToroError:
                self.missing.append(t)
        if not series:
            return pd.DataFrame()
        out = pd.DataFrame(series).sort_index()
        # Precio del momento: se añade (o actualiza) la fila de hoy con la última cotización.
        try:
            live = self.client.rates(list(ids.values()))
        except EToroError:
            live = {}
        today = pd.Timestamp.today().normalize()
        for t, iid in ids.items():
            if iid in live:
                out.loc[today, t] = live[iid]
        return out.sort_index().ffill().dropna(how="all")


class FallbackSource:
    """Usa la fuente principal y completa con la de respaldo los activos que falten."""

    def __init__(self, primary, backup):
        self.primary, self.backup = primary, backup
        self.name = f"{primary.name} (respaldo: {backup.name})"
        self.used_backup: list[str] = []

    def closes(self, tickers: list[str], period: str = "2y") -> pd.DataFrame:
        try:
            main = self.primary.closes(tickers, period)
        except Exception:
            main = pd.DataFrame()
        missing = [t for t in tickers if t not in main.columns]
        self.used_backup = missing
        if not missing:
            return main
        extra = self.backup.closes(missing, period)
        if main.empty:
            return extra
        if extra.empty:
            return main
        return main.join(extra, how="outer").sort_index().ffill()


def make_source(name: str):
    """'etoro' (con Yahoo de respaldo), 'yahoo' o 'demo'."""
    from .news import EToroClient

    if name == "demo":
        return DemoSource()
    if name == "etoro" and EToroClient.configured():
        return FallbackSource(EToroSource(), YahooSource())
    return YahooSource()


def last_prices(source, tickers: list[str]) -> dict[str, float]:
    """Último precio disponible de cada símbolo."""
    df = source.closes(tickers, period="1mo")
    if df.empty:
        return {}
    last = df.ffill().iloc[-1]
    return {t: float(v) for t, v in last.items() if pd.notna(v)}
