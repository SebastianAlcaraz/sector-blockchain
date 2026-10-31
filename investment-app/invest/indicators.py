"""Indicadores técnicos clásicos calculados con pandas puro."""

import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    """Media móvil simple."""
    return close.rolling(window, min_periods=window).mean()


def ema(close: pd.Series, span: int) -> pd.Series:
    """Media móvil exponencial."""
    return close.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Índice de fuerza relativa (RSI) con el suavizado de Wilder. Rango 0-100."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    out = 100 - 100 / (1 + rs)
    # Sin pérdidas en el periodo -> RSI = 100; sin movimiento -> 50.
    out = out.where(avg_loss != 0, 100.0)
    out = out.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)
    return out.where(avg_gain.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD: línea, señal e histograma."""
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def bollinger(close: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """Bandas de Bollinger."""
    mid = sma(close, window)
    std = close.rolling(window, min_periods=window).std()
    return pd.DataFrame({"mid": mid, "upper": mid + num_std * std, "lower": mid - num_std * std})
