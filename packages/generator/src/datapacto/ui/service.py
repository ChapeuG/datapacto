"""Lógica da interface (sem Streamlit): formulário ↔ data contract, nomenclatura, validação e geração.

Fluxo da interface:
    1. Contrato   — formulário + colunas (DDL, contrato existente ou digitadas) → data contract ODCS
    2. Campos     — nomenclatura proposta (heurística/LLM), editável → vira stagingName no contrato
    3. Validação  — contrato, campos obrigatórios, padrão de nomenclatura e simulação da geração
    4. Geração    — grava contrato, ingestion.yml e projeto de transformação
"""

from __future__ import annotations

import contextlib
import io
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from datapacto.cli import _initial_state
from datapacto.ingestion_config import placeholders
from datapacto.parsers.contract_parser import check_relationships, custom_props, load_contract, relationships_of
from datapacto.parsers.ddl_parser import parse_ddl_tables
from datapacto.parsers.schema_reader import read_schema
from datapacto.standards.nomenclatura import validate_naming
from datapacto.standards.sources import SOURCES, get_source

ODCS_VERSION = "v3.2.0"
SOURCE_TYPES = sorted(SOURCES)
LOGICAL_TYPES = ["string", "integer", "number", "boolean", "date", "timestamp", "time", "array", "object"]
ENVIRONMENTS = ["dev", "hml", "prd"]
LANGUAGES = ["pyspark", "scala"]
LANGUAGE_LABELS = {"pyspark": "PySpark", "scala": "Scala (sbt)"}

_SPARK_TO_LOGICAL = {
    "StringType": "string", "BooleanType": "boolean", "IntegerType": "integer", "LongType": "integer",
    "ShortType": "integer", "ByteType": "integer", "DoubleType": "number", "FloatType": "number",
    "DateType": "date", "TimestampType": "timestamp",
}

COLUMN_KEYS = ["name", "physicalType", "logicalType", "primaryKey", "required", "partitioned", "encrypt", "description"]
SERVER_KEYS = ["environment", "host", "port", "database", "secretId"]
# Papéis da coluna (badges na tela) → flag da linha de coluna
ROLES = {"PK": "primaryKey", "incremental": "partitioned", "LGPD": "encrypt", "obrigatória": "required"}


def empty_form() -> dict:
    return {
        "id": str(uuid.uuid4()), "version": "1.0.0", "dataset": "", "domain": "", "table": "", "physicalName": "",
        "description": "", "owner": "", "sourceType": "postgres", "schema": "",
        "loadMode": "incremental", "incrementalColumns": [], "fetchSize": 150000, "numQueriesParallel": 1,
        "rawDatabase": "", "rawPartitionColumn": "", "cryptographySecretArn": "",
        "quality": default_quality(), "transformationLanguage": "pyspark",
    }


def empty_servers() -> list[dict]:
    return [{"environment": "prd", "host": "", "port": None, "database": "", "secretId": ""}]


# Campos do formulário que são de cada tabela; o resto (dataset, origem, servidores, raw...) vale para todas
TABLE_KEYS = ["id", "table", "physicalName", "description", "schema", "loadMode", "incrementalColumns",
              "fetchSize", "numQueriesParallel", "quality"]

# Regras de qualidade que o orquestrador executa antes de gravar na raw.
# Cada regra: {"rule": notNull|unique|rowCount, "columns": [...], "min": int, "severity": error|warning}
QUALITY_RULES = {"notNull": "Não pode vir nulo", "unique": "Sem duplicados", "rowCount": "Quantidade mínima de linhas"}
SEVERITIES = {"error": "Bloquear a carga", "warning": "Só avisar"}


def default_quality() -> list[dict]:
    """Regras de toda tabela nova: chave sem duplicados (bloqueia) e carga não vazia (avisa)."""
    return [{"rule": "unique", "columns": [], "min": None, "severity": "error"},
            {"rule": "rowCount", "columns": [], "min": 1, "severity": "warning"}]


