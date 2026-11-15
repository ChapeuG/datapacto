# datapacto

**Um data contract entra; a pipeline, a qualidade e o catálogo saem prontos.**

Você descreve a tabela uma vez, num data contract no padrão aberto [ODCS](https://bitol-io.github.io/open-data-contract-standard).
A plataforma valida o contrato contra as regras de modelagem da empresa, gera a ingestão e a transformação, e
(em construção) publica o mesmo contrato nas ferramentas de monitoria e de catálogo.

```
contracts/<dataset>/<tabela>.odcs.yaml
        │  datapacto generate  (ou a interface: datapacto ui)
        ▼
ingestion.yml ──▶ orquestrador (JDBC → raw no S3 + Glue/Athena)
transformação ──▶ projeto PySpark ou Scala (raw → staging Delta)
```

## O que tem neste repositório

| Pasta | O que é |
|---|---|
| [`packages/generator`](packages/generator/README.md) | **Gerador** (`datapacto`): CLI e interface *Data Contract Studio*. Contrato → `ingestion.yml` + projeto de transformação, com nomenclatura padronizada (heurística ou LLM). |
| [`packages/orchestrator`](packages/orchestrator/README.md) | **Orquestrador** (PySpark): lê o `ingestion.yml`, conecta na origem (Postgres, Oracle, MySQL, SQL Server), roda as regras de qualidade, criptografa colunas sensíveis e grava na raw. |
| [`contracts/`](contracts/template.odcs.yaml) | Template do data contract e os contratos. |
| [`docs/`](docs/MANUAL.md) | [Manual](docs/MANUAL.md) (passo a passo) e [visão do projeto](docs/VISAO.md) (para onde vamos). |

Os dois pacotes são instalados separadamente: o orquestrador roda no cluster Spark (EMR) e não precisa das
dependências do gerador.

## Começo rápido

```powershell
git clone https://github.com/ChapeuG/datapacto.git
cd datapacto
pip install -e "packages/generator[ui]"

datapacto ui                                              # interface: contrato → campos → validação → geração
datapacto generate --contract contracts/<dataset>/<tabela>.odcs.yaml   # ou pela linha de comando
```

Para o orquestrador, veja [`packages/orchestrator`](packages/orchestrator/README.md).

## Testes

```powershell
cd packages/generator;    python -m pytest tests
cd packages/orchestrator; python -m pytest
```

## Licença

Apache 2.0 (a definir: ver [decisões em aberto](docs/VISAO.md#16-decisões-em-aberto)).
