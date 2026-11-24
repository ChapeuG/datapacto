"""Dependências opcionais (extras do pip).

A instalação básica (`pip install datapacto`) gera contrato, ingestion.yml e transformação sem LLM. O que é
pesado fica em extras:

- `[llm]`: nomenclatura por LLM (langchain, openai);
- `[amostra]`: leitura de amostras e arquivos de dados (pandas, pyarrow);
- `[ui]`: Data Contract Studio (streamlit).
"""

from __future__ import annotations

import importlib
from types import ModuleType


class MissingExtra(ValueError):
    """Uma função precisa de um pacote que só vem com um extra. A mensagem diz o que instalar."""


def require(module: str, extra: str, purpose: str) -> ModuleType:
    """Importa `module` ou explica qual extra instalar."""
    try:
        return importlib.import_module(module)
    except ImportError as e:
        raise MissingExtra(f"{purpose} precisa do extra [{extra}]: pip install \"datapacto[{extra}]\" "
                           f"(falta o módulo {e.name or module})") from e
