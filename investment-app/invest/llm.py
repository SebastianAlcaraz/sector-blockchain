"""Conexión con Claude por dos vías intercambiables:

- ApiBackend ("api"): API de Anthropic con ANTHROPIC_API_KEY. Pago por uso.
- ClaudeCodeBackend ("suscripcion"): el programa oficial `claude` (Claude Code) en modo automático,
  con tu suscripción (token de `claude setup-token` en CLAUDE_CODE_OAUTH_TOKEN). Gasta de los
  límites de tu plan y no tiene coste extra.

Las dos devuelven una respuesta validada con el mismo esquema (un modelo de Pydantic).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

DEFAULT_MODEL = "claude-opus-5-5"
BACKENDS = {"api": "API de Anthropic (clave, pago por uso)", "suscripcion": "Suscripción de Claude (Claude Code)"}


class LLMError(RuntimeError):
    """Claude no está disponible o no devolvió una respuesta válida."""


class LLMLimitError(LLMError):
    """Se alcanzó un límite de uso (suscripción) o de peticiones (API)."""


_LIMIT_WORDS = ("usage limit", "rate limit", "rate_limit", "limit reached", "quota", "overloaded", "limite", "límite")


def _looks_like_limit(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in _LIMIT_WORDS)


def inline_schema(schema: dict) -> dict:
    """Sustituye las referencias $ref de Pydantic por su definición (esquema autocontenido)."""
    defs = schema.get("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            return {k: walk(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


class ApiBackend:
    name = "api"

    def __init__(self, client=None):
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def structured(self, prompt: str, output_model, system: str = "", effort: str = "medium", model: str = DEFAULT_MODEL):
        kwargs = dict(
            model=model,
            max_tokens=16000,
            output_config={"effort": effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
            output_format=output_model,
        )
        if system:
            kwargs["system"] = system
        try:
            response = self.client.beta.messages.parse(**kwargs)
        except Exception as exc:
            if type(exc).__name__ == "RateLimitError":
                raise LLMLimitError("La API de Anthropic ha limitado las peticiones; se reintentará más tarde.") from exc
            if type(exc).__name__ in ("AuthenticationError", "PermissionDeniedError"):
                raise LLMError("La clave ANTHROPIC_API_KEY no es válida o no tiene permisos.") from exc
            if type(exc).__name__ in ("APIConnectionError", "APITimeoutError", "InternalServerError", "APIStatusError"):
                raise LLMError(f"No se pudo hablar con la API de Anthropic ({type(exc).__name__}).") from exc
            raise
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise LLMError("Claude no devolvió una respuesta válida.")
        return response.parsed_output


def find_claude_binary() -> str | None:
    """El programa `claude`: CLAUDE_BIN, el PATH o la ruta del instalador oficial (~/.local/bin)."""
    local_bin = Path.home() / ".local" / "bin"
    for candidate in (os.environ.get("CLAUDE_BIN"), shutil.which("claude"), str(local_bin / "claude"), str(local_bin / "claude.exe")):
        if candidate and Path(candidate).exists():
            return candidate
    return None


class ClaudeCodeBackend:
    name = "suscripcion"

    def __init__(self, binary: str | None = None, workdir: Path | None = None, timeout: float = 600, runner=subprocess.run):
        self.binary = binary
        self.workdir = Path(workdir) if workdir else Path.home() / ".cache" / "asistente-inversion" / "claude"
        self.timeout = timeout
        self.runner = runner

    def command(self, schema: dict, system: str, effort: str, model: str) -> list[str]:
        cmd = [
            self.binary or find_claude_binary() or "claude",
            "-p",
            "--output-format", "json",
            "--json-schema", json.dumps(schema, ensure_ascii=False),
            "--model", model,
            "--effort", effort,
            "--tools", "",  # sin herramientas: solo analiza el texto que le damos
            "--strict-mcp-config",
            "--permission-mode", "dontAsk",
            "--permission-prompts", "none",
            "--no-session-persistence",
        ]
        if system:
            cmd += ["--system-prompt", system]
        return cmd

    @staticmethod
    def environment() -> dict:
        """Sin claves de API: si existieran, Claude Code las usaría y cobraría por API en vez de usar la suscripción."""
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        return env

    def structured(self, prompt: str, output_model, system: str = "", effort: str = "medium", model: str = DEFAULT_MODEL):
        cmd = self.command(inline_schema(output_model.model_json_schema()), system, effort, model)
        self.workdir.mkdir(parents=True, exist_ok=True)  # carpeta vacía: no carga CLAUDE.md ni ajustes de ningún proyecto
        try:
            proc = self.runner(cmd, input=prompt, capture_output=True, text=True, timeout=self.timeout, cwd=str(self.workdir), env=self.environment())
        except FileNotFoundError as exc:
            raise LLMError("No se encontró el programa `claude`. Instala Claude Code en el equipo del bot (ver README).") from exc
        except subprocess.TimeoutExpired as exc:
            raise LLMError(f"Claude Code tardó más de {self.timeout:.0f} s en responder.") from exc

        data = None
        for line in reversed((proc.stdout or "").strip().splitlines()):
            try:
                data = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
        if not isinstance(data, dict):
            detail = (proc.stderr or proc.stdout or "").strip()[-300:]
            if _looks_like_limit(detail):
                raise LLMLimitError("Se alcanzó el límite de uso de tu suscripción. " + detail)
            raise LLMError(f"Respuesta de Claude Code no válida (código {proc.returncode}). {detail}")
        if data.get("is_error") or data.get("structured_output") is None:
            msg = str(data.get("result") or data.get("subtype") or "sin detalle")[:300]
            if _looks_like_limit(msg):
                raise LLMLimitError("Se alcanzó el límite de uso de tu suscripción: " + msg)
            if "login" in msg.lower() or "auth" in msg.lower() or "token" in msg.lower():
                raise LLMError("Claude Code no tiene sesión iniciada. Crea el token con `claude setup-token` y ponlo en CLAUDE_CODE_OAUTH_TOKEN. " + msg)
            raise LLMError("Claude Code no devolvió una respuesta válida: " + msg)
        try:
            return output_model.model_validate(data["structured_output"])
        except Exception as exc:
            raise LLMError(f"La respuesta de Claude Code no cumple el formato esperado: {exc}") from exc


def get_backend(name: str, client=None):
    if name == "suscripcion":
        return ClaudeCodeBackend()
    return ApiBackend(client)


def check(backend, model: str = DEFAULT_MODEL) -> str:
    """Prueba mínima de conexión. Devuelve un texto corto o lanza LLMError."""
    from pydantic import BaseModel

    class Ping(BaseModel):
        respuesta: str

    out = backend.structured("Responde solo con la palabra: listo", Ping, effort="low", model=model)
    return out.respuesta
