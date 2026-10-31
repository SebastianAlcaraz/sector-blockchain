"""Configuración del bot. Se guarda en data/bot/config.json y se edita desde la web."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

MODES = {"simulacion": "Simulación local (dinero ficticio)", "etoro_demo": "Cuenta demo de eToro (dinero virtual)"}
ADVISORS = {"claude": "IA (Claude)", "reglas": "Reglas técnicas (sin IA, gratis)"}


@dataclass
class BotConfig:
    # Qué y cómo
    modo: str = "simulacion"
    asesor: str = "claude"
    fuente_datos: str = "yahoo"  # "yahoo" o "demo"
    lista_activos: list[str] = field(default_factory=lambda: ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "GLD", "GC=F", "CL=F", "BTC-USD"])
    referencia: str = "SPY"  # para comparar el resultado del bot con "comprar y mantener"
    capital_inicial: float = 10_000.0  # solo simulación
    diferencial_pct: float = 0.15  # coste simulado por operación (spread), en %

    # Aprobación
    requiere_aprobacion: bool = True
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
        if not self.lista_activos:
            errors.append("La lista de activos está vacía.")
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
