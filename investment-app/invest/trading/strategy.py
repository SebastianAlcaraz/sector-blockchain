"""Estrategia del bot: una parte numérica (parámetros que se pueden probar con datos históricos)
y un manual en texto (principios que la IA sigue al analizar). Ambas evolucionan con el aprendizaje.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields

import numpy as np
import pandas as pd

from ..indicators import macd, rsi, sma


@dataclass
class StrategyParams:
    peso_tendencia: float = 1.0  # precio frente a medias de 50 y 200 sesiones
    peso_impulso: float = 1.0  # histograma MACD
    peso_rsi: float = 0.5  # sobreventa suma, sobrecompra resta
    peso_rendimiento_3m: float = 0.5  # impulso de 3 meses
    peso_sentimiento: float = 0.5  # noticias (no existe en el histórico: no cuenta en las pruebas)
    umbral_compra: float = 0.45
    umbral_venta: float = -0.3
    rsi_sobrecompra: float = 70.0
    rsi_sobreventa: float = 30.0
    tamano_pct: float = 5.0  # % de la cartera por compra (el control de riesgo puede reducirlo)
    dias_minimos: int = 5  # días mínimos en cartera antes de vender por señal (el stop-loss no espera)

    def clamp(self) -> "StrategyParams":
        out = {}
        for f in fields(self):
            lo, hi = BOUNDS[f.name]
            v = min(max(float(getattr(self, f.name)), lo), hi)
            out[f.name] = int(round(v)) if f.type in (int, "int") else round(v, 3)
        if out["umbral_venta"] >= out["umbral_compra"]:
            out["umbral_venta"] = round(out["umbral_compra"] - 0.2, 3)
        if out["rsi_sobreventa"] >= out["rsi_sobrecompra"] - 10:
            out["rsi_sobreventa"] = out["rsi_sobrecompra"] - 10
        return StrategyParams(**out)

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StrategyParams":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in known}).clamp()


# Rango permitido de cada parámetro: el aprendizaje nunca puede salirse de aquí.
BOUNDS: dict[str, tuple[float, float]] = {
    "peso_tendencia": (0.0, 3.0),
    "peso_impulso": (0.0, 3.0),
    "peso_rsi": (0.0, 3.0),
    "peso_rendimiento_3m": (0.0, 3.0),
    "peso_sentimiento": (0.0, 3.0),
    "umbral_compra": (0.1, 0.9),
    "umbral_venta": (-0.9, 0.2),
    "rsi_sobrecompra": (60.0, 85.0),
    "rsi_sobreventa": (15.0, 45.0),
    "tamano_pct": (1.0, 10.0),
    "dias_minimos": (1, 30),
}

DEFAULT_PLAYBOOK = """Horizonte de medio plazo (días a semanas).
1. Compra solo con tendencia alcista confirmada (precio sobre sus medias) e impulso positivo.
2. Evita comprar con RSI en sobrecompra o justo después de una subida muy fuerte.
3. Las noticias confirman o frenan una señal técnica; por sí solas no bastan.
4. Vende cuando la tendencia se rompe o las noticias cambian de forma clara a negativas, no por una caída de un día.
5. Diversifica: no acumules activos que se mueven igual."""


def _terms(trend, impulse, rsi_val, ret3m, sentiment, p: StrategyParams) -> float:
    """Combina las señales (cada una de -1 a 1) en una puntuación de -1 a 1."""
    parts = []
    if trend is not None:
        parts.append((p.peso_tendencia, trend))
    if impulse is not None:
        parts.append((p.peso_impulso, impulse))
    if rsi_val is not None:
        if rsi_val >= p.rsi_sobrecompra:
            r = -1.0
        elif rsi_val <= p.rsi_sobreventa:
            r = 1.0
        else:
            mid = (p.rsi_sobrecompra + p.rsi_sobreventa) / 2
            r = -(rsi_val - mid) / ((p.rsi_sobrecompra - p.rsi_sobreventa) / 2) * 0.5
        parts.append((p.peso_rsi, r))
    if ret3m is not None:
        parts.append((p.peso_rendimiento_3m, math.tanh(ret3m * 5)))
    if sentiment is not None:
        parts.append((p.peso_sentimiento, max(-1.0, min(1.0, sentiment * 2))))
    wsum = sum(w for w, _ in parts)
    return sum(w * v for w, v in parts) / wsum if wsum else 0.0


def score_snapshot(s, p: StrategyParams) -> float:
    """Puntuación de un AssetSnapshot con estos parámetros."""
    trend_flags = [f for f in (s.sobre_media_50, s.sobre_media_200) if f is not None]
    trend = sum(1 if f else -1 for f in trend_flags) / len(trend_flags) if trend_flags else None
    impulse = math.tanh(s.macd_hist * 200) if s.macd_hist is not None else None
    ret3m = s.var_3m if s.var_3m == s.var_3m else None  # NaN -> None
    return round(_terms(trend, impulse, s.rsi, ret3m, s.sentimiento, p), 4)


def score_series(close: pd.Series, p: StrategyParams) -> pd.Series:
    """Puntuación diaria a partir del histórico de precios (sin sentimiento: no hay noticias históricas)."""
    close = close.dropna()
    s50, s200 = sma(close, 50), sma(close, 200)
    trend = ((close > s50).astype(float) * 2 - 1 + (close > s200).astype(float) * 2 - 1) / 2
    trend[s200.isna()] = ((close > s50).astype(float) * 2 - 1)[s200.isna()]
    trend[s50.isna()] = np.nan
    impulse = np.tanh(macd(close)["hist"] / close * 200)
    r = rsi(close)
    ret3m = close.pct_change(63)
    out = []
    for i in range(len(close)):
        t = trend.iloc[i]
        out.append(_terms(
            None if np.isnan(t) else float(t),
            None if i < 35 else float(impulse.iloc[i]),
            None if np.isnan(r.iloc[i]) else float(r.iloc[i]),
            None if np.isnan(ret3m.iloc[i]) else float(ret3m.iloc[i]),
            None,
            p,
        ))
    return pd.Series(out, index=close.index)
