# Exemplos

## `loja/`: do DDL à raw

Uma loja fictícia com duas tabelas (`cliente` e `pedido`, ligadas por chave estrangeira). O exemplo mostra cada
etapa do datapacto com os arquivos de verdade, e roda a ingestão num ambiente local com Docker.

```
loja/
  ddl.sql                      1. o ponto de partida: o CREATE TABLE da origem
  contracts/loja/*.odcs.yaml   2. os data contracts (gerados da DDL e completados à mão)
  saida/
    naming/*.json              3. a nomenclatura revisável (nome padronizado de cada coluna)
    ingestion-config/loja/     4. o ingestion.yml de cada tabela, lido pelo orquestrador
    loja-transformation/       5. o projeto PySpark de transformação (raw → staging Delta)
  demo/                        6. Postgres com dados + Spark local para rodar a ingestão
```

### Rodar do início ao fim

Da raiz do repositório:

```bash
pip install -e packages/generator
datapacto generate --contract examples/loja/contracts/loja --output-dir examples/loja/saida \
    --naming-dir examples/loja/saida/naming
docker compose -f examples/loja/demo/docker-compose.yml run --rm ingestao
```

O último comando sobe um Postgres com 50 clientes e 200 pedidos criados ontem, constrói uma imagem com Spark e o
orquestrador, e roda a carga diária (D-1) das duas tabelas. O resultado fica em `examples/loja/demo/raw/`:

```
raw/loja/cliente/dt_ingestao=<hoje>/part-*.json.gz
raw/loja/pedido/dt_ingestao=<hoje>/part-*.json.gz
```

Na raw de `cliente`, a coluna `document` (CPF) está criptografada: o contrato marca a coluna com `encrypt: true`.
Nas duas tabelas, as regras de qualidade do contrato rodam antes da gravação (`id` único, `email` preenchido e
pelo menos uma linha).

A primeira execução demora alguns minutos (imagem e driver JDBC). Nada usa AWS: as secrets vêm de variáveis de
ambiente (`secretId: env:DEMO_DB`) e a tabela não é registrada no Glue/Athena (`--skip-catalog`).

### Refazer os contratos a partir da DDL

Os contratos de `contracts/loja/` saíram deste comando e depois ganharam descrições, dono e a criptografia do CPF:

```bash
datapacto contrato --ddl examples/loja/ddl.sql --dataset loja --source-db postgres --env demo \
    --host postgres --port 5432 --database loja --secret-id env:DEMO_DB \
    --raw-partition-column dt_ingestao -o examples/loja/contracts
```
