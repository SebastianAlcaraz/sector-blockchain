"""Motor del bot: un ciclo de análisis y la ejecución de propuestas aprobadas."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from ..catalog import label
from ..data import DemoSource, YahooSource
from ..news import demo_news, yahoo_news
from ..sentiment import LexiconAnalyzer, aggregate
from .advisor import Advice, ClaudeAdvisor, RuleAdvisor
from .broker import BrokerError, EToroDemoBroker, PaperBroker
from .config import BotConfig
from .market import snapshot
from .risk import RiskContext, buying_blocked, check_buy, check_sell, stop_loss_hits
from .store import Store


def default_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "bot"


class Engine:
    def __init__(self, data_dir: Path | None = None, cfg: BotConfig | None = None, source=None, advisor=None, broker=None, news_fn=None):
        self.dir = Path(data_dir or default_dir())
        self.dir.mkdir(parents=True, exist_ok=True)
        self.cfg_path = self.dir / "config.json"
        self.cfg = cfg or BotConfig.load(self.cfg_path)
        self.store = Store(self.dir / "bot.sqlite")
        self._source = source
        self._advisor = advisor
        self._broker = broker
        self.news_fn = news_fn or (lambda t: demo_news(t, label(t), 8) if self.cfg.fuente_datos == "demo" else yahoo_news(t, 8))

    # ---------------------------------------------------------- piezas
    @property
    def source(self):
        if self._source is None:
            self._source = DemoSource() if self.cfg.fuente_datos == "demo" else YahooSource()
        return self._source

    @property
    def broker(self):
        if self._broker is None:
            if self.cfg.modo == "etoro_demo":
                self._broker = EToroDemoBroker()
            else:
                self._broker = PaperBroker(self.store, self.cfg.capital_inicial, self.cfg.diferencial_pct)
        return self._broker

    @property
    def advisor(self):
        if self._advisor is None:
            self._advisor = ClaudeAdvisor() if self.cfg.asesor == "claude" else RuleAdvisor()
        return self._advisor

    def prices(self, tickers: list[str], period: str = "1mo") -> tuple[dict[str, float], pd.DataFrame]:
        closes = self.source.closes(sorted(set(tickers)), period)
        if closes.empty:
            return {}, closes
        last = closes.ffill().iloc[-1]
        return {t: float(v) for t, v in last.items() if pd.notna(v)}, closes

    def context(self, prices: dict[str, float]) -> RiskContext:
        b = self.broker
        positions = b.positions()
        cash = b.cash()
        equity = cash + sum(p.units * prices.get(t, p.avg_price) for t, p in positions.items())
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        week_start = (now - timedelta(days=7)).isoformat()
        hist = self.store.equity_history()
        eq_day = next((h["equity"] for h in hist if h["ts"] >= day_start), None)
        eq_week = next((h["equity"] for h in hist if h["ts"] >= week_start), None)
        pending = self.store.proposals("pendiente")
        return RiskContext(
            equity=equity,
            cash=cash,
            positions=positions,
            prices=prices,
            trades_today=len([t for t in self.store.trades(since=day_start) if t["origin"] != "stop-loss"]),
            pending_buys=sum(p["amount"] or 0 for p in pending if p["side"] == "comprar"),
            pending_count=len(pending),
            equity_day_start=eq_day,
            equity_week_start=eq_week,
            paused=self.store.paused,
        )

    def expire_proposals(self) -> None:
        limit = (datetime.now(timezone.utc) - timedelta(hours=self.cfg.caducidad_propuesta_horas)).isoformat()
        for p in self.store.proposals("pendiente"):
            if p["created"] < limit:
                self.store.update_proposal(p["id"], "caducada", "Nadie la aprobó a tiempo.", only_if="pendiente")

    # ---------------------------------------------------------- ciclo
    def run_cycle(self) -> dict:
        """Un ciclo completo. Devuelve un resumen. Nunca lanza excepciones: las registra."""
        try:
            return self._run_cycle()
        except Exception as exc:  # el bot debe seguir vivo para el siguiente ciclo
            self.store.log("error", f"El ciclo falló: {type(exc).__name__}: {exc}")
            return {"ok": False, "error": str(exc)}

    def _run_cycle(self) -> dict:
        cfg = self.cfg
        errors = cfg.validate()
        if errors:
            self.store.log("error", "Configuración no válida: " + "; ".join(errors))
            return {"ok": False, "error": "; ".join(errors)}
        self.expire_proposals()

        held = list(self.broker.positions())
        prices, closes = self.prices(cfg.lista_activos + held + [cfg.referencia], "1y")
        if not prices:
            self.store.log("error", "No se pudieron obtener precios. Se reintentará en el próximo ciclo.")
            return {"ok": False, "error": "sin precios"}

        self._handle_stop_losses(prices)
        ctx = self.context(prices)
        self.store.add_equity(ctx.equity, ctx.cash, prices.get(cfg.referencia))

        if ctx.paused:
            self.store.log("info", "Bot detenido: se registró el valor de la cartera pero no se analizó el mercado.")
            return {"ok": True, "paused": True}
        week_block = buying_blocked(ctx, cfg)
        if week_block and "semanal" in week_block:
            self.store.set_paused(True, week_block)
            return {"ok": True, "paused": True}

        snaps = []
        for t in cfg.lista_activos:
            if t not in closes or closes[t].dropna().size < 30:
                self.store.log("aviso", f"Sin datos suficientes de {t}; se omite en este ciclo.")
                continue
            s = snapshot(t, closes[t])
            try:
                items = self.news_fn(t)
            except Exception:
                items = []
            if items:
                scored, _ = LexiconAnalyzer().score_many([i.text for i in items])
                agg = aggregate(scored, [i.published for i in items])
                s.sentimiento, s.sentimiento_veredicto = round(agg.score, 3), agg.label
                s.titulares = [i.title for i in items[:5]]
            pos = ctx.positions.get(t)
            if pos:
                s.en_cartera_unidades = pos.units
                s.en_cartera_peso = round(100 * pos.units * prices[t] / ctx.equity, 2)
                s.en_cartera_ganancia = prices[t] / pos.avg_price - 1
            snaps.append(s)

        advice: Advice = self.advisor.advise(snaps, cfg, 100 * ctx.cash / ctx.equity if ctx.equity else 100)
        created = self._proposals_from(advice, ctx)
        self.store.set("last_cycle", {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "resumen": advice.resumen, "asesor": advice.asesor, "propuestas": created})
        self.store.log("info", f"Análisis completado con {advice.asesor}: {created} propuesta(s) nueva(s).")

        if not cfg.requiere_aprobacion:
            for p in self.store.proposals("pendiente"):
                self.approve(p["id"], origin="automatica")
        return {"ok": True, "propuestas": created, "resumen": advice.resumen}

    def _handle_stop_losses(self, prices: dict[str, float]) -> None:
        if isinstance(self.broker, EToroDemoBroker):
            return  # en eToro el stop-loss va en la propia orden y lo ejecuta eToro
        positions = self.broker.positions()
        for t in stop_loss_hits(positions, prices):
            pos = positions[t]
            msg = f"Stop-loss de {label(t)}: precio {prices[t]:,.2f} ≤ {pos.stop_price:,.2f}."
            if self.cfg.stop_loss_automatico:
                fill = self.broker.sell(t, pos.units, prices[t])
                self.store.add_trade(t, "vender", fill.units, fill.price, fill.amount, fill.fee, origin="stop-loss")
                self.store.log("aviso", msg + " Vendido automáticamente.")
            elif not any(p["ticker"] == t and p["side"] == "vender" for p in self.store.proposals("pendiente")):
                self.store.add_proposal(t, "vender", prices[t], units=pos.units, confidence=1.0, reason=msg, risks="El precio podría recuperarse.", checks=["Stop-loss alcanzado."])
                self.store.log("aviso", msg + " Venta propuesta.")

    def _proposals_from(self, advice: Advice, ctx: RiskContext) -> int:
        created = 0
        full_only = isinstance(self.broker, EToroDemoBroker)
        for d in advice.decisions:
            if d.accion == "mantener":
                continue
            # Sustituye una propuesta pendiente del mismo activo y sentido.
            for old in self.store.proposals("pendiente"):
                if old["ticker"] == d.ticker and old["side"] == d.accion:
                    self.store.update_proposal(old["id"], "caducada", "Sustituida por un análisis más reciente.", only_if="pendiente")
                    if old["side"] == "comprar":
                        ctx.pending_buys -= old["amount"] or 0
                    ctx.pending_count -= 1
            v = check_buy(d, ctx, self.cfg) if d.accion == "comprar" else check_sell(d, ctx, self.cfg, full_only)
            price = ctx.prices.get(d.ticker, 0.0)
            if not v.ok:
                self.store.add_proposal(d.ticker, d.accion, price, confidence=d.confianza, reason=d.motivo, risks=d.riesgos, checks=v.notes, status="descartada")
                continue
            self.store.add_proposal(
                d.ticker, d.accion, price,
                amount=v.amount if d.accion == "comprar" else round(v.units * price, 2),
                units=v.units if d.accion == "vender" else None,
                confidence=d.confianza, reason=d.motivo, risks=d.riesgos, checks=v.notes,
            )
            if d.accion == "comprar":
                ctx.pending_buys += v.amount
            ctx.pending_count += 1
            created += 1
        return created

    # ---------------------------------------------------------- decisiones de la persona
    def approve(self, pid: int, origin: str = "aprobada") -> tuple[bool, str]:
        p = self.store.proposal(pid)
        if not p or p["status"] != "pendiente":
            return False, "La propuesta ya no está pendiente."
        if not self.store.update_proposal(pid, "aprobada", only_if="pendiente"):
            return False, "La propuesta ya no está pendiente."
        try:
            prices, _ = self.prices(list({p["ticker"], self.cfg.referencia}))
            price = prices.get(p["ticker"])
            if not price:
                raise BrokerError("No se pudo obtener el precio actual.")
            moved = abs(price / p["price"] - 1) * 100
            if moved > self.cfg.max_desvio_precio_pct:
                raise BrokerError(f"El precio se movió un {moved:.1f} % desde la propuesta (máximo {self.cfg.max_desvio_precio_pct} %). Espera al próximo análisis.")
            ctx = self.context(prices)  # esta propuesta ya no cuenta como pendiente
            if p["side"] == "comprar":
                blocked = buying_blocked(ctx, self.cfg)
                if blocked:
                    raise BrokerError(blocked)
                spendable = ctx.cash - ctx.pending_buys - self.cfg.min_liquidez_pct / 100 * ctx.equity
                amount = min(p["amount"], max(spendable, 0))
                if amount < self.cfg.importe_minimo:
                    raise BrokerError("Ya no hay efectivo suficiente respetando la liquidez mínima.")
                stop = price * (1 - self.cfg.stop_loss_pct / 100)
                fill = self.broker.buy(p["ticker"], amount, price, stop)
            else:
                if ctx.paused:
                    raise BrokerError("El bot está detenido.")
                pos = ctx.positions.get(p["ticker"])
                if not pos:
                    raise BrokerError("Ya no tienes esta posición.")
                fill = self.broker.sell(p["ticker"], min(p["units"] or pos.units, pos.units), price)
        except BrokerError as e:
            self.store.update_proposal(pid, "fallida", str(e))
            self.store.log("aviso", f"No se ejecutó la propuesta #{pid} ({label(p['ticker'])}): {e}")
            return False, str(e)
        self.store.add_trade(p["ticker"], p["side"], fill.units, fill.price, fill.amount, fill.fee, pid, origin)
        result = f"{p['side'].capitalize()} {fill.units:.6g} {p['ticker']} a {fill.price:,.2f} ({fill.amount:,.2f})."
        self.store.update_proposal(pid, "ejecutada", result)
        self.store.log("info", f"Ejecutada #{pid}: {result}")
        return True, result

    def reject(self, pid: int) -> bool:
        ok = self.store.update_proposal(pid, "rechazada", "Rechazada por ti.", only_if="pendiente")
        if ok:
            self.store.log("info", f"Propuesta #{pid} rechazada.")
        return ok

    def save_config(self, cfg: BotConfig) -> list[str]:
        errors = cfg.validate()
        if not errors:
            cfg.save(self.cfg_path)
            self.cfg = cfg
            self._broker = None
            self._advisor = None
            self._source = None
            self.store.log("info", "Configuración actualizada.")
        return errors

    def reset_simulation(self) -> None:
        self.store.set("paper_cash", None)
        self.store.set("paper_positions", {})
        self._broker = None
        with self.store.conn() as c:
            c.execute("DELETE FROM equity")
            c.execute("DELETE FROM trades")
            c.execute("DELETE FROM proposals")
        self.store.log("aviso", "Simulación reiniciada.")