def quality_from_table(table: dict) -> list[dict]:
    """Regras de qualidade do contrato (tabela ODCS) → linhas da tela."""
    rules: dict[tuple, dict] = {}
    for p in table.get("properties") or []:
        for q in p.get("quality") or []:
            if q.get("metric") == "nullValues":
                sev = "warning" if q.get("severity") == "warning" else "error"
                rules.setdefault(("notNull", sev), {"rule": "notNull", "columns": [], "min": None, "severity": sev})
                rules[("notNull", sev)]["columns"].append(p.get("physicalName") or p["name"])
    out = list(rules.values())
    pks = [p["name"] for p in table.get("properties") or [] if p.get("primaryKey")]
    for q in table.get("quality") or []:
        sev = "warning" if q.get("severity") == "warning" else "error"
        if q.get("metric") == "duplicateValues":
            cols = list((q.get("arguments") or {}).get("properties") or [])
            out.append({"rule": "unique", "columns": [] if cols == pks else cols, "min": None, "severity": sev})
        elif q.get("metric") == "rowCount":
            low = q.get("mustBeGreaterOrEqualTo", (q.get("mustBeGreaterThan", 0) or 0) + 1)
            out.append({"rule": "rowCount", "columns": [], "min": int(low), "severity": sev})
    return out


def empty_table_form() -> dict:
    return {k: v for k, v in empty_form().items() if k in TABLE_KEYS}


def roles_of(column: dict) -> list[str]:
    return [role for role, key in ROLES.items() if column.get(key)]


def with_roles(column: dict, roles) -> dict:
    """Linha do editor (com a lista de papéis) → linha de coluna com as flags."""
    roles = set(roles or [])
    out = {k: v for k, v in column.items() if k != "roles"}
    out.update({key: role in roles for role, key in ROLES.items()})
    return out


def _logical(spark_type: str) -> str:
    if spark_type.startswith("DecimalType"):
        return "number"
    if spark_type.startswith("ArrayType"):
        return "array"
    return _SPARK_TO_LOGICAL.get(spark_type, "string")


# ── Entrada das colunas ────────────────────────────────────────────────

def schema_to_ddl(source: str | bytes, filename: str = "") -> str:
    """DDL, query, JSON (Avro, JSON Schema, StructType), lista de campos, planilha ou arquivo de dados → DDL."""
    return read_schema(source, filename)


def ddl_tables(ddl: str) -> list[str]:
    """Nomes das tabelas de um script DDL (um ou vários CREATE TABLE), query ou schema."""
    return [s["table_name"] for s in parse_ddl_tables(read_schema(ddl))]


def columns_from_ddl(ddl: str, source_type: str = "postgres", table: str = "") -> tuple[dict, list[dict]]:
    """DDL (ou query/schema) → (campos do formulário, linhas de colunas). Com várias tabelas, escolha a tabela."""
    schemas = parse_ddl_tables(read_schema(ddl), type_map=dict(get_source(source_type).type_overrides))
    schema = next((s for s in schemas if s["table_name"].lower() == table.lower()), None) if table else schemas[0]
    if schema is None:
        raise ValueError(f"Tabela '{table}' não está na DDL. Tabelas: {', '.join(s['table_name'] for s in schemas)}")
    rows = [{
        "name": f["raw_field"], "physicalType": f["raw_type"], "logicalType": _logical(f["data_type"]),
        "primaryKey": f["is_pk"], "required": not f["nullable"], "partitioned": False, "encrypt": False,
        "description": f["comment"], "references": f.get("references", ""),
    } for f in schema["fields"]]
    # Sugestão de coluna incremental: o primeiro candidato de data do DDL
    for r in rows:
        if r["name"] in schema["partition_candidates"]:
            r["partitioned"] = True
            break
    form = {"table": schema["table_name"], "physicalName": schema["source_table"],
            "description": schema["table_comment"]}
    return form, rows


def tables_from_ddl(ddl: str, source_type: str = "postgres") -> list[tuple[dict, list[dict]]]:
    """Uma ou várias DDLs/queries/schemas → [(campos da tabela, colunas)], uma entrada por tabela.

    Tabela com coluna de data na origem vira carga incremental por ela; sem data, carga full.
    """
    ddl = read_schema(ddl)
    out = []
    for name in ddl_tables(ddl):
        form, rows = columns_from_ddl(ddl, source_type, name)
        incremental = any(r["partitioned"] for r in rows)
        out.append(({**empty_table_form(), **form, "loadMode": "incremental" if incremental else "full"}, rows))
    return out


