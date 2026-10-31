"""Prueba histórica (backtest) de unos parámetros de estrategia, con división en dos tramos:
- dentro de muestra: datos con los que se puede ajustar la estrategia;
- fuera de muestra: datos más recientes que el ajuste no ve, para comprobar que no es casualidad.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .config import BotConfig
from .strategy import StrategyParams, score_series


@dataclass
class BacktestResult:
    rentabilidad: float
    referencia: float  # comprar y mantener el índice de referencia en el mismo tramo
    max_caida: float
    sharpe: float
    operaciones: int
    aciertos: float  # % de ventas con ganancia
    curva: pd.Series | None = None

    def metrics(self) -> dict:
        d = asdict(self)
        d.pop("curva")
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}


def run(closes: pd.DataFrame, params: StrategyParams, cfg: BotConfig, start=None, end=None, rebalance_days: int = 5, scores: dict | None = None) -> BacktestResult:
    """Simula la estrategia sobre `closes` (una columna por activo, incluida la referencia)."""
    tickers = [t for t in cfg.lista_activos if t in closes]
    scores = scores or {t: score_series(closes[t], params) for t in tickers}
    idx = closes.index
    if start is not None:
        idx = idx[idx >= start]
    if end is not None:
        idx = idx[idx <= end]
    spread = cfg.diferencial_pct / 100
    cash, pos = 1.0, {}  # pos: ticker -> [unidades, precio_entrada, día_entrada, stop]
    curve, trades, wins = [], 0, 0
    for n, day in enumerate(idx):
        prices = closes.loc[day]
        # stop-loss diario
        for t in list(pos):
            u, entry, d0, stop = pos[t]
            if prices[t] <= stop:
                cash += u * prices[t] * (1 - spread / 2)
                wins += prices[t] > entry
                trades += 1
                del pos[t]
        if n % rebalance_days == 0:
            equity = cash + sum(u * prices[t] for t, (u, *_) in pos.items())
            for t in tickers:
                sc = scores[t].get(day, np.nan)
                if np.isnan(sc) or np.isnan(prices[t]):
                    continue
                if t in pos:
                    u, entry, d0, stop = pos[t]
                    if sc <= params.umbral_venta and (day - d0).days >= params.dias_minimos:
                        cash += u * prices[t] * (1 - spread / 2)
                        wins += prices[t] > entry
                        trades += 1
                        del pos[t]
                elif sc >= params.umbral_compra:
                    amount = min(params.tamano_pct, cfg.max_operacion_pct) / 100 * equity
                    amount = min(amount, cash - cfg.min_liquidez_pct / 100 * equity)
                    if amount > 0.001 * equity:
                        fill = prices[t] * (1 + spread / 2)
                        pos[t] = [amount / fill, fill, day, fill * (1 - cfg.stop_loss_pct / 100)]
                        cash -= amount
        curve.append(cash + sum(u * prices[t] for t, (u, *_) in pos.items()))
    curve = pd.Series(curve, index=idx)
    if len(curve) < 2:
        return BacktestResult(0.0, 0.0, 0.0, 0.0, 0, 0.0, curve)
    ret = curve.pct_change().dropna()
    ref = closes.loc[idx, cfg.referencia] if cfg.referencia in closes else None
    return BacktestResult(
        rentabilidad=float(curve.iloc[-1] / curve.iloc[0] - 1),
        referencia=float(ref.iloc[-1] / ref.iloc[0] - 1) if ref is not None else 0.0,
        max_caida=float((curve / curve.cummax() - 1).min()),
        sharpe=float(ret.mean() / ret.std() * np.sqrt(252)) if ret.std() > 0 else 0.0,
        operaciones=trades,
        aciertos=wins / trades if trades else 0.0,
        curva=curve,
    )


def split_point(closes: pd.DataFrame, warmup: int = 200, in_sample: float = 0.7):
    usable = closes.index[warmup:]
    if len(usable) < 60:
        raise ValueError("Hace falta más historial para probar la estrategia.")
    return usable[0], usable[int(len(usable) * in_sample)]


def evaluate(closes: pd.DataFrame, params: StrategyParams, cfg: BotConfig) -> dict:
    """Métricas dentro y fuera de muestra."""
    start, cut = split_point(closes)
    tickers = [t for t in cfg.lista_activos if t in closes]
    scores = {t: score_series(closes[t], params) for t in tickers}
    ins = run(closes, params, cfg, start=start, end=cut, scores=scores)
    oos = run(closes, params, cfg, start=cut, scores=scores)
    return {"dentro": ins.metrics(), "fuera": oos.metrics(), "corte": str(cut.date()), "curva_fuera": oos.curva}


def compare(current: dict, candidate: dict, min_trades: int = 3) -> tuple[bool, list[str]]:
    """¿La candidata mejora a la actual en los datos que no vio? Devuelve (recomendada, motivos)."""
    c, n = current["fuera"], candidate["fuera"]
    reasons, ok = [], True
    diff = n["rentabilidad"] - c["rentabilidad"]
    if diff >= 0:
        reasons.append(f"Fuera de muestra gana {diff * 100:+.1f} puntos frente a la actual.")
    else:
        ok = False
        reasons.append(f"Fuera de muestra rinde {diff * 100:+.1f} puntos peor que la actual.")
    if n["max_caida"] < c["max_caida"] - 0.02:
        ok = False
        reasons.append(f"Su peor caída es mayor ({n['max_caida'] * 100:.1f} % frente a {c['max_caida'] * 100:.1f} %).")
    if n["operaciones"] < min_trades:
        ok = False
        reasons.append(f"Solo {n['operaciones']} operaciones fuera de muestra: muy pocas para fiarse.")
    if candidate["dentro"]["rentabilidad"] - current["dentro"]["rentabilidad"] > 0.15 and diff < 0.02:
        reasons.append("Mejora mucho en los datos de ajuste pero poco en los nuevos: posible sobreajuste.")
    return ok, reasons
