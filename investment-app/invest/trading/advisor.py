"""Asesores: estudian el mercado y PROPONEN operaciones. El control de riesgo decide después.

- ClaudeAdvisor: la IA de Claude analiza técnica, noticias y cartera y razona cada propuesta.
- RuleAdvisor: reglas técnicas fijas, sin IA ni coste. Útil para comparar o si no hay clave.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from .config import BotConfig
from .market import AssetSnapshot


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
    name = "Reglas técnicas"

    def advise(self, snaps: list[AssetSnapshot], cfg: BotConfig, cash_pct: float) -> Advice:
        out = []
        for s in snaps:
            sent = s.sentimiento if s.sentimiento is not None else 0.0
            held = s.en_cartera_unidades > 0
            if not held and s.lectura_tecnica >= 50 and sent >= -0.1 and (s.rsi or 50) < 70:
                out.append(Decision(s.ticker, "comprar", cfg.max_operacion_pct, 0, 0.65 + min(s.lectura_tecnica, 100) / 400,
                                    f"Tendencia alcista (lectura técnica {s.lectura_tecnica:+d}) y sentimiento {s.sentimiento_veredicto.lower()}.",
                                    "Un cambio de tendencia o una mala noticia pueden revertir la subida."))
            elif held and (s.lectura_tecnica <= -50 or sent <= -0.4):
                out.append(Decision(s.ticker, "vender", 0, 1.0, 0.7,
                                    f"Deterioro: lectura técnica {s.lectura_tecnica:+d}, sentimiento {s.sentimiento_veredicto.lower()}.",
                                    "Podría rebotar después de vender."))
            else:
                out.append(Decision(s.ticker, "mantener", motivo="Sin señal clara."))
        return Advice(out, "Propuestas generadas con reglas técnicas fijas (sin IA).", self.name)


SYSTEM_PROMPT = """Eres el analista de un bot de inversión personal con horizonte de MEDIO PLAZO (días a semanas).
Cada pocas horas recibes un estudio de mercado de una lista cerrada de activos y la cartera actual, y propones operaciones.

Cómo trabajar:
- Por defecto, "mantener". Propón comprar o vender solo con una razón clara y concreta que combine tendencia, impulso y noticias.
- No persigas subidas fuertes ni vendas por pánico tras una caída puntual; ten en cuenta la volatilidad del activo.
- Diversifica: no concentres compras en activos muy correlacionados (p. ej. varias tecnológicas a la vez).
- Las noticias simuladas o escasas pesan poco. Si los datos no bastan, dilo y mantén.
- Sé honesto con la confianza (0 a 1): 0,8 o más solo con varias señales coherentes.
- El tamaño de compra es un % de la cartera total; nunca superes el máximo indicado. Para vender, indica qué fracción de la posición.
- Escribe los motivos y riesgos en español, claros y breves, para una persona no experta.

Un sistema de control de riesgo independiente revisará cada propuesta y la persona dueña de la cartera tendrá que aprobarla."""


class ClaudeAdvisor:
    name = "IA (Claude)"
    model = "claude-opus-5-5"

    def __init__(self, client=None):
        import anthropic

        self.client = client or anthropic.Anthropic()

    def advise(self, snaps: list[AssetSnapshot], cfg: BotConfig, cash_pct: float) -> Advice:
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
            "cartera": {"liquidez_pct": round(cash_pct, 2)},
            "activos": [s.as_dict() for s in snaps],
        }
        prompt = (
            "Estudio de mercado actual (variaciones en tanto por uno; pesos en %; sentimiento de -1 a 1):\n"
            f"```json\n{json.dumps(payload, ensure_ascii=False, indent=1)}\n```\n"
            "Devuelve una decisión por cada activo de la lista, con el mismo ticker."
        )
        response = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
            output_format=Result,
        )
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise RuntimeError("Claude no devolvió un análisis válido.")
        valid = {s.ticker for s in snaps}
        decisions = [
            Decision(i.ticker, i.accion, max(0.0, i.importe_pct), min(max(0.0, i.fraccion_venta), 1.0), min(max(0.0, i.confianza), 1.0), i.motivo, i.riesgos)
            for i in response.parsed_output.decisiones
            if i.ticker in valid
        ]
        return Advice(decisions, response.parsed_output.resumen, self.name)
