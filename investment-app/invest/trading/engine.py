"""Motor del bot: un ciclo de análisis y la ejecución de propuestas aprobadas."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from ..catalog import CATALOG, label
from ..data import make_source
from ..news import EToroClient, aggregate_news, demo_news
from ..sentiment import LexiconAnalyzer, aggregate
from ..llm import LLMError, get_backend
from .advisor import Advice, ClaudeAdvisor, RuleAdvisor
from .broker import BrokerError, EToroDemoBroker, PaperBroker
from .config import UNIVERSE_CLASSES, BotConfig
from .market import snapshot
from .learning import active_strategy, evaluate_decisions
from ..indicators import atr
from .risk import RiskContext, buying_blocked, check_buy, check_sell, stop_loss_hits, stop_pct_for
from .store import Store
from .strategy import StrategyParams, score_snapshot


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
        self.news_fn = news_fn or self._default_news
        self.community_fn = None if news_fn else self._community_posts  # en pruebas con noticias falsas, sin comunidad
        self._etoro_client = None
        self._etoro_general = None  # noticias generales de eToro (una petición por ciclo)
        self.news_errors: list[str] = []

    # ---------------------------------------------------------- piezas
    @property
    def source(self):
        if self._source is None:
            self._source = make_source(self.cfg.fuente_datos)
        return self._source

    @property
    def etoro(self) -> EToroClient | None:
        """Cliente de eToro compartido; recuerda los identificadores de los activos entre ciclos."""
        if self._etoro_client is None and EToroClient.configured():
            self._etoro_client = EToroClient(cache=self.store.get("etoro_ids", {}) or {})
        return self._etoro_client

    def save_etoro_cache(self) -> None:
        if self._etoro_client is not None:
            self.store.set("etoro_ids", self._etoro_client.cache)

    def universe(self) -> list[str]:
        """Activos entre los que el bot puede elegir."""
        if self.cfg.universo == "catalogo":
            base = [t for c in UNIVERSE_CLASSES for t in CATALOG[c]]
            return list(dict.fromkeys(base + list(self.cfg.lista_activos)))
        return list(self.cfg.lista_activos)

    @property
    def broker(self):
        if self._broker is None:
            if self.cfg.modo == "etoro_demo" and self.etoro is not None:
                self._broker = EToroDemoBroker(self.etoro, self.universe())
            else:
                if self.cfg.modo == "etoro_demo":
                    self.store.log("aviso", "Faltan las claves de eToro: el bot opera en la simulación local hasta que las añadas.")
                self._broker = PaperBroker(self.store, self.cfg.capital_inicial, self.cfg.diferencial_pct)
        return self._broker

    def _default_news(self, ticker: str):
        if self.cfg.fuente_datos == "demo":
            return demo_news(ticker, label(ticker).split(" (")[0], 8)
        if "etoro" in self.cfg.fuentes_noticias and self.etoro is not None and self._etoro_general is None:
            try:
                self._etoro_general = self.etoro.news()
            except Exception:
                self._etoro_general = []
        name = label(ticker).split(" (")[0]
        return aggregate_news(ticker, name, self.cfg.fuentes_noticias, 20, self.etoro, self._etoro_general, self.news_errors)

    def _community_posts(self, ticker: str):
        if not self.cfg.comunidad_etoro or self.etoro is None or self.cfg.fuente_datos == "demo":
            return []
        return self.etoro.instrument_posts(ticker, 25, label(ticker).split(" (")[0])

    def llm_backend(self):
        return get_backend(self.cfg.motor_ia)

    @property
    def advisor(self):
        if self._advisor is None:
            self._advisor = ClaudeAdvisor(self.llm_backend(), model=self.cfg.modelo_ia) if self.cfg.asesor == "claude" else RuleAdvisor()
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
        universe = self.universe()
        self._etoro_general, self.news_errors = None, []
        prices, closes = self.prices(universe + held + [cfg.referencia], "1y")
        backup = getattr(self.source, "used_backup", [])
        if backup:
            self.store.log("aviso", f"eToro no dio precios de {len(backup)} activo(s); se usó Yahoo Finance: {', '.join(backup[:10])}.")
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

        strategy = active_strategy(self)
        params = StrategyParams.from_dict(strategy["params"])
        held_since = self._held_since()
        # 1) Estudio técnico de todo el universo (barato: solo precios).
        snaps = []
        for t in universe:
            if t not in closes or closes[t].dropna().size < 30:
                if t in cfg.lista_activos or t in ctx.positions:
                    self.store.log("aviso", f"Sin datos suficientes de {t}; se omite en este ciclo.")
                continue
            s = snapshot(t, closes[t])
            s.puntuacion_estrategia = score_snapshot(s, params)
            snaps.append(s)
        # 2) Preselección: lo que tienes en cartera + los mejores candidatos según la estrategia.
        held_set = set(ctx.positions)
        ranked = sorted((s for s in snaps if s.ticker not in held_set), key=lambda s: s.puntuacion_estrategia, reverse=True)
        snaps = [s for s in snaps if s.ticker in held_set] + ranked[: max(cfg.max_candidatos, 1)]
        # Volatilidad de los preseleccionados (velas completas): fija la distancia del stop y el tamaño.
        ctx.atr_pct = self._atr_pct([s.ticker for s in snaps])
        for s in snaps:
            s.atr_pct = ctx.atr_pct.get(s.ticker)
            s.stop_pct = stop_pct_for(cfg, s.atr_pct)[0]
        # 3) Estudio a fondo de los preseleccionados: noticias de varias fuentes y comunidad de eToro.
        lex = LexiconAnalyzer()
        for s in snaps:
            t = s.ticker
            try:
                items = self.news_fn(t)
            except Exception:
                items = []
            if items:
                scored, _ = lex.score_many([i.text for i in items])
                agg = aggregate(scored, [i.published for i in items])
                s.sentimiento, s.sentimiento_veredicto = round(agg.score, 3), agg.label
                s.titulares = [i.title for i in items[:6]]
                s.fuentes_noticias = sorted({v.strip() for i in items for v in (i.via or "").split(",") if v.strip()})
            if self.community_fn:
                try:
                    posts = self.community_fn(t)
                except Exception:
                    posts = []
                if posts:
                    pscored, _ = lex.score_many([p.text for p in posts])
                    s.sentimiento_comunidad = round(aggregate(pscored, [p.published for p in posts]).score, 3)
                    s.opiniones_comunidad = [p.title[:160] for p in posts[:3]]
            pos = ctx.positions.get(t)
            if pos:
                s.en_cartera_unidades = pos.units
                s.en_cartera_peso = round(100 * pos.units * prices[t] / ctx.equity, 2)
                s.en_cartera_ganancia = prices[t] / pos.avg_price - 1
                if t in held_since:
                    s.dias_en_cartera = (datetime.now(timezone.utc) - datetime.fromisoformat(held_since[t])).days
            s.puntuacion_estrategia = score_snapshot(s, params)
        self.save_etoro_cache()
        if self.news_errors:
            self.store.log("aviso", "Algunas fuentes de noticias fallaron: " + "; ".join(sorted(set(self.news_errors))[:6]))

        cash_pct = 100 * ctx.cash / ctx.equity if ctx.equity else 100
        try:
            advice: Advice = self.advisor.advise(snaps, cfg, cash_pct, strategy)
        except LLMError as exc:
            if not cfg.respaldo_reglas:
                raise
            self.store.log("aviso", f"Claude no está disponible ({exc}). Este ciclo usa las reglas de la estrategia.")
            advice = RuleAdvisor().advise(snaps, cfg, cash_pct, strategy)
            advice.asesor = "Reglas de la estrategia (respaldo: Claude no disponible)"
        created = self._proposals_from(advice, ctx)
        self._journal(advice, snaps, prices, strategy["id"])
        try:
            evaluate_decisions(self)
        except Exception as exc:
            self.store.log("aviso", f"No se pudieron evaluar decisiones pasadas: {exc}")
        self.store.set("last_cycle", {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "resumen": advice.resumen, "asesor": advice.asesor, "propuestas": created})
        self.store.log("info", f"Análisis completado con {advice.asesor}: {created} propuesta(s) nueva(s).")

        if not cfg.requiere_aprobacion:
            for p in self.store.proposals("pendiente"):
                self.approve(p["id"], origin="automatica")
        return {"ok": True, "propuestas": created, "resumen": advice.resumen}

    def _atr_pct(self, tickers: list[str]) -> dict[str, float]:
        """ATR de 14 días en % del último cierre. Si la fuente no da velas, el stop será el fijo."""
        if self.cfg.tipo_stop != "atr" or not tickers or not hasattr(self.source, "ohlc"):
            return {}
        try:
            candles = self.source.ohlc(tickers, "6mo")
        except Exception as exc:
            self.store.log("aviso", f"No se pudieron obtener velas para el ATR ({exc}); se usa el stop fijo.")
            return {}
        out = {}
        for t, df in candles.items():
            if len(df) < 20:
                continue
            value = atr(df["high"], df["low"], df["close"]).iloc[-1]
            if pd.notna(value) and df["close"].iloc[-1] > 0:
                out[t] = round(float(value / df["close"].iloc[-1] * 100), 3)
        missing = [t for t in tickers if t not in out]
        if missing:
            self.store.log("aviso", f"Sin velas para el ATR de {len(missing)} activo(s); usan el stop fijo: {', '.join(missing[:10])}.")
        return out

    def _held_since(self) -> dict[str, str]:
        """Fecha de la última compra de cada activo (para saber cuántos días lleva en cartera)."""
        out: dict[str, str] = {}
        for t in reversed(self.store.trades()):
            if t["side"] == "comprar":
                out[t["ticker"]] = t["ts"]
            else:
                out.pop(t["ticker"], None)
        return out

    def _journal(self, advice: Advice, snaps, prices: dict[str, float], strategy_id: int) -> None:
        """Guarda TODAS las decisiones (también mantener) para evaluarlas más adelante."""
        by_ticker = {s.ticker: s for s in snaps}
        recent = {(p["ticker"], p["side"]): p["id"] for p in self.store.proposals(limit=50)}
        bench = prices.get(self.cfg.referencia)
        for d in advice.decisions:
            s = by_ticker.get(d.ticker)
            if not s:
                continue
            self.store.add_decision(
                d.ticker, d.accion, s.precio, d.confianza, s.puntuacion_estrategia, bench, strategy_id,
                recent.get((d.ticker, d.accion)) if d.accion != "mantener" else None, s.as_dict(), d.motivo,
            )

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
            v = check_buy(d, ctx, self.cfg, set(self.universe())) if d.accion == "comprar" else check_sell(d, ctx, self.cfg, full_only)
            price = ctx.prices.get(d.ticker, 0.0)
            if not v.ok:
                self.store.add_proposal(d.ticker, d.accion, price, confidence=d.confianza, reason=d.motivo, risks=d.riesgos, checks=v.notes, status="descartada")
                continue
            self.store.add_proposal(
                d.ticker, d.accion, price,
                amount=v.amount if d.accion == "comprar" else round(v.units * price, 2),
                units=v.units if d.accion == "vender" else None,
                confidence=d.confianza, reason=d.motivo, risks=d.riesgos, checks=v.notes,
                stop_pct=v.stop_pct if d.accion == "comprar" else None,
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
                stop = price * (1 - (p.get("stop_pct") or self.cfg.stop_loss_pct) / 100)
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
