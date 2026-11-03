"""Configuración del bot. Se guarda en data/bot/config.json y se edita desde la web."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

MODES = {"simulacion": "Simulación local (dinero ficticio)", "etoro_demo": "Cuenta demo de eToro (dinero virtual)"}
# A propósito no hay modo "real": operar con dinero real requiere una orden expresa y nuevo código.
UNIVERSE_CLASSES = ("Acciones", "ETF", "Materias primas", "Criptomonedas")
ADVISORS = {"claude": "IA (Claude)", "reglas": "Reglas técnicas (sin IA, gratis)"}


@dataclass
class BotConfig:
    # Qué y cómo
    modo: str = "etoro_demo"  # nunca hay modo real: no existe código para operar con dinero real
    asesor: str = "claude"
    motor_ia: str = "api"  # "api" (clave de Anthropic) o "suscripcion" (Claude Code con tu plan)
    modelo_ia: str = "claude-opus-5-5"
    respaldo_reglas: bool = True  # si Claude no está disponible, usar las reglas de la estrategia en ese ciclo
    fuente_datos: str = "etoro"  # "etoro" (con Yahoo de respaldo), "yahoo" o "demo"
    fuentes_noticias: list[str] = field(default_factory=lambda: ["yahoo", "google_es", "google_en", "etoro"])
    comunidad_etoro: bool = True  # opiniones de inversores de eToro (se analizan aparte de las noticias)
    universo: str = "catalogo"  # "catalogo": el bot elige entre todo el catálogo; "lista": solo lista_activos
    max_candidatos: int = 12  # cuántos activos estudia a fondo (noticias + IA) en cada ciclo
    lista_activos: list[str] = field(default_factory=lambda: ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "GLD", "GC=F", "CL=F", "BTC-USD"])
    referencia: str = "SPY"  # para comparar el resultado del bot con "comprar y mantener"
    capital_inicial: float = 10_000.0  # solo simulación
    diferencial_pct: float = 0.15  # coste simulado por operación (spread), en %

    # Aprobación
    requiere_aprobacion: bool = False  # el bot compra y vende solo (en la cuenta demo)
    caducidad_propuesta_horas: float = 6.0
    max_desvio_precio_pct: float = 2.0  # si el precio se movió más desde la propuesta, no se ejecuta

    # Límites de riesgo (la IA no puede saltárselos)
    max_operacion_pct: float = 5.0  # de la cartera total, por compra
    max_posicion_pct: float = 20.0  # peso máximo de un activo
    min_liquidez_pct: float = 10.0  # efectivo que siempre se conserva
    max_perdida_diaria_pct: float = 3.0
    max_perdida_semanal_pct: float = 6.0
    max_operaciones_dia: int = 4
    importe_minimo: float = 25.0
    stop_loss_pct: float = 8.0
    stop_loss_automatico: bool = True  # vende sin esperar aprobación si salta el stop-loss
    confianza_minima: float = 0.6

    # Aprendizaje
    horizonte_evaluacion_dias: int = 14  # a cuántos días se juzga si una decisión acertó

    @classmethod
    def load(cls, path: Path) -> "BotConfig":
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def validate(self) -> list[str]:
        errors = []
        if self.modo not in MODES:
            errors.append(f"Modo desconocido: {self.modo}")
        if self.asesor not in ADVISORS:
            errors.append(f"Asesor desconocido: {self.asesor}")
        if self.motor_ia not in ("api", "suscripcion"):
            errors.append(f"Conexión con Claude desconocida: {self.motor_ia}")
        if not self.lista_activos and self.universo == "lista":
            errors.append("La lista de activos está vacía.")
        if self.universo not in ("catalogo", "lista"):
            errors.append(f"Universo desconocido: {self.universo}")
        if self.fuente_datos not in ("etoro", "yahoo", "demo"):
            errors.append(f"Fuente de datos desconocida: {self.fuente_datos}")
        for name in ("max_operacion_pct", "max_posicion_pct", "max_perdida_diaria_pct", "max_perdida_semanal_pct", "stop_loss_pct"):
            v = getattr(self, name)
            if not 0 < v <= 100:
                errors.append(f"{name} debe estar entre 0 y 100.")
        if not 0 <= self.min_liquidez_pct < 100:
            errors.append("min_liquidez_pct debe estar entre 0 y 99.")
        if self.max_operacion_pct > self.max_posicion_pct:
            errors.append("max_operacion_pct no puede superar max_posicion_pct.")
        if not 0 <= self.confianza_minima <= 1:
            errors.append("confianza_minima debe estar entre 0 y 1.")
        return errors
