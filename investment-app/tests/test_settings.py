import os

from invest import settings


def test_parse_env_ignores_comments_and_quotes():
    text = "\ufeff# comentario\nAPP_PASSWORD=abc\n\nANTHROPIC_API_KEY='x y'\nETORO_API_KEY=\nMAL FORMATO\n"
    assert settings.parse_env(text) == {"APP_PASSWORD": "abc", "ANTHROPIC_API_KEY": "x y", "ETORO_API_KEY": ""}


def test_load_env_does_not_override_existing(tmp_path, monkeypatch):
    f = tmp_path / "env"
    f.write_text("PRUEBA_A=archivo\nPRUEBA_B=archivo\nPRUEBA_C=\n", encoding="utf-8")
    monkeypatch.setenv("PRUEBA_A", "entorno")
    monkeypatch.delenv("PRUEBA_B", raising=False)
    monkeypatch.delenv("PRUEBA_C", raising=False)
    assert settings.load_env(f) == ["PRUEBA_B"]
    assert os.environ["PRUEBA_A"] == "entorno" and os.environ["PRUEBA_B"] == "archivo" and "PRUEBA_C" not in os.environ
    assert settings.load_env(tmp_path / "no-existe") == []


def test_config_dir_per_platform(monkeypatch):
    monkeypatch.setattr(settings.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\x\AppData\Roaming")
    assert str(settings.config_dir()).endswith("AsistenteInversion")
    monkeypatch.setattr(settings.sys, "platform", "linux")
    assert str(settings.config_dir()).endswith(os.path.join(".config", "asistente-inversion"))
