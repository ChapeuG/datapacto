# datapacto — gerador

Gera, a partir do **data contract** de uma tabela (ou do DDL, de uma query ou de qualquer schema com nome e tipo dos
campos: Avro, JSON Schema, planilha, parquet...):

- o `ingestion.yml` usado pelo orquestrador ([`packages/orchestrator`](../orchestrator/README.md));
- o projeto de transformação `<dataset>-transformation` (raw → staging Delta), em **PySpark** (padrão) ou **Scala** (`--language scala`).

```powershell
git clone https://github.com/ChapeuG/datapacto.git
cd datapacto
pip install -e "packages/generator[ui]"

datapacto ui                                   # interface: contrato → campos → validação → geração
datapacto generate --contract actor.odcs.yaml  # ou pela linha de comando
```

Passo a passo completo: **[docs/MANUAL.md](../../docs/MANUAL.md)**.

O que cada etapa sabe fazer está nas **[skills do agente](src/datapacto/skills/README.md)** (`src/datapacto/skills/`,
um `SKILL.md` por skill; `datapacto skills` lista). Nomes de coluna com LLM usam o LiteLLM pela lib `openai`
(extra `[llm]`; `datapacto llm` testa a conexão). Sem o extra, os nomes saem da heurística.
