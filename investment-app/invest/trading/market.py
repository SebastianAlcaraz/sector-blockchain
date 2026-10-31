"""Estudio de mercado: resume cada activo en datos que el asesor (IA o reglas) puede valorar."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from .. import analysis
from ..catalog import all_assets, asset_class
from ..indicators import macd, rsi, sma


@dataclass
class AssetSnapshot:
    ticker: str
    nombre: str
    clase: str
    precio: float
    var_1s: float
    var_1m: float
    var_3m: float
    var_1a: float
    sobre_media_50: bool | None
    sobre_media_200: bool | None
    rsi: float | None
    macd_hist: float | None
    volatilidad_anual: float
    caida_desde_max: float
    lectura_tecnica: int
    veredicto_tecnico: str
    sentimiento: float | None = None
    sentimiento_veredicto: str = "Sin datos"
    titulares: list[str] = field(default_factory=list)
    en_cartera_unidades: float = 0.0
    en_cartera_peso: float = 0.0
    en_cartera_ganancia: float | None = None
    dias_en_cartera: int | None = None
    puntuacion_estrategia: float | None = None

    def as_dict(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, float):
                d[k] = round(v, 4)
        return d


def _change(s: pd.Series, days: int) -> float:
    past = s[s.index <= s.index[-1] - pd.Timedelta(days=days)]
    return float(s.iloc[-1] / past.iloc[-1] - 1) if len(past) else float("nan")


def snapshot(ticker: str, close: pd.Series) -> AssetSnapshot:
    close = close.dropna()
    look = analysis.technical_outlook(close)
    s50 = sma(close, 50).iloc[-1] if len(close) >= 50 else np.nan
    s200 = sma(close, 200).iloc[-1] if len(close) >= 200 else np.nan
    r = rsi(close).iloc[-1] if len(close) > 15 else np.nan
    m = macd(close)["hist"].iloc[-1] if len(close) >= 35 else np.nan
    price = float(close.iloc[-1])
    return AssetSnapshot(
        ticker=ticker,
        nombre=all_assets().get(ticker, ticker),
        clase=asset_class(ticker),
        precio=price,
        var_1s=_change(close, 7),
        var_1m=_change(close, 30),
        var_3m=_change(close, 91),
        var_1a=_change(close, 365),
        sobre_media_50=None if np.isnan(s50) else bool(price > s50),
        sobre_media_200=None if np.isnan(s200) else bool(price > s200),
        rsi=None if np.isnan(r) else float(r),
        macd_hist=None if np.isnan(m) else float(m / price),  # normalizado por el precio
        volatilidad_anual=analysis.annual_volatility(close),
        caida_desde_max=float(analysis.drawdown(close).iloc[-1]),
        lectura_tecnica=look.score,
        veredicto_tecnico=look.verdict,
    )
