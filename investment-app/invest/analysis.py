"""Métricas de rentabilidad/riesgo y una lectura técnica orientativa."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .indicators import macd, rsi, sma

TRADING_DAYS = 252


def daily_returns(close: pd.Series) -> pd.Series:
    return close.pct_change().dropna()


def total_return(close: pd.Series) -> float:
    close = close.dropna()
    if len(close) < 2:
        return float("nan")
    return float(close.iloc[-1] / close.iloc[0] - 1)


def cagr(close: pd.Series) -> float:
    """Rentabilidad anual compuesta, usando las fechas reales del índice."""
    close = close.dropna()
    if len(close) < 2:
        return float("nan")
    years = (close.index[-1] - close.index[0]).days / 365.25
    if years <= 0:
        return float("nan")
    return float((close.iloc[-1] / close.iloc[0]) ** (1 / years) - 1)


def annual_volatility(close: pd.Series, periods: int = TRADING_DAYS) -> float:
    r = daily_returns(close)
    return float(r.std() * np.sqrt(periods)) if len(r) > 1 else float("nan")


def sharpe_ratio(close: pd.Series, risk_free: float = 0.0, periods: int = TRADING_DAYS) -> float:
    """Ratio de Sharpe anualizado. risk_free es la tasa anual libre de riesgo (p. ej. 0.04)."""
    r = daily_returns(close)
    if len(r) < 2 or r.std() == 0:
        return float("nan")
    excess = r - risk_free / periods
    return float(excess.mean() / r.std() * np.sqrt(periods))


def drawdown(close: pd.Series) -> pd.Series:
    """Caída porcentual desde el máximo previo (valores <= 0)."""
    close = close.dropna()
    return close / close.cummax() - 1


def max_drawdown(close: pd.Series) -> float:
    dd = drawdown(close)
    return float(dd.min()) if len(dd) else float("nan")


def summary(close: pd.Series, risk_free: float = 0.0) -> dict[str, float]:
    return {
        "Rentabilidad total": total_return(close),
        "Rentabilidad anual (CAGR)": cagr(close),
        "Volatilidad anual": annual_volatility(close),
        "Sharpe": sharpe_ratio(close, risk_free),
        "Máxima caída": max_drawdown(close),
    }


def correlation_matrix(closes: pd.DataFrame) -> pd.DataFrame:
    """Correlación de rentabilidades diarias entre activos."""
    return closes.pct_change().dropna(how="all").corr()


@dataclass
class Outlook:
    """Lectura técnica: puntuación de -100 (muy bajista) a +100 (muy alcista)."""

    score: int
    verdict: str
    reasons: list[str] = field(default_factory=list)


def technical_outlook(close: pd.Series) -> Outlook:
    """Combina tendencia (medias móviles), momento (MACD) y RSI en una puntuación.

    Es una heurística educativa, no una recomendación de inversión.
    """
    close = close.dropna()
    reasons: list[str] = []
    points = 0.0
    weight = 0.0
    price = close.iloc[-1]

    s50 = sma(close, 50).iloc[-1] if len(close) >= 50 else np.nan
    s200 = sma(close, 200).iloc[-1] if len(close) >= 200 else np.nan

    if not np.isnan(s50):
        weight += 1
        if price > s50:
            points += 1
            reasons.append(f"El precio está por encima de su media de 50 sesiones ({s50:,.2f}): tendencia de corto plazo al alza.")
        else:
            points -= 1
            reasons.append(f"El precio está por debajo de su media de 50 sesiones ({s50:,.2f}): tendencia de corto plazo a la baja.")
    if not np.isnan(s200):
        weight += 1
        if price > s200:
            points += 1
            reasons.append(f"Por encima de la media de 200 sesiones ({s200:,.2f}): tendencia de largo plazo alcista.")
        else:
            points -= 1
            reasons.append(f"Por debajo de la media de 200 sesiones ({s200:,.2f}): tendencia de largo plazo bajista.")
        if not np.isnan(s50):
            weight += 0.5
            if s50 > s200:
                points += 0.5
                reasons.append("La media de 50 está sobre la de 200 (configuración de 'cruce dorado').")
            else:
                points -= 0.5
                reasons.append("La media de 50 está bajo la de 200 (configuración de 'cruce de la muerte').")

    if len(close) >= 35:
        m = macd(close).iloc[-1]
        weight += 1
        if m["hist"] > 0:
            points += 1
            reasons.append("MACD por encima de su señal: el impulso es positivo.")
        else:
            points -= 1
            reasons.append("MACD por debajo de su señal: el impulso es negativo.")

    r = rsi(close).iloc[-1] if len(close) > 15 else np.nan
    if not np.isnan(r):
        weight += 1
        if r >= 70:
            points -= 1
            reasons.append(f"RSI en {r:.0f}: zona de sobrecompra, posible corrección.")
        elif r <= 30:
            points += 1
            reasons.append(f"RSI en {r:.0f}: zona de sobreventa, posible rebote.")
        else:
            reasons.append(f"RSI en {r:.0f}: zona neutral.")

    if weight == 0:
        return Outlook(0, "Datos insuficientes", ["Se necesitan más sesiones de historial."])

    score = int(round(100 * points / weight))
    if score >= 50:
        verdict = "Alcista"
    elif score >= 15:
        verdict = "Moderadamente alcista"
    elif score > -15:
        verdict = "Neutral"
    elif score > -50:
        verdict = "Moderadamente bajista"
    else:
        verdict = "Bajista"
    return Outlook(score, verdict, reasons)
