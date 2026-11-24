"""Secrets: AWS Secrets Manager ou, para rodar sem AWS, uma variável de ambiente ou um arquivo local.

O secretId do contrato escolhe a origem:

- `env:NOME`: JSON na variável de ambiente NOME (demonstração local, CI);
- `file:caminho.json`: JSON num arquivo local;
- qualquer outro valor: id ou ARN no AWS Secrets Manager.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ENV_PREFIX = "env:"
FILE_PREFIX = "file:"


def _raw_secret(secret_id: str) -> str:
    if secret_id.startswith(ENV_PREFIX):
        name = secret_id[len(ENV_PREFIX):]
        if name not in os.environ:
            raise ValueError(f"Secret {secret_id}: variável de ambiente {name} não definida")
        return os.environ[name]
    if secret_id.startswith(FILE_PREFIX):
        path = Path(secret_id[len(FILE_PREFIX):])
        if not path.is_file():
            raise ValueError(f"Secret {secret_id}: arquivo {path} não existe")
        return path.read_text(encoding="utf-8")

    import boto3

    return boto3.client("secretsmanager").get_secret_value(SecretId=secret_id)["SecretString"]


def get_secret(secret_id: str) -> dict:
    """Secret em JSON (username, password, host, port, dbname, url...)."""
    value = _raw_secret(secret_id)
    try:
        data = json.loads(value)
    except json.JSONDecodeError as e:
        raise ValueError(f"Secret {secret_id} não é um JSON") from e
    if not isinstance(data, dict):
        raise ValueError(f"Secret {secret_id} não é um objeto JSON")
    return data


def get_secret_field(secret_id: str, field: str) -> str:
    """Campo da secret (ex: AES_KEY, a chave AES em base64)."""
    data = get_secret(secret_id)
    if field not in data:
        raise ValueError(f"Campo '{field}' não encontrado na secret {secret_id}")
    return str(data[field])
