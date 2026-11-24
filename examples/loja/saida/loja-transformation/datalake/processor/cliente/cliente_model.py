"""Modelo da tabela cliente (SDD: docs_sdd/cliente_sdd_doc.md).

Objeto de configuracao puro — sem SparkSession, sem I/O.
"""

from pyspark.sql.types import IntegerType, StringType, TimestampType

from datalake.utils.field_spec import FieldSpec
from datalake.utils.table_model import TableModel


class ClienteModel(TableModel):
    table_name = "cliente"
    database_name = "loja"
    table_comment = "Clientes cadastrados na loja"

    fields = [
        FieldSpec("id", "id_cliente", IntegerType(), "Identificador do cliente", transformation="default"),
        FieldSpec("name", "nm_nome", StringType(), "Nome completo do cliente", transformation="default"),
        FieldSpec("email", "dc_email", StringType(), "E-mail de contato do cliente", transformation="default"),
        FieldSpec("document", "nu_documento", StringType(), "CPF do cliente", encrypted=True, transformation=None),
        FieldSpec("city", "dc_cidade", StringType(), "Cidade do cliente", transformation="default"),
        FieldSpec("created_at", "dh_criacao", TimestampType(), "Data e hora do cadastro", transformation="default"),
        FieldSpec("@timestamp", "dh_criacao_data_lake", TimestampType(), "Data e horario da criacao do registro no Data Lake.", transformation="default"),
    ]

    merge_keys = ["id_cliente"]

    partition_columns = ["dt_criacao_particao", "dt_atualizacao_registro_particao"]

    #: Coluna usada na deduplicacao: mantem o registro mais recente por chave de merge.
    timestamp_field = "dh_criacao_data_lake"

    extra_column_comments = {
        "dt_criacao_particao": "Data de criacao (yyyyMMdd) - particao de dados.",
        "dt_atualizacao_registro_particao": "Data de processamento (yyyyMMdd) - particao de atualizacao.",
        "dh_criacao_registro": "Data e horario da criacao do registro na camada.",
        "dh_atualizacao_registro": "Data e horario da ultima atualizacao do registro na camada.",
    }

    #: Tamanho medio estimado de uma linha (bytes), usado no file sizing da primeira carga.
    avg_row_size = 188
