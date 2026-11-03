"""Archivo de claves y ajustes del equipo (contraseña de la web, Claude, eToro).

Ubicación:
  - Windows:        %APPDATA%\\AsistenteInversion\\env
  - Linux / macOS:  ~/.config/asistente-inversion/env

Formato: una línea por clave, `NOMBRE=valor`. Las líneas vacías o que empiezan por # se ignoran.
Las variables de entorno que ya existan tienen prioridad sobre el archivo.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def config_dir() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "AsistenteInversion"
    return Path.home() / ".config" / "asistente-inversion"


def env_file() -> Path:
    return Path(os.environ.get("ASISTENTE_ENV_FILE") or config_dir() / "env")


def parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip().lstrip("﻿")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def load_env(path: Path | None = None) -> list[str]:
    """Carga el archivo de claves en el entorno. Devuelve los nombres cargados (nunca los valores)."""
    path = Path(path) if path else env_file()
    if not path.exists():
        return []
    try:
        values = parse_env(path.read_text(encoding="utf-8"))
    except OSError:
        return []
    loaded = []
    for key, value in values.items():
        if value and not os.environ.get(key):
            os.environ[key] = value
            loaded.append(key)
    return loaded
