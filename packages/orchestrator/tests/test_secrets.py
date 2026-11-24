"""Secrets sem AWS: env:NOME e file:caminho (demonstração local e CI)."""

import json

import pytest

from ingestion.secrets import get_secret, get_secret_field


def test_secret_from_env(monkeypatch):
    monkeypatch.setenv("DEMO_DB", json.dumps({"username": "demo", "password": "demo"}))
    assert get_secret("env:DEMO_DB") == {"username": "demo", "password": "demo"}


def test_secret_from_file(tmp_path):
    path = tmp_path / "aes.json"
    path.write_text(json.dumps({"AES_KEY": "chave"}), encoding="utf-8")
    assert get_secret_field(f"file:{path}", "AES_KEY") == "chave"


@pytest.mark.parametrize("secret_id, message", [
    ("env:NAO_EXISTE_XYZ", "não definida"),
    ("file:/nao/existe.json", "não existe"),
])
def test_missing_local_secret(secret_id, message):
    with pytest.raises(ValueError, match=message):
        get_secret(secret_id)


def test_local_secret_must_be_json_object(monkeypatch):
    monkeypatch.setenv("DEMO_DB", "[1, 2]")
    with pytest.raises(ValueError, match="objeto JSON"):
        get_secret("env:DEMO_DB")