def table_names(contract_text: str) -> list[str]:
    """Nomes das tabelas de um data contract (um contrato pode ter várias)."""
    return [t["name"] for t in load_contract(contract_text)["schema"]]


def form_from_contract(text: str, table: str = "") -> tuple[dict, list[dict], list[dict]]:
    """Contrato ODCS existente → (formulário, servidores, colunas)."""
    contract = load_contract(text)
    tables = contract["schema"]
    t = next((x for x in tables if x["name"] == table), tables[0]) if table else tables[0]
    tp, cp = custom_props(t), custom_props(contract)
    servers = contract.get("servers") or []

    form = {**empty_form(),
            "id": str(contract.get("id") or uuid.uuid4()), "version": str(contract.get("version", "1.0.0")),
            "dataset": contract.get("dataProduct", ""), "domain": contract.get("domain", ""),
            "table": t["name"], "physicalName": t.get("physicalName", ""),
            "description": t.get("description") or (contract.get("description") or {}).get("purpose", ""),
            "owner": next((m.get("username", "") for m in (contract.get("team") or {}).get("members", [])), ""),
            "sourceType": str(servers[0].get("type", "postgres")) if servers else "postgres",
            "schema": next((s.get("schema", "") for s in servers if s.get("schema")), ""),
            "loadMode": tp.get("loadMode", "incremental"), "incrementalColumns": list(tp.get("incrementalColumns") or []),
            "fetchSize": int(tp.get("fetchSize") or 150000), "numQueriesParallel": int(tp.get("numQueriesParallel") or 1),
            "rawDatabase": tp.get("rawDatabase", ""),
            "rawPartitionColumn": tp.get("rawPartitionColumn", ""),
            "cryptographySecretArn": tp.get("cryptographySecretArn", ""),
            "quality": quality_from_table(t),
            "githubOrg": cp.get("githubOrg", ""),
            "transformationLanguage": cp.get("transformationLanguage", "pyspark")}
    server_rows = [{"environment": s.get("environment", ""), "host": s.get("host", ""), "port": s.get("port"),
                    "database": s.get("database") or s.get("serviceName", ""),
                    "secretId": custom_props(s).get("secretId", "")} for s in servers] or empty_servers()
    columns = [{
        "name": p.get("physicalName") or p["name"], "physicalType": p.get("physicalType", ""),
        "logicalType": p.get("logicalType", "string"), "primaryKey": bool(p.get("primaryKey")),
        "required": bool(p.get("required")), "partitioned": bool(p.get("partitioned")),
        "encrypt": str(custom_props(p).get("encrypt", "")).lower() == "true" or custom_props(p).get("encrypt") is True,
        "description": p.get("description", ""), "stagingName": custom_props(p).get("stagingName", ""),
        "references": next(iter(relationships_of(p)), ""),
    } for p in t["properties"]]
    return form, server_rows, columns


# ── Formulário → data contract ─────────────────────────────────────────

def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


def _props(items: dict) -> list[dict]:
    return [{"property": k, "value": v} for k, v in items.items() if v not in (None, "", [], False)]


