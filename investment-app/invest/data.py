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


def last_prices(source, tickers: list[str]) -> dict[str, float]:
    """Último precio disponible de cada símbolo."""
    df = source.closes(tickers, period="1mo")
    if df.empty:
        return {}
    last = df.ffill().iloc[-1]
    return {t: float(v) for t, v in last.items() if pd.notna(v)}
