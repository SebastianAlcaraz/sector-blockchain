"""Aprendizaje del bot.

Ciclo semanal:
1. Evaluar: cada decisión pasada (comprar, vender, mantener, también las rechazadas o descartadas)
   se compara con lo que hizo el precio después y con el índice de referencia.
2. Diagnosticar: qué señales y qué tipo de decisiones acertaron o fallaron.
3. Proponer: la IA (o un optimizador sin IA) crea una estrategia candidata con cambios moderados.
4. Validar: la candidata se prueba con datos históricos que no se usaron para ajustarla.
5. Decidir: tú adoptas o descartas la candidata. Se puede volver a cualquier versión anterior.

Los límites de riesgo nunca forman parte de la estrategia: el aprendizaje no puede tocarlos.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pandas as pd

from ..llm import DEFAULT_MODEL, ApiBackend, LLMError
from . import backtest
from .strategy import BOUNDS, DEFAULT_PLAYBOOK, StrategyParams

if TYPE_CHECKING:
    from .engine import Engine


# ------------------------------------------------------------------ estrategia activa
def active_strategy(engine: "Engine") -> dict:
    active = engine.store.strategies("activa")
    if active:
        return active[0]
    sid = engine.store.add_strategy("activa", "inicial", StrategyParams().as_dict(), DEFAULT_PLAYBOOK, changelog="Estrategia inicial.")
    engine.store.log("info", "Creada la estrategia inicial (versión 1).")
    return engine.store.strategy(sid)


# ------------------------------------------------------------------ 1. evaluar decisiones
def evaluate_decisions(engine: "Engine", horizon_days: int | None = None) -> int:
    horizon = horizon_days or engine.cfg.horizonte_evaluacion_dias
    limit = datetime.now(timezone.utc) - timedelta(days=horizon)
    pending = [d for d in engine.store.decisions(evaluated=False) if datetime.fromisoformat(d["ts"]) <= limit]
    if not pending:
        return 0
    tickers = sorted({d["ticker"] for d in pending} | {engine.cfg.referencia})
    closes = engine.source.closes(tickers, "1y")
    if closes.empty:
        return 0
    done = 0
    for d in pending:
        target = pd.Timestamp(datetime.fromisoformat(d["ts"]).astimezone(timezone.utc).replace(tzinfo=None)) + pd.Timedelta(days=horizon)
        after = closes.index[closes.index >= target.normalize()]
        if not len(after) or d["ticker"] not in closes:
            continue
        price_then = closes.at[after[0], d["ticker"]]
        if pd.isna(price_then) or not d["price"]:
            continue
        fwd = float(price_then / d["price"] - 1)
        bench = None
        if d["bench_price"] and engine.cfg.referencia in closes:
            b = closes.at[after[0], engine.cfg.referencia]
            bench = float(b / d["bench_price"] - 1) if pd.notna(b) else None
        engine.store.set_outcome(d["id"], fwd, bench)
        done += 1
    if done:
        engine.store.log("info", f"Evaluadas {done} decisiones pasadas a {horizon} días.")
    return done


# ------------------------------------------------------------------ 2. diagnóstico
def _excess(d: dict) -> float:
    return d["fwd_return"] - (d["bench_return"] or 0.0)


def decision_stats(decisions: list[dict]) -> dict:
    """Aciertos por tipo de decisión y por nivel de puntuación. Un acierto es:
    comprar y que el activo bata al índice; vender y que lo haga peor que el índice."""
    ev = [d for d in decisions if d.get("evaluated")]
    out: dict = {"evaluadas": len(ev), "por_accion": {}, "por_puntuacion": {}}
    for action in ("comprar", "vender", "mantener"):
        ds = [d for d in ev if d["action"] == action]
        if not ds:
            continue
        ex = [_excess(d) for d in ds]
        row = {"n": len(ds), "exceso_medio": round(sum(ex) / len(ex), 4)}
        if action == "comprar":
            row["aciertos"] = round(sum(e > 0 for e in ex) / len(ex), 3)
        elif action == "vender":
            row["aciertos"] = round(sum(e < 0 for e in ex) / len(ex), 3)
        out["por_accion"][action] = row
    buckets = {"baja (< -0,3)": lambda s: s < -0.3, "media": lambda s: -0.3 <= s <= 0.3, "alta (> 0,3)": lambda s: s > 0.3}
    for name, f in buckets.items():
        ds = [d for d in ev if d["score"] is not None and f(d["score"])]
        if ds:
            ex = [_excess(d) for d in ds]
            out["por_puntuacion"][name] = {"n": len(ds), "exceso_medio_posterior": round(sum(ex) / len(ex), 4)}
    return out


# ------------------------------------------------------------------ 3. proponer
def optimize(closes: pd.DataFrame, base: StrategyParams, cfg, trials: int = 40, seed: int = 7) -> StrategyParams:
    """Búsqueda local sin IA: prueba variaciones moderadas y se queda con la mejor DENTRO de muestra.
    La validación fuera de muestra se hace después, por separado."""
    rng = random.Random(seed)
    start, cut = backtest.split_point(closes)

    def fitness(p: StrategyParams) -> float:
        r = backtest.run(closes, p, cfg, start=start, end=cut)
        return r.sharpe + 2 * r.rentabilidad + r.max_caida  # rentabilidad ajustada por riesgo

    best, best_fit = base, fitness(base)
    for _ in range(trials):
        d = base.as_dict()
        for k in rng.sample(list(BOUNDS), 3):  # cambia pocos parámetros cada vez
            lo, hi = BOUNDS[k]
            d[k] = d[k] + rng.gauss(0, (hi - lo) * 0.12)
        cand = StrategyParams.from_dict(d)
        f = fitness(cand)
        if f > best_fit:
            best, best_fit = cand, f
    return best


REVIEW_SYSTEM = """Eres el responsable de estrategia de un bot de inversión personal de medio plazo.
Cada semana revisas cómo han salido sus decisiones y propones una versión mejorada de la estrategia.

