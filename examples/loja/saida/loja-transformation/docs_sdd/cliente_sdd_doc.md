# SDD — cliente

> Gerado pelo framework a partir do DDL. Seções marcadas como **Informação pendente** precisam ser completadas antes do desenvolvimento (skill sdd-specification).

## 1. Identificação

| Campo | Valor |
|---|---|
| Nome da tabela | `cliente` |
| Database | `loja` |
| Comentário | Clientes cadastrados na loja |
| Origem dos dados | `public.cliente` (postgres) via datapacto-orchestrator (`ingestion-config/loja/cliente.ingestion.yml`) — JSON gzip na raw |

## 2. Particionamento

| Nível | Campo | Tipo | Descrição |
|---|---|---|---|
| 1 | `dt_criacao_particao` | StringType | Data de criacao (yyyyMMdd) - particao de dados. |
| 2 | `dt_atualizacao_registro_particao` | StringType | Data de processamento (yyyyMMdd) - particao de atualizacao. |


## 3. Chave de Merge (Deduplicação/Upsert)

Campos: `id_cliente` (origem: --merge-keys).

Deduplicação: registro mais recente por chave, ordenado por `dh_criacao_data_lake`.

## 4. Schema — Campos Principais

| rawField | stagingField | dataType | transformation | customFormat | Comentário |
|---|---|---|---|---|---|
| `id` | `id_cliente` | IntegerType | default | - | Identificador do cliente |
| `name` | `nm_nome` | StringType | default | - | Nome completo do cliente |
| `email` | `dc_email` | StringType | default | - | E-mail de contato do cliente |
| `document` | `nu_documento` | StringType | null | - | CPF do cliente **[criptografado na ingestão]** |
| `city` | `dc_cidade` | StringType | default | - | Cidade do cliente |
| `created_at` | `dh_criacao` | TimestampType | default | - | Data e hora do cadastro |
| `@timestamp` | `dh_criacao_data_lake` | TimestampType | default | - | Data e horario da criacao do registro no Data Lake. |
| derivado | `dh_criacao_registro` | TimestampType | null | - | Data e horário da criação do registro na camada. |
| derivado | `dh_atualizacao_registro` | TimestampType | null | - | Data e horário da última atualização do registro na camada. |

## 5. Campos Aninhados (NestedField)

Nenhum. Todos os campos são flat.

## 6. Regras de Negócio

- Segurança: `nu_documento` chegam criptografados (AES/ECB + base64) da ingestão; preservados sem transformação.

**Informação pendente:** domínios de valores, regras condicionais e campos derivados.

## 7. Enrichments

Nenhum enrichment definido.

**Informação pendente:** confirme se a tabela precisa de joins com tabelas de lookup.

## 8. Joins Inter-tabelas

Não aplicável.

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
| Modo inicial | `mode("overwrite")` com particionamento (`maxRecordsPerFile` ≈ 128MB / 188 bytes). |
| Modo incremental | Delta MERGE com condições null-safe (`<=>`); `dh_criacao_registro` preservado. |
| Merge keys | Seção 3. |
| Persist | `MEMORY_AND_DISK` (tabela simples), `unpersist` no `finally`. |
| Manifesto | `symlink_format_manifest`. |
| Tabela Hive | `CREATE EXTERNAL TABLE IF NOT EXISTS loja.cliente` + `ALTER TABLE ADD COLUMNS`. |
| Partições | `ALTER TABLE ADD IF NOT EXISTS PARTITION` em lotes de 100. |
