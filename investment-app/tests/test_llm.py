import json
import subprocess
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from invest import llm
from invest.trading import learning
from invest.trading.config import BotConfig
from invest.trading.engine import Engine


class Out(BaseModel):
    items: list[dict]
    resumen: str


class Nested(BaseModel):
    class Item(BaseModel):
        x: int

    lista: list[Item]


def fake_runner(stdout="", stderr="", code=0, exc=None, seen=None):
    def run(cmd, **kw):
        if seen is not None:
            seen["cmd"], seen["kw"] = cmd, kw
        if exc:
            raise exc
        return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=code)

    return run


def ok_json(structured):
    return json.dumps({"type": "result", "subtype": "success", "is_error": False, "structured_output": structured, "result": "x"})


def test_claude_code_success_and_command(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-no-usar")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok")
    seen = {}
    b = llm.ClaudeCodeBackend(binary="/usr/bin/claude", workdir=tmp_path / "w", runner=fake_runner(ok_json({"items": [], "resumen": "r"}), seen=seen))
    out = b.structured("hola", Out, system="sys", effort="low", model="m")
    assert out.resumen == "r"
    cmd = seen["cmd"]
    assert cmd[:2] == ["/usr/bin/claude", "-p"]
    assert cmd[cmd.index("--tools") + 1] == ""
    assert cmd[cmd.index("--model") + 1] == "m" and cmd[cmd.index("--system-prompt") + 1] == "sys"
    assert seen["kw"]["input"] == "hola"
    env = seen["kw"]["env"]
    assert "ANTHROPIC_API_KEY" not in env and env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok"  # nunca cobra por API


def test_schema_is_inlined():
    schema = llm.inline_schema(Nested.model_json_schema())
    assert "$defs" not in json.dumps(schema) and "$ref" not in json.dumps(schema)
    assert schema["properties"]["lista"]["items"]["properties"]["x"]["type"] == "integer"


@pytest.mark.parametrize("stdout,err", [
    (json.dumps({"is_error": True, "result": "Claude usage limit reached. Your limit will reset at 5pm"}), llm.LLMLimitError),
    (json.dumps({"is_error": True, "result": "Invalid API key · Please run /login"}), llm.LLMError),
    (json.dumps({"is_error": False, "result": "texto sin estructura"}), llm.LLMError),
    ("esto no es json", llm.LLMError),
])
def test_claude_code_errors(tmp_path, stdout, err):
    b = llm.ClaudeCodeBackend(binary="claude", workdir=tmp_path, runner=fake_runner(stdout))
    with pytest.raises(err):
        b.structured("x", Out)


def test_claude_code_missing_binary_and_timeout(tmp_path):
    with pytest.raises(llm.LLMError, match="No se encontró"):
        llm.ClaudeCodeBackend(binary="claude", workdir=tmp_path, runner=fake_runner(exc=FileNotFoundError())).structured("x", Out)
    with pytest.raises(llm.LLMError, match="tardó"):
        llm.ClaudeCodeBackend(binary="claude", workdir=tmp_path, runner=fake_runner(exc=subprocess.TimeoutExpired("claude", 1))).structured("x", Out)


def test_api_backend_maps_rate_limit():
    class RateLimitError(Exception):
        pass

    class Msgs:
        def parse(self, **kw):
            raise RateLimitError("429")

    b = llm.ApiBackend(SimpleNamespace(beta=SimpleNamespace(messages=Msgs())))
    with pytest.raises(llm.LLMLimitError):
        b.structured("x", Out)


def test_get_backend():
    assert isinstance(llm.get_backend("suscripcion"), llm.ClaudeCodeBackend)
    assert isinstance(llm.get_backend("api"), llm.ApiBackend)


class LimitedBackend:
    name = "suscripcion"

    def structured(self, *a, **k):
        raise llm.LLMLimitError("Se alcanzó el límite de uso de tu suscripción")


def demo_engine(tmp_path, **kw):
    cfg = BotConfig(lista_activos=["SPY", "AAPL", "GC=F"], referencia="SPY", fuente_datos="demo", asesor="claude", motor_ia="suscripcion", modo="simulacion", universo="lista", **kw)
    e = Engine(tmp_path, cfg=cfg, news_fn=lambda t: [])
    e.llm_backend = lambda: LimitedBackend()
    return e


def test_cycle_falls_back_to_rules_when_claude_is_unavailable(tmp_path):
    e = demo_engine(tmp_path)
    r = e.run_cycle()
    assert r["ok"]
    assert "respaldo" in e.store.get("last_cycle")["asesor"]
    assert any("Claude no está disponible" in ev["message"] for ev in e.store.events())


def test_cycle_without_fallback_does_nothing(tmp_path):
    e = demo_engine(tmp_path, respaldo_reglas=False)
    r = e.run_cycle()
    assert not r["ok"] and e.store.proposals() == []


def test_review_falls_back_to_optimizer(tmp_path):
    e = demo_engine(tmp_path)
    r = learning.review(e)
    cand = e.store.strategy(r["candidata"])
    assert cand["origin"] == "optimizador" and "no estuvo disponible" in cand["diagnosis"]
