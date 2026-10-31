"""Asesores: estudian el mercado y PROPONEN operaciones. El control de riesgo decide después.

- ClaudeAdvisor: la IA de Claude analiza técnica, noticias y cartera y razona cada propuesta.
- RuleAdvisor: reglas técnicas fijas, sin IA ni coste. Útil para comparar o si no hay clave.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from ..llm import DEFAULT_MODEL, ApiBackend
from .config import BotConfig
from .market import AssetSnapshot
from .strategy import DEFAULT_PLAYBOOK, StrategyParams


@dataclass
class Decision:
    ticker: str
    accion: str  # comprar / vender / mantener
    importe_pct: float = 0.0  # compras: % de la cartera total
    fraccion_venta: float = 0.0  # ventas: parte de la posición (0-1)
    confianza: float = 0.0
    motivo: str = ""
    riesgos: str = ""


@dataclass
class Advice:
    decisions: list[Decision]
    resumen: str
    asesor: str


class RuleAdvisor:
    """Aplica directamente la parte numérica de la estrategia activa (sin IA)."""

    name = "Reglas de la estrategia"

    def advise(self, snaps: list[AssetSnapshot], cfg: BotConfig, cash_pct: float, strategy: dict | None = None) -> Advice:
        p = StrategyParams.from_dict((strategy or {}).get("params", {}))
        out = []
        for s in snaps:
            sc = s.puntuacion_estrategia if s.puntuacion_estrategia is not None else 0.0
            held = s.en_cartera_unidades > 0
            conf = round(min(0.6 + 0.4 * abs(sc), 1.0), 3)
            if not held and sc >= p.umbral_compra:
                out.append(Decision(s.ticker, "comprar", p.tamano_pct, 0, conf,
                                    f"Puntuación de la estrategia {sc:+.2f} (umbral de compra {p.umbral_compra:+.2f}); técnico {s.veredicto_tecnico.lower()}, noticias {s.sentimiento_veredicto.lower()}.",
                                    "Un cambio de tendencia o una mala noticia pueden revertir la subida."))
            elif held and sc <= p.umbral_venta and (s.dias_en_cartera or 0) >= p.dias_minimos:
                out.append(Decision(s.ticker, "vender", 0, 1.0, conf,
                                    f"Puntuación de la estrategia {sc:+.2f} por debajo del umbral de venta ({p.umbral_venta:+.2f}).",
                                    "Podría rebotar después de vender."))
            else:
                out.append(Decision(s.ticker, "mantener", motivo=f"Puntuación {sc:+.2f}: sin señal."))
        return Advice(out, "Propuestas generadas con los parámetros de la estrategia activa (sin IA).", self.name)


SYSTEM_PROMPT = """Eres el analista de un bot de inversión personal con horizonte de MEDIO PLAZO (días a semanas).
Cada pocas horas recibes un estudio de mercado de una lista cerrada de activos y la cartera actual, y propones operaciones.

Cómo trabajar:
- Por defecto, "mantener". Propón comprar o vender solo con una razón clara y concreta que combine tendencia, impulso y noticias.
- No persigas subidas fuertes ni vendas por pánico tras una caída puntual; ten en cuenta la volatilidad del activo.
- Diversifica: no concentres compras en activos muy correlacionados (p. ej. varias tecnológicas a la vez).
- Las noticias simuladas o escasas pesan poco. Si los datos no bastan, dilo y mantén.
- Sé honesto con la confianza (0 a 1): 0,8 o más solo con varias señales coherentes.
- El tamaño de compra es un % de la cartera total; nunca superes el máximo indicado. Para vender, indica qué fracción de la posición.
- Sigue el manual de la estrategia y las lecciones aprendidas que recibes; son el resultado de revisar decisiones anteriores.
- Escribe los motivos y riesgos en español, claros y breves, para una persona no experta.

Un sistema de control de riesgo independiente revisará cada propuesta y la persona dueña de la cartera tendrá que aprobarla."""


class ClaudeAdvisor:
    name = "IA (Claude)"

    def __init__(self, backend=None, client=None, model: str = DEFAULT_MODEL):
        """backend: ApiBackend o ClaudeCodeBackend. `client` (API) se mantiene por compatibilidad."""
        self.backend = backend or ApiBackend(client)
        self.model = model

    def advise(self, snaps: list[AssetSnapshot], cfg: BotConfig, cash_pct: float, strategy: dict | None = None) -> Advice:
        from pydantic import BaseModel, Field

        class Item(BaseModel):
            ticker: str
            accion: Literal["comprar", "vender", "mantener"]
            importe_pct: float = Field(description="Solo compras: % de la cartera total a invertir. 0 si no compra.")
            fraccion_venta: float = Field(description="Solo ventas: fracción de la posición a vender, de 0 a 1. 0 si no vende.")
            confianza: float = Field(description="De 0 a 1")
            motivo: str = Field(description="Por qué, en 1-2 frases")
            riesgos: str = Field(description="Qué podría salir mal, en 1 frase")

        class Result(BaseModel):
            decisiones: list[Item]
            resumen: str = Field(description="Visión general del mercado en 2-4 frases")

        payload = {
            "reglas": {
                "max_compra_pct_por_operacion": cfg.max_operacion_pct,
                "max_peso_por_activo_pct": cfg.max_posicion_pct,
                "liquidez_minima_pct": cfg.min_liquidez_pct,
                "stop_loss_pct": cfg.stop_loss_pct,
                "apalancamiento": "no permitido",
            },
            "estrategia": {
                "manual": (strategy or {}).get("playbook", DEFAULT_PLAYBOOK),
                "lecciones_aprendidas": (strategy or {}).get("lessons", []),
                "umbrales": {k: v for k, v in (strategy or {}).get("params", {}).items() if k.startswith("umbral")},
                "nota": "puntuacion_estrategia (-1 a 1) es la señal numérica de la estrategia para cada activo.",
            },
            "cartera": {"liquidez_pct": round(cash_pct, 2)},
            "activos": [s.as_dict() for s in snaps],
        }
        prompt = (
            "Estudio de mercado actual (variaciones en tanto por uno; pesos en %; sentimiento de -1 a 1):\n"
            f"```json\n{json.dumps(payload, ensure_ascii=False, indent=1)}\n```\n"
            "Devuelve una decisión por cada activo de la lista, con el mismo ticker."
        )
        parsed = self.backend.structured(prompt, Result, system=SYSTEM_PROMPT, effort="medium", model=self.model)
        valid = {s.ticker for s in snaps}
        decisions = [
            Decision(i.ticker, i.accion, max(0.0, i.importe_pct), min(max(0.0, i.fraccion_venta), 1.0), min(max(0.0, i.confianza), 1.0), i.motivo, i.riesgos)
            for i in parsed.decisiones
            if i.ticker in valid
        ]
        return Advice(decisions, parsed.resumen, self.name)
