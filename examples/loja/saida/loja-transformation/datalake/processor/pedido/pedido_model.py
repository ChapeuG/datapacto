"""Modelo da tabela pedido (SDD: docs_sdd/pedido_sdd_doc.md).

Objeto de configuracao puro — sem SparkSession, sem I/O.
"""

from pyspark.sql.types import DecimalType, IntegerType, StringType, TimestampType

from datalake.utils.field_spec import FieldSpec
from datalake.utils.table_model import TableModel


class PedidoModel(TableModel):
    table_name = "pedido"
    database_name = "loja"
    table_comment = "Pedidos feitos pelos clientes da loja"

    fields = [
        FieldSpec("id", "id_pedido", IntegerType(), "Identificador do pedido", transformation="default"),
        FieldSpec("customer_id", "id_cliente", IntegerType(), "Cliente que fez o pedido", transformation="default"),
        FieldSpec("status", "cd_status", StringType(), "Situação do pedido (ABERTO, PAGO, CANCELADO)", transformation="default"),
        FieldSpec("total_amount", "vl_total", DecimalType(12, 2), "Valor total do pedido em reais", transformation="default"),
        FieldSpec("created_at", "dh_criacao", TimestampType(), "Data e hora do pedido", transformation="default"),
        FieldSpec("@timestamp", "dh_criacao_data_lake", TimestampType(), "Data e horario da criacao do registro no Data Lake.", transformation="default"),
    ]

    merge_keys = ["id_pedido"]

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
    avg_row_size = 112
