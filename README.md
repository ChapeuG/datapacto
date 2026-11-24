# datapacto

<p align="center">
  <img src="docs/assets/pacto-de-dados.jpg" alt="Pacto de Dados: por um uso responsável das informações" width="800">
</p>

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

## Começo rápido

Do DDL à raw, com o [exemplo da loja](examples/README.md) (precisa de Python 3.10+ e Docker):

```bash
git clone https://github.com/ChapeuG/datapacto.git && cd datapacto

pip install -e packages/generator
datapacto generate --contract examples/loja/contracts/loja --output-dir examples/loja/saida \
    --naming-dir examples/loja/saida/naming
docker compose -f examples/loja/demo/docker-compose.yml run --rm ingestao
```

O `generate` cria o `ingestion.yml` de cada tabela e o projeto PySpark de transformação. O `docker compose` sobe um
Postgres com dados e roda o orquestrador num Spark local: as duas tabelas chegam em `examples/loja/demo/raw/`, com
o CPF criptografado e as regras de qualidade do contrato aplicadas.

Para os seus contratos, use a interface ou a linha de comando:

```bash
pip install -e "packages/generator[ui]"
datapacto ui                                                     # contrato → campos → validação → geração
datapacto generate --contract contracts/<dataset>/<tabela>.odcs.yaml
```

### Extras da instalação

A instalação básica gera tudo sem LLM. O resto é opcional:

| Extra | Para quê |
|---|---|
| `[llm]` | Nomes das colunas sugeridos por LLM (LiteLLM, OpenAI ou outro provedor do LangChain) |
| `[amostra]` | Amostra de dados (`--sample`) e arquivos de dados como entrada (`.parquet`, CSV de dados) |
| `[ui]` | A interface *Data Contract Studio* |
| `[all]` | Todos os anteriores |

## O que serve para qualquer stack

O datapacto tem duas partes, e só a segunda depende da arquitetura:

| Parte | Serve para | Exige |
|---|---|---|
| **Contrato e validação** | Escrever o contrato ODCS a partir de uma DDL ou de outro schema, padronizar os nomes das colunas e conferir nomenclatura e tipagem | Nada além do Python. O contrato continua ODCS puro, compatível com o [`datacontract-cli`](https://github.com/datacontract/datacontract-cli). O comando `datapacto validate`, para rodar no CI de quem usa, é o próximo marco do [roadmap](docs/ROADMAP.md). |
| **Pipeline (runtime de referência)** | Gerar e rodar a ingestão e a transformação | A mesma arquitetura do projeto: origem JDBC (Postgres, Oracle, MySQL, SQL Server), raw em JSON no S3, staging em Delta, Spark (EMR) e Glue |

Quem tem outra arquitetura aproveita a primeira parte e ignora a segunda.

## O que tem neste repositório

| Pasta | O que é |
|---|---|
| [`packages/generator`](packages/generator/README.md) | **Gerador** (`datapacto`): CLI e interface *Data Contract Studio*. Contrato → `ingestion.yml` + projeto de transformação, com nomenclatura padronizada (heurística ou LLM). |
| [`packages/orchestrator`](packages/orchestrator/README.md) | **Orquestrador** (PySpark): lê o `ingestion.yml`, conecta na origem (Postgres, Oracle, MySQL, SQL Server), roda as regras de qualidade, criptografa colunas sensíveis e grava na raw. |
| [`contracts/`](contracts/template.odcs.yaml) | Template do data contract, com cada campo explicado. |
| [`examples/`](examples/README.md) | Exemplo completo: DDL, contratos, arquivos gerados e a demonstração com Docker. |
| [`docs/`](docs/MANUAL.md) | [Manual](docs/MANUAL.md) (passo a passo), [visão do projeto](docs/VISAO.md) (para onde vamos) e [roadmap](docs/ROADMAP.md) (o que falta, em ordem). |

Os dois pacotes são instalados separadamente: o orquestrador roda no cluster Spark (EMR) e não precisa das
dependências do gerador.

## Testes

```bash
cd packages/generator && python -m pytest tests
cd packages/orchestrator && python -m pytest
```

## Contribuir

Veja o [guia de contribuição](CONTRIBUTING.md).

## Licença

[Apache 2.0](LICENSE), a mesma do ODCS.
