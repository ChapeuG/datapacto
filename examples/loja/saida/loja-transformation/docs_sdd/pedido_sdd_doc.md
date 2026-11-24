# SDD — pedido

> Gerado pelo framework a partir do DDL. Seções marcadas como **Informação pendente** precisam ser completadas antes do desenvolvimento (skill sdd-specification).

## 1. Identificação

| Campo | Valor |
|---|---|
| Nome da tabela | `pedido` |
| Database | `loja` |
| Comentário | Pedidos feitos pelos clientes da loja |
| Origem dos dados | `public.pedido` (postgres) via datapacto-orchestrator (`ingestion-config/loja/pedido.ingestion.yml`) — JSON gzip na raw |

## 2. Particionamento

| Nível | Campo | Tipo | Descrição |
|---|---|---|---|
| 1 | `dt_criacao_particao` | StringType | Data de criacao (yyyyMMdd) - particao de dados. |
| 2 | `dt_atualizacao_registro_particao` | StringType | Data de processamento (yyyyMMdd) - particao de atualizacao. |


## 3. Chave de Merge (Deduplicação/Upsert)

Campos: `id_pedido` (origem: --merge-keys).

Deduplicação: registro mais recente por chave, ordenado por `dh_criacao_data_lake`.

## 4. Schema — Campos Principais

| rawField | stagingField | dataType | transformation | customFormat | Comentário |
|---|---|---|---|---|---|
| `id` | `id_pedido` | IntegerType | default | - | Identificador do pedido |
| `customer_id` | `id_cliente` | IntegerType | default | - | Cliente que fez o pedido |
| `status` | `cd_status` | StringType | default | - | Situação do pedido (ABERTO, PAGO, CANCELADO) |
| `total_amount` | `vl_total` | DecimalType(12,2) | default | - | Valor total do pedido em reais |
| `created_at` | `dh_criacao` | TimestampType | default | - | Data e hora do pedido |
| `@timestamp` | `dh_criacao_data_lake` | TimestampType | default | - | Data e horario da criacao do registro no Data Lake. |
| derivado | `dh_criacao_registro` | TimestampType | null | - | Data e horário da criação do registro na camada. |
| derivado | `dh_atualizacao_registro` | TimestampType | null | - | Data e horário da última atualização do registro na camada. |

## 5. Campos Aninhados (NestedField)

Nenhum. Todos os campos são flat.

## 6. Regras de Negócio


**Informação pendente:** domínios de valores, regras condicionais e campos derivados.

## 7. Enrichments

Nenhum enrichment definido.

**Informação pendente:** confirme se a tabela precisa de joins com tabelas de lookup.

## 8. Joins Inter-tabelas

Relacionamentos declarados no contrato (`relationships`, chave estrangeira na origem):

| Coluna (raw → staging) | Referencia |
|---|---|
| `customer_id` → `id_cliente` | `cliente.id` |

A transformação carrega esta tabela sozinha (sem join); a relação fica documentada para quem consome a staging.

## 9. Transformações

- `StringType default` → `trim(upper(col))`
- `IntegerType/LongType/DecimalType default` → `col.cast(tipo)`
- `DateType default` → `to_date(col)`; `format` → `to_date(col, customFormat)`
- `TimestampType default` → `to_timestamp(normalize_timestamp_string(col))`; `format` → com `customFormat`
- `BooleanType default` → `S/N/true/false` → `true/false`
- `null` → sem transformação (identificadores, criptografados)

## 10. Escrita e Persistência

| Atributo | Valor |
|---|---|
| Modo inicial | `mode("overwrite")` com particionamento (`maxRecordsPerFile` ≈ 128MB / 112 bytes). |
| Modo incremental | Delta MERGE com condições null-safe (`<=>`); `dh_criacao_registro` preservado. |
| Merge keys | Seção 3. |
| Persist | `MEMORY_AND_DISK` (tabela simples), `unpersist` no `finally`. |
| Manifesto | `symlink_format_manifest`. |
| Tabela Hive | `CREATE EXTERNAL TABLE IF NOT EXISTS loja.pedido` + `ALTER TABLE ADD COLUMNS`. |
| Partições | `ALTER TABLE ADD IF NOT EXISTS PARTITION` em lotes de 100. |