def _port(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


_DEFAULT_SCHEMA = {"postgres": "public", "sqlserver": "dbo"}


def _server_schema(form: dict, source_type: str) -> str:
    """schema do servidor (o ODCS exige em postgres e sqlserver): informado > prefixo da tabela > padrão do banco."""
    if source_type not in _DEFAULT_SCHEMA:
        return ""
    physical = str(form.get("physicalName") or "")
    return (str(form.get("schema") or "").strip() or (physical.split(".")[0] if "." in physical else "")
            or _DEFAULT_SCHEMA[source_type])


def contracts_from_ddl(ddl: str, form: dict, servers: list[dict]) -> list[dict]:
    """DDL com uma ou várias tabelas → um data contract por tabela, com as FKs em relationships.

    As FKs apontam para tabela.coluna de outro contrato (validadas entre os contratos gerados).
    Tabela sem coluna de data na origem vira carga full; com data, incremental pela primeira coluna de data.
    """
    source_type = form.get("sourceType", "postgres")
    ddl = read_schema(ddl)
    contracts = []
    for name in ddl_tables(ddl):
        table_form, rows = columns_from_ddl(ddl, source_type, name)
        incremental = [r["name"] for r in rows if r["partitioned"]]
        merged = {**empty_form(), **form, **table_form, "loadMode": "incremental" if incremental else "full",
                  "incrementalColumns": incremental}
        contract = build_contract(merged, servers, rows)
        load_contract(dump_contract(contract))  # valida a estrutura de cada um
        contracts.append(contract)
    check_relationships(contracts)
    return contracts


def _quality_rules(rules, cols: list[dict]) -> tuple[list[dict], dict[str, list[dict]]]:
    """Regras da tela → (quality da tabela, quality por coluna) no formato ODCS.

    "Sem duplicados" sem coluna escolhida usa a chave primária. Colunas que não existem mais são ignoradas.
    """
    names = {str(c["name"]).strip() for c in cols}
    pk_cols = [str(c["name"]).strip() for c in cols if c.get("primaryKey")]
    table_q: list[dict] = []
    column_q: dict[str, list[dict]] = {}
    for r in default_quality() if rules is None else rules:
        kind = r.get("rule")
        severity = "warning" if r.get("severity") == "warning" else "error"
        chosen = [c for c in r.get("columns") or [] if c in names]
        if kind == "notNull":
            for c in chosen:
                column_q.setdefault(c, []).append({"metric": "nullValues", "mustBe": 0, "severity": severity,
                                                   "description": "Não pode vir nulo"})
        elif kind == "unique" and (chosen or pk_cols):
            table_q.append({"metric": "duplicateValues", "mustBe": 0, "severity": severity,
                            "description": "Sem duplicados" + ("" if chosen else " na chave"),
                            "arguments": {"properties": chosen or pk_cols}})
        elif kind == "rowCount":
            low = r.get("min")
            low = 1 if low is None or (isinstance(low, float) and low != low) else int(low)
            table_q.append({"metric": "rowCount", "mustBeGreaterOrEqualTo": low, "severity": severity,
                            "description": f"Pelo menos {low} linha(s) na carga"})
    return table_q, column_q


def build_contract(form: dict, servers: list[dict], columns: list[dict], naming: dict[str, dict] | None = None) -> dict:
    """Monta o data contract ODCS. naming: coluna → {staging_field, comment} revisados na etapa 2."""
    naming = naming or {}
    dataset = str(form.get("dataset", "")).strip().lower()
    table = str(form.get("table", "")).strip()
    source_type = form.get("sourceType", "postgres")
    cols = [c for c in columns if str(c.get("name") or "").strip()]

    contract_servers = []
    for s in servers:
        env = str(s.get("environment") or "").strip()
        if not env:
            continue
        db_key = "serviceName" if source_type == "oracle" else "database"
        contract_servers.append(_clean({
            "server": f"{dataset or 'origem'}-{env}", "environment": env, "type": source_type,
            "host": str(s.get("host") or "").strip(), "port": _port(s.get("port")),
            db_key: str(s.get("database") or "").strip(),
            "schema": _server_schema(form, source_type),
            "customProperties": _props({"secretId": str(s.get("secretId") or "").strip()}),
        }))

    quality, column_quality = _quality_rules(form.get("quality"), cols)

    pk_pos = 0
    properties = []
    for c in cols:
        name = str(c["name"]).strip()
        review = naming.get(name, {})
        pk = bool(c.get("primaryKey"))
        if pk:
            pk_pos += 1
        properties.append(_clean({
            "name": name,
            "logicalType": c.get("logicalType") or "string",
            "physicalType": str(c.get("physicalType") or "").strip(),
            "primaryKey": pk or None, "primaryKeyPosition": pk_pos if pk else None,
            "required": bool(c.get("required")) or pk or None,
            "partitioned": bool(c.get("partitioned")) or None,
            "partitionKeyPosition": 1 if c.get("partitioned") else None,
            "description": (review.get("comment") or c.get("description") or "").strip(),
            "classification": "restricted" if c.get("encrypt") else None,
            "quality": column_quality.get(name),
            "relationships": [{"type": "foreignKey", "to": str(c["references"]).strip()}]
            if str(c.get("references") or "").strip() else None,
            "customProperties": _props({
                "encrypt": bool(c.get("encrypt")),
                "stagingName": (review.get("staging_field") or c.get("stagingName") or "").strip(),
            }),
        }))

    encrypt = any(c.get("encrypt") for c in cols)
    table_props = _props({
        "loadMode": form.get("loadMode"),
        "incrementalColumns": [c for c in form.get("incrementalColumns") or [] if c],
        "fetchSize": int(form.get("fetchSize") or 150000) if int(form.get("fetchSize") or 150000) != 150000 else None,
        "numQueriesParallel": int(form.get("numQueriesParallel") or 1) if int(form.get("numQueriesParallel") or 1) > 1 else None,
        "rawPartitionColumn": str(form.get("rawPartitionColumn") or "").strip(),
        "rawDatabase": str(form.get("rawDatabase") or "").strip(),
        "cryptographySecretArn": str(form.get("cryptographySecretArn") or "").strip() if encrypt else "",
    })

    contract = _clean({
        "apiVersion": ODCS_VERSION, "kind": "DataContract", "id": form.get("id") or str(uuid.uuid4()),
        "name": f"{dataset}-{table}" if dataset and table else "", "version": form.get("version") or "1.0.0",
        "status": "draft", "domain": str(form.get("domain") or "").strip(), "dataProduct": dataset,
        "description": _clean({"purpose": str(form.get("description") or "").strip()}),
        "team": {"name": "dono-do-dado", "members": [{"username": form["owner"].strip(), "role": "owner"}]}
        if str(form.get("owner") or "").strip() else None,
        "servers": contract_servers,
        "schema": [_clean({
            "name": table, "physicalName": str(form.get("physicalName") or "").strip(), "physicalType": "table",
            "description": str(form.get("description") or "").strip(),
            "customProperties": table_props, "properties": properties, "quality": quality,
        })],
        "customProperties": _props({"githubOrg": str(form.get("githubOrg") or "").strip(),
                                    "transformationLanguage": form.get("transformationLanguage") or "pyspark"}),
    })
    return contract


def dump_contract(contract: dict) -> str:
    return yaml.safe_dump(contract, sort_keys=False, allow_unicode=True, width=120)


# ── Etapa 2: nomenclatura ──────────────────────────────────────────────

def _state(contract_text: str, llm_model: str = "", naming_dir: str = "", dry_run: bool = True) -> dict:
    return _initial_state(None, None, None, None, llm_model or "", naming_dir, dry_run, contract_text=contract_text)


@dataclass
class NamingResult:
    rows: list[dict]
    source: str
    warnings: list[str] = field(default_factory=list)


def propose_naming(contract_text: str, llm_model: str = "") -> NamingResult:
    """Roda profiler + nomenclatura (sem gravar nada) e devolve as linhas para revisão."""
    from datapacto.agents.naming import naming_agent
    from datapacto.agents.profiler import profiler_agent

    state = _state(contract_text, llm_model)
    with contextlib.redirect_stdout(io.StringIO()):
        state.update(profiler_agent(state))
        state.update(naming_agent(state))
    rows = [{
        "raw_field": f["raw_field"], "data_type": f["data_type"], "staging_field": f["staging_field"],
        "comment": f["comment"], "primaryKey": f["is_pk"], "encrypt": bool(f.get("encrypt")),
    } for f in state["schema"]["fields"]]
    return NamingResult(rows, state.get("naming_source", ""), list(state.get("naming_warnings") or []))


def naming_map(rows: list[dict]) -> dict[str, dict]:
    return {r["raw_field"]: {"staging_field": str(r.get("staging_field") or "").strip().lower(),
                             "comment": str(r.get("comment") or "").strip()} for r in rows}


# ── Etapa 3: validação ─────────────────────────────────────────────────

@dataclass
class Check:
    level: str   # ok | warning | error
    title: str
    detail: str = ""
    target: str = ""  # campo a corrigir (chave do formulário, "columns", "servers" ou "naming")


@dataclass
class ValidationResult:
    checks: list[Check]
    files: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not any(c.level == "error" for c in self.checks)


def health_checks(contract: dict) -> list[Check]:
    """Conferências rápidas do formulário (sem gerar nada): alimentam a saúde do contrato e a validação."""
    checks: list[Check] = []
    table = (contract.get("schema") or [{}])[0]
    props = table.get("properties") or []
    tp = custom_props(table)

    def need(cond: bool, title: str, detail: str, target: str, level: str = "error"):
        checks.append(Check("ok" if cond else level, title, "" if cond else detail, target))

    need(bool(contract.get("dataProduct")), "Dataset informado", "Preencha o dataset na etapa 1.", "dataset")
    need(bool(table.get("name")), "Tabela informada", "Preencha o nome da tabela.", "table")
    need(bool(props), "Colunas informadas", "Adicione as colunas (importe a DDL ou digite).", "columns")
    need(any(p.get("primaryKey") for p in props), "Chave primária marcada",
         "Marque ao menos uma coluna como chave: ela é a chave do MERGE na transformação.", "columns")
    partitioned = [p["name"] for p in props if p.get("partitioned")]
    need(len(partitioned) <= 1, "No máximo uma coluna incremental", f"Marcadas: {', '.join(partitioned)}.", "columns")
    if tp.get("loadMode") == "incremental":
        need(len(partitioned) == 1, "Coluna incremental marcada",
             "Carga incremental precisa de uma coluna de data marcada como incremental (ou use carga full).", "columns")
    servers = contract.get("servers") or []
    need(bool(servers), "Servidor de origem", "Informe ao menos um ambiente (dev, hml ou prd).", "servers")
    for s in servers:
        need(bool(custom_props(s).get("secretId")), f"Secret do ambiente {s.get('environment')}",
             "Informe o ID/ARN da secret com usuário e senha.", "servers")
        need(bool(s.get("host")), f"Host do ambiente {s.get('environment')}",
             "Sem host no contrato: ele precisa estar na secret (host ou url).", "servers", level="warning")
    need(bool(tp.get("rawPartitionColumn")), "Coluna de partição da raw", "Informe a coluna de partição da raw.", "rawPartitionColumn")
    if any(str(custom_props(p).get("encrypt")).lower() == "true" for p in props):
        need(bool(tp.get("cryptographySecretArn")), "Chave de criptografia",
             "Há coluna criptografada: informe o ARN da secret com a chave AES.", "cryptographySecretArn")
    return checks


def cross_table_checks(contracts: list[dict]) -> list[Check]:
    """Conferências entre as tabelas: nomes repetidos e chaves estrangeiras que apontam para outra tabela."""
    names = [str((c.get("schema") or [{}])[0].get("name") or "").lower() for c in contracts]
    repeated = sorted({n for n in names if n and names.count(n) > 1})
    checks = [Check("error" if repeated else "ok", "Uma tabela de cada nome",
                    f"Repetidas: {', '.join(repeated)}." if repeated else "", "table")]
    try:
        check_relationships(contracts)
        checks.append(Check("ok", "Chaves estrangeiras entre as tabelas"))
    except (ValueError, KeyError) as e:
        checks.append(Check("error", "Chaves estrangeiras entre as tabelas", str(e), "columns"))
    return checks


def validate(contract: dict) -> ValidationResult:
    """Checklist da etapa 3 + simulação da geração (nada é gravado)."""
    from datapacto.agents.input_gen import input_gen_agent
    from datapacto.agents.naming import naming_agent
    from datapacto.agents.profiler import profiler_agent
    from datapacto.agents.transform_gen import transform_gen_agent

    text = dump_contract(contract)
    checks: list[Check] = []
    try:
        load_contract(text)
        checks.append(Check("ok", "Estrutura do data contract (ODCS)"))
    except ValueError as e:
        return ValidationResult([Check("error", "Estrutura do data contract (ODCS)", str(e))])

    checks += health_checks(contract)
    if any(c.level == "error" for c in checks):
        return ValidationResult(checks)

    files: dict[str, str] = {}
    try:
        state = _state(text)
        state["transform_files"] = {}
        with contextlib.redirect_stdout(io.StringIO()):
            state.update(profiler_agent(state))
            state.update(naming_agent(state))

            fields = state["schema"]["fields"]
            names = {f["raw_field"]: {"staging_field": f["staging_field"], "comment": f["comment"]} for f in fields}
            errors, _ = validate_naming(fields, names)
            state.update(input_gen_agent(state))
            files.update(state["input_files"])
            files.update(transform_gen_agent(state)["transform_files"])
    except Exception as e:  # noqa: BLE001 — mostra o motivo na tela
        checks.append(Check("error", "Simulação da geração", str(e)))
        return ValidationResult(checks)

    if errors:
        detail = "; ".join(f"{e['raw_field']}: {e['message']}" for e in errors)
        checks.append(Check("error", "Padrão de nomenclatura", detail, "naming"))
    else:
        checks.append(Check("ok", "Padrão de nomenclatura", ""))

    ingestion = yaml.safe_load(next(iter(state["input_files"].values())))
    pending = placeholders(ingestion)
    checks.append(Check("warning" if pending else "ok", "ingestion.yml completo",
                        f"Campos sem valor: {', '.join(pending)}" if pending else ""))
    checks.append(Check("ok", "Simulação da geração", f"{len(files)} arquivos"))
    return ValidationResult(checks, files)


# ── Etapa 4: geração ───────────────────────────────────────────────────

OUTPUT_DIR_ENV = "DL_OUTPUT_DIR"


def default_output_dir() -> str:
    """Pasta usada quando nenhuma é informada: $DL_OUTPUT_DIR > C:/temp_tables (Windows) > ~/temp_tables."""
    return os.getenv(OUTPUT_DIR_ENV) or (r"C:\temp_tables" if os.name == "nt" else str(Path.home() / "temp_tables"))


@dataclass
class GenerationResult:
    output_dir: Path
    contract_path: Path
    files: list[str]
    log: str
    published: list[str] = field(default_factory=list)


def generate_all(contracts: list[dict], output_dir: str, llm_model: str = "",
                 publish_s3: str = "") -> list[GenerationResult]:
    """Gera várias tabelas: cada uma tem seu contrato e ingestion.yml; a transformação é um projeto só."""
    return [generate(c, output_dir, llm_model, publish_s3, append=i > 0) for i, c in enumerate(contracts)]


def generate(contract: dict, output_dir: str, llm_model: str = "", publish_s3: str = "",
             append: bool = False) -> GenerationResult:
    """Grava o contrato em contracts/<dataset>/<tabela>.odcs.yaml e gera ingestion.yml + transformação.

    output_dir vazio = default_output_dir(). append: acrescenta a tabela ao projeto de transformação que já
    está na pasta (como o --append da linha de comando).
    """
    from datapacto.graph import run_pipeline

    out = Path(str(output_dir or "").strip() or default_output_dir()).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    text = dump_contract(contract)
    table = contract["schema"][0]["name"]
    contract_path = out / "contracts" / contract["dataProduct"] / f"{table}.odcs.yaml"
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(text, encoding="utf-8")

    state = _state(text, llm_model, naming_dir=str(out / "naming"), dry_run=False)
    state["output_dir"] = str(out)
    project = f"{state['dataset']}-transformation"
    if append and (out / project).exists():
        pattern = "*.scala" if state["language"] == "scala" else "*.py"
        state["transform_files"] = {f.relative_to(out).as_posix(): f.read_text(encoding="utf-8")
                                    for f in (out / project).rglob(pattern)}
        state["transform_project_dir"] = project
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        final = run_pipeline(state)

    published = []
    if publish_s3:
        from datapacto.publish import publish_to_s3
        for rel, content in final.get("input_files", {}).items():
            published.append(publish_to_s3(publish_s3, rel, content))

    files = sorted({**final.get("input_files", {}), **final.get("transform_files", {})})
    return GenerationResult(out, contract_path, files, buffer.getvalue(), published)
