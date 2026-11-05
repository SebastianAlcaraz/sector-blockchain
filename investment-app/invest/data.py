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

    def _field(self, raw: pd.DataFrame, field: str, tickers: list[str]) -> pd.DataFrame:
        if isinstance(raw.columns, pd.MultiIndex):
            out = raw[field]
        else:
            out = raw[[field]].rename(columns={field: tickers[0]})
        if isinstance(out, pd.Series):
            out = out.to_frame(tickers[0])
        out = out.reindex(columns=[t for t in tickers if t in out.columns])
        out.index = pd.to_datetime(out.index).tz_localize(None)
        return out

    def _download(self, tickers: list[str], period: str):
        import yfinance as yf

        raw = yf.download(tickers, period=period, auto_adjust=True, progress=False, threads=True)
        return None if raw is None or raw.empty else raw

    def closes(self, tickers: list[str], period: str = "2y") -> pd.DataFrame:
        """Cierres ajustados, una columna por símbolo."""
        tickers = list(dict.fromkeys(t for t in tickers if t))
        raw = self._download(tickers, period) if tickers else None
        if raw is None:
            return pd.DataFrame()
        out = self._field(raw, "Close", tickers)
        # Los mercados tienen calendarios distintos (cripto cotiza a diario): rellenamos huecos hacia delante.
        return out.ffill().dropna(how="all").dropna(axis=1, how="all")

    def ohlc(self, tickers: list[str], period: str = "6mo") -> dict[str, pd.DataFrame]:
        """Velas diarias (máximo, mínimo y cierre ajustados) de cada símbolo."""
        tickers = list(dict.fromkeys(t for t in tickers if t))
        raw = self._download(tickers, period) if tickers else None
        if raw is None:
            return {}
        fields = {k: self._field(raw, k.capitalize(), tickers) for k in ("high", "low", "close")}
        out = {}
        for t in tickers:
            if t in fields["close"]:
                df = pd.DataFrame({k: v[t] for k, v in fields.items()}).dropna()
                if not df.empty:
                    out[t] = df
        return out


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

    def ohlc(self, tickers: list[str], period: str = "6mo") -> dict[str, pd.DataFrame]:
        """Máximos y mínimos simulados alrededor de los cierres (reproducibles)."""
        from .catalog import asset_class

        closes = self.closes(tickers, period)
        out = {}
        for t in closes:
            c = closes[t]
            sigma = self._PARAMS[asset_class(t)][1] / np.sqrt(252)
            rng = np.random.default_rng(zlib.crc32(("ohlc" + t).encode()))
            top = pd.concat([c, c.shift(1)], axis=1).max(axis=1)
            bottom = pd.concat([c, c.shift(1)], axis=1).min(axis=1)
            out[t] = pd.DataFrame({
                "high": top * (1 + np.abs(rng.normal(0, sigma * 0.5, len(c)))),
                "low": bottom * (1 - np.abs(rng.normal(0, sigma * 0.5, len(c)))),
                "close": c,
            })
        return out


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

    def ohlc(self, tickers: list[str], period: str = "6mo") -> dict[str, pd.DataFrame]:
        from .news import EToroError

        count = max(int(PERIOD_DAYS.get(period, 183) * 252 / 365) + 5, 30)
        out = {}
        for t in dict.fromkeys(t for t in tickers if t):
            try:
                found = self.client.find_instrument(t)
                df = self.client.candles_ohlc(found["instrumentId"], count) if found else None
            except EToroError:
                df = None
            if df is not None and not df.empty:
                out[t] = df
        return out


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

    def ohlc(self, tickers: list[str], period: str = "6mo") -> dict[str, pd.DataFrame]:
        try:
            out = dict(self.primary.ohlc(tickers, period))
        except Exception:
            out = {}
        missing = [t for t in tickers if t not in out]
        if missing:
            out.update(self.backup.ohlc(missing, period))
        return out


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
