"""Fluxo do gerador: uma sequência fixa de etapas, sem laço de correção.

    Profiler → Nomenclatura → Input Gen (ingestion.yml) → Transform Gen → Validator

A geração é por template: o mesmo contrato gera sempre os mesmos arquivos. Se o projeto gerado não compila, o
defeito está no template, e regerar não resolve. Por isso o Validator só confere e reporta: o erro aparece no
resultado (status "error") e o teste do template deve pegá-lo antes de chegar a quem usa.
"""

from __future__ import annotations

from datapacto.agents.input_gen import input_gen_agent
from datapacto.agents.naming import naming_agent
from datapacto.agents.profiler import profiler_agent
from datapacto.agents.transform_gen import transform_gen_agent
from datapacto.agents.validator import validator_agent
from datapacto.state import FrameworkState

STEPS = (profiler_agent, naming_agent, input_gen_agent, transform_gen_agent, validator_agent)


def run_pipeline(state: FrameworkState) -> FrameworkState:
    """Executa as etapas em ordem; cada uma devolve só o que mudou no estado."""
    state = dict(state)
    for step in STEPS:
        state.update(step(state))
    if state.get("compile_errors"):
        n = len(state["compile_errors"])
        state["status"] = "error"
        state["error_message"] = (f"O projeto gerado não compila ({n} erro{'s' if n > 1 else ''}). "
                                  "É defeito do template: abra uma issue com o contrato que o causou.")
    else:
        state["status"] = "done"
    return state