Principios:
- Cambios moderados y justificados por los datos. Con pocas decisiones evaluadas, cambia poco: el ruido engaña.
- Busca patrones repetidos (p. ej. "las compras con RSI alto salieron mal"), no casos aislados.
- La estrategia tiene dos partes: parámetros numéricos (dentro de los rangos dados) y un manual de principios en texto.
- No puedes cambiar los límites de riesgo (stop-loss, tamaños máximos, pérdidas máximas): no son parte de la estrategia.
- Tu propuesta se probará con datos históricos que no ves y la persona dueña decidirá si la adopta.
- Escribe en español claro para alguien no experto."""


def claude_candidate(backend, current: dict, stats: dict, sample: list[dict], current_bt: dict, bot_vs_ref: dict, model: str = DEFAULT_MODEL) -> dict:
    from pydantic import BaseModel, Field, create_model

    Params = create_model("Params", **{k: (int if k == "dias_minimos" else float, ...) for k in BOUNDS})

    class Review(BaseModel):
        diagnostico: str = Field(description="Qué funciona y qué no, en 3-5 frases")
        lecciones: list[str] = Field(description="Hasta 6 lecciones concretas y breves")
        parametros: Params
        manual: str = Field(description="Manual de principios actualizado, máximo 250 palabras, en puntos numerados")
        cambios: str = Field(description="Qué cambias respecto a la versión actual y por qué")

    payload = {
        "estrategia_actual": {"parametros": current["params"], "manual": current["playbook"], "lecciones_previas": current["lessons"]},
        "rangos_permitidos": {k: list(v) for k, v in BOUNDS.items()},
        "estadisticas_decisiones": stats,
        "muestra_decisiones_evaluadas": sample,
        "prueba_historica_actual": {k: v for k, v in current_bt.items() if k != "curva_fuera"},
        "resultado_real_del_bot": bot_vs_ref,
        "nota": "El sentimiento de noticias no existe en el histórico: la prueba histórica solo usa señales técnicas.",
    }
    prompt = "Revisión semanal. Datos:\n```json\n" + json.dumps(payload, ensure_ascii=False, indent=1, default=str) + "\n```"
    r = backend.structured(prompt, Review, system=REVIEW_SYSTEM, effort="high", model=model)
    return {
        "params": StrategyParams.from_dict(r.parametros.model_dump()),
        "playbook": r.manual.strip(),
        "lessons": [l.strip() for l in r.lecciones][:6],
        "changelog": r.cambios.strip(),
        "diagnosis": r.diagnostico.strip(),
        "origin": "IA",
    }


# ------------------------------------------------------------------ 4-5. revisión completa
def review(engine: "Engine", client=None) -> dict:
    """Ejecuta la revisión semanal y guarda una estrategia candidata (no la activa)."""
    cfg = engine.cfg
    evaluate_decisions(engine)
    current = active_strategy(engine)
    cur_params = StrategyParams.from_dict(current["params"])

    closes = engine.source.closes(sorted(set(cfg.lista_activos) | {cfg.referencia}), "5y")
    if closes.empty:
        raise RuntimeError("No hay datos históricos para probar estrategias.")
    closes = closes.ffill()
    cur_bt = backtest.evaluate(closes, cur_params, cfg)

    decisions = engine.store.decisions(evaluated=True, limit=300)
    stats = decision_stats(decisions)
    sample = [
        {"ticker": d["ticker"], "accion": d["action"], "confianza": d["confidence"], "puntuacion": d["score"],
         "rsi": d["features"].get("rsi"), "tendencia_50": d["features"].get("sobre_media_50"), "sentimiento": d["features"].get("sentimiento"),
         "exceso_posterior": round(_excess(d), 4)}
        for d in decisions[:40]
    ]
    hist = engine.store.equity_history()
    bot_vs_ref = {}
    if len(hist) >= 2 and hist[0]["benchmark"] and hist[-1]["benchmark"]:
        bot_vs_ref = {"bot": round(hist[-1]["equity"] / hist[0]["equity"] - 1, 4), "referencia": round(hist[-1]["benchmark"] / hist[0]["benchmark"] - 1, 4), "desde": hist[0]["ts"]}

    cand = None
    note = ""
    if cfg.asesor == "claude":
        backend = ApiBackend(client) if client is not None else engine.llm_backend()
        try:
            cand = claude_candidate(backend, current, stats, sample, cur_bt, bot_vs_ref, cfg.modelo_ia)
        except LLMError as exc:
            if not cfg.respaldo_reglas:
                raise
            note = f"Claude no estuvo disponible ({exc}); se usó el optimizador sin IA. "
            engine.store.log("aviso", "Revisión: " + note)
    if cand is None:
        params = optimize(closes, cur_params, cfg)
        cand = {
            "params": params, "playbook": current["playbook"], "lessons": current["lessons"], "origin": "optimizador",
            "changelog": "Ajuste automático de parámetros por búsqueda en datos históricos (sin IA).",
            "diagnosis": note + f"{stats['evaluadas']} decisiones evaluadas. " + "; ".join(f"{a}: {r.get('aciertos', '—')} aciertos, exceso medio {r['exceso_medio']:+.2%}" for a, r in stats["por_accion"].items()),
        }

    cand_bt = backtest.evaluate(closes, cand["params"], cfg)
    ok, reasons = backtest.compare(cur_bt, cand_bt)
    metrics = {
        "actual": {k: v for k, v in cur_bt.items() if k != "curva_fuera"},
        "candidata": {k: v for k, v in cand_bt.items() if k != "curva_fuera"},
        "motivos": reasons,
        "estadisticas": stats,
    }
    for old in engine.store.strategies("candidata"):
        engine.store.set_strategy_status(old["id"], "descartada")
    sid = engine.store.add_strategy("candidata", cand["origin"], cand["params"].as_dict(), cand["playbook"], cand["lessons"], cand["changelog"], cand["diagnosis"], metrics, ok)
    engine.store.set("last_review", {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "candidata": sid, "recomendada": ok})
    engine.store.log("info", f"Revisión de estrategia: candidata v{sid} {'RECOMENDADA' if ok else 'no recomendada'}. " + " ".join(reasons))
    return {"ok": True, "candidata": sid, "recomendada": ok, "motivos": reasons}


def adopt(engine: "Engine", sid: int) -> None:
    s = engine.store.strategy(sid)
    if not s or s["status"] not in ("candidata", "retirada", "descartada"):
        raise ValueError("Esa estrategia no se puede activar.")
    engine.store.activate_strategy(sid)
    engine.store.log("aviso", f"Estrategia v{sid} activada ({s['origin']}).")
