"""Simulación histórica de estrategias de aportación."""

from dataclasses import dataclass

import pandas as pd


@dataclass
class SimResult:
    history: pd.DataFrame  # columnas: aportado, valor
    invested: float
    final_value: float

    @property
    def profit(self) -> float:
        return self.final_value - self.invested

    @property
    def profit_pct(self) -> float:
        return self.profit / self.invested if self.invested else float("nan")


def _first_trading_day_each_month(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    s = pd.Series(index, index=index)
    return pd.DatetimeIndex(s.groupby([index.year, index.month]).first().values)


def dca(close: pd.Series, monthly_amount: float, initial: float = 0.0) -> SimResult:
    """Promedio del coste en dólares: compra `monthly_amount` el primer día hábil de cada mes."""
    close = close.dropna()
    buy_days = set(_first_trading_day_each_month(close.index))
    units = 0.0
    invested = 0.0
    rows = []
    for i, (day, price) in enumerate(close.items()):
        amount = 0.0
        if i == 0 and initial:
            amount += initial
        if day in buy_days:
            amount += monthly_amount
        if amount:
            units += amount / price
            invested += amount
        rows.append((day, invested, units * price))
    hist = pd.DataFrame(rows, columns=["fecha", "aportado", "valor"]).set_index("fecha")
    return SimResult(hist, invested, float(hist["valor"].iloc[-1]) if len(hist) else 0.0)


def lump_sum(close: pd.Series, amount: float) -> SimResult:
    """Invierte todo el importe el primer día."""
    close = close.dropna()
    units = amount / close.iloc[0]
    hist = pd.DataFrame({"aportado": amount, "valor": units * close})
    hist.index.name = "fecha"
    return SimResult(hist, amount, float(hist["valor"].iloc[-1]))
