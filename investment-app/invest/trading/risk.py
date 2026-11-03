"""Control de riesgo: reglas fijas que revisan cada propuesta. La IA no puede saltárselas."""

from __future__ import annotations

from dataclasses import dataclass, field

from .advisor import Decision
from .broker import Position
from .config import BotConfig


@dataclass
class RiskContext:
    equity: float
    cash: float
    positions: dict[str, Position]
    prices: dict[str, float]
    trades_today: int = 0
    pending_buys: float = 0.0  # importe de compras ya propuestas y sin decidir
    pending_count: int = 0
    equity_day_start: float | None = None
    equity_week_start: float | None = None
    paused: bool = False


@dataclass
class Verdict:
    ok: bool
    amount: float = 0.0  # compras
    units: float = 0.0  # ventas
    notes: list[str] = field(default_factory=list)


def loss_pct(current: float, start: float | None) -> float:
    if not start:
        return 0.0
    return (current / start - 1) * 100


def buying_blocked(ctx: RiskContext, cfg: BotConfig) -> str | None:
    """Motivo por el que hoy no se puede comprar, o None."""
    if ctx.paused:
        return "El bot está detenido."
    day = loss_pct(ctx.equity, ctx.equity_day_start)
    if day <= -cfg.max_perdida_diaria_pct:
        return f"Pérdida de hoy {day:.1f} %: se alcanzó el límite diario ({cfg.max_perdida_diaria_pct} %)."
    week = loss_pct(ctx.equity, ctx.equity_week_start)
    if week <= -cfg.max_perdida_semanal_pct:
        return f"Pérdida de la semana {week:.1f} %: se alcanzó el límite semanal ({cfg.max_perdida_semanal_pct} %)."
    if ctx.trades_today + ctx.pending_count >= cfg.max_operaciones_dia:
        return f"Ya hay {ctx.trades_today + ctx.pending_count} operaciones hoy (máximo {cfg.max_operaciones_dia})."
    return None


def check_buy(d: Decision, ctx: RiskContext, cfg: BotConfig, allowed: set[str] | None = None) -> Verdict:
    notes: list[str] = []
    if d.ticker not in (allowed if allowed is not None else set(cfg.lista_activos)):
        return Verdict(False, notes=[f"{d.ticker} no está en tu lista de activos permitidos."])
    blocked = buying_blocked(ctx, cfg)
    if blocked:
        return Verdict(False, notes=[blocked])
    if d.confianza < cfg.confianza_minima:
        return Verdict(False, notes=[f"Confianza {d.confianza:.2f} por debajo del mínimo ({cfg.confianza_minima:.2f})."])
    price = ctx.prices.get(d.ticker)
    if not price:
        return Verdict(False, notes=["No hay precio actual."])

    wanted = d.importe_pct / 100 * ctx.equity
    amount = min(wanted, cfg.max_operacion_pct / 100 * ctx.equity)
    if amount < wanted - 1e-6:
        notes.append(f"Importe reducido al máximo por operación ({cfg.max_operacion_pct} % de la cartera).")

    pos = ctx.positions.get(d.ticker)
    current_value = pos.units * price if pos else 0.0
    room = cfg.max_posicion_pct / 100 * ctx.equity - current_value
    if amount > room:
        amount = max(room, 0.0)
        notes.append(f"Importe reducido para no superar el {cfg.max_posicion_pct} % en un solo activo.")

    spendable = ctx.cash - ctx.pending_buys - cfg.min_liquidez_pct / 100 * ctx.equity
    if amount > spendable:
        amount = max(spendable, 0.0)
        notes.append(f"Importe reducido para conservar al menos un {cfg.min_liquidez_pct} % en efectivo.")

    if amount < cfg.importe_minimo:
        return Verdict(False, notes=notes + [f"El importe resultante ({amount:,.2f}) es menor que el mínimo ({cfg.importe_minimo:,.2f})."])
    notes.append(f"Stop-loss al {cfg.stop_loss_pct} % por debajo del precio de compra.")
    return Verdict(True, amount=round(amount, 2), notes=notes)


def check_sell(d: Decision, ctx: RiskContext, cfg: BotConfig, full_only: bool = False) -> Verdict:
    pos = ctx.positions.get(d.ticker)
    if not pos or pos.units <= 0:
        return Verdict(False, notes=[f"No tienes {d.ticker} en cartera."])
    if ctx.paused:
        return Verdict(False, notes=["El bot está detenido."])
    fraction = 1.0 if full_only else min(max(d.fraccion_venta, 0.0), 1.0)
    if fraction <= 0:
        return Verdict(False, notes=["Fracción de venta nula."])
    notes = []
    if full_only and d.fraccion_venta < 1:
        notes.append("eToro cierra posiciones completas: se venderá toda la posición.")
    units = pos.units * fraction
    price = ctx.prices.get(d.ticker, pos.avg_price)
    if units * price < cfg.importe_minimo and fraction < 1:
        units = pos.units
        notes.append("La venta parcial era muy pequeña: se propone vender toda la posición.")
    return Verdict(True, units=units, notes=notes)


def stop_loss_hits(positions: dict[str, Position], prices: dict[str, float]) -> list[str]:
    return [t for t, p in positions.items() if p.stop_price and t in prices and prices[t] <= p.stop_price]
