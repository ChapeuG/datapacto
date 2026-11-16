"""Lógica da interface (framework.ui.service): formulário → contrato → nomenclatura → validação → geração."""

from __future__ import annotations

from pathlib import Path

import yaml

from framework.parsers.contract_parser import custom_props, load_contract, resolve_table
from framework.ui import service

DDL = """
CREATE TABLE public.cliente (
    id          INTEGER PRIMARY KEY,
    nu_cpf      VARCHAR(11),
    nome        VARCHAR(100) NOT NULL,
    created_at  TIMESTAMP NOT NULL,
    updated_at  TIMESTAMP
);
"""


def _filled():
    form, rows = service.columns_from_ddl(DDL)
    f = {**service.empty_form(), **form, "dataset": "vendas",
         "rawPartitionColumn": "dt_ingestao", "incrementalColumns": ["updated_at"],
         "cryptographySecretArn": "arn:crypto"}
    for r in rows:
        r["encrypt"] = r["name"] == "nu_cpf"
    servers = [{"environment": "prd", "host": "db", "port": 5432.0, "database": "crm", "secretId": "arn:secret"}]
    return f, servers, rows


def test_columns_from_ddl():
    form, rows = service.columns_from_ddl(DDL)
    assert form == {"table": "cliente", "physicalName": "public.cliente", "description": ""}
    by = {r["name"]: r for r in rows}
    assert by["id"]["primaryKey"] and by["id"]["logicalType"] == "integer"
    assert by["created_at"]["partitioned"]  # candidato a coluna incremental
    assert by["nome"]["required"] and not by["nu_cpf"]["required"]


def test_build_contract_is_valid_odcs_and_resolves():
    form, servers, rows = _filled()
    contract = service.build_contract(form, servers, rows)
    ct = resolve_table(load_contract(service.dump_contract(contract)))
    assert (ct.dataset, ct.source_db, ct.partition_col) == ("vendas", "postgres", "created_at")
    assert ct.merge_keys == ["id"] and ct.encrypt_columns == ["nu_cpf"]
    assert contract["servers"][0]["port"] == 5432 and custom_props(contract["servers"][0])["secretId"] == "arn:secret"
    tp = custom_props(contract["schema"][0])
    assert tp["incrementalColumns"] == ["updated_at"] and tp["rawPartitionColumn"] == "dt_ingestao"
    assert [q["metric"] for q in contract["schema"][0]["quality"]] == ["duplicateValues", "rowCount"]


def test_odcs_schema_if_available():
    """Confere com o JSON Schema oficial quando ele estiver em cache local (sem rede no teste)."""
    import json
    import os

    path = os.environ.get("ODCS_SCHEMA")
    if not path or not Path(path).exists():
        return
    import jsonschema
    schema = json.loads(Path(path).read_text(encoding="utf-8"))
    form, servers, rows = _filled()
    errors = list(jsonschema.validators.validator_for(schema)(schema).iter_errors(service.build_contract(form, servers, rows)))
    assert errors == []


def test_naming_proposal_and_edit_roundtrip():
    form, servers, rows = _filled()
    text = service.dump_contract(service.build_contract(form, servers, rows))
    result = service.propose_naming(text)
    assert result.source == "heuristica"
    by = {r["raw_field"]: r for r in result.rows}
    assert by["nu_cpf"]["encrypt"] and by["id"]["primaryKey"]

    by["nome"]["staging_field"] = "nm_cliente"
    by["nome"]["comment"] = "Nome do cliente"
    contract = service.build_contract(form, servers, rows, service.naming_map(result.rows))
    prop = next(p for p in contract["schema"][0]["properties"] if p["name"] == "nome")
    assert custom_props(prop)["stagingName"] == "nm_cliente" and prop["description"] == "Nome do cliente"
    # a próxima proposta respeita o que foi editado
    again = {r["raw_field"]: r for r in service.propose_naming(service.dump_contract(contract)).rows}
    assert again["nome"]["staging_field"] == "nm_cliente"


def test_form_from_contract_roundtrip():
    form, servers, rows = _filled()
    text = service.dump_contract(service.build_contract(form, servers, rows))
    form2, servers2, rows2 = service.form_from_contract(text)
    assert form2["dataset"] == "vendas" and form2["rawPartitionColumn"] == "dt_ingestao"
    assert servers2[0]["secretId"] == "arn:secret"
    assert [r["name"] for r in rows2] == [r["name"] for r in rows]
    assert next(r for r in rows2 if r["name"] == "nu_cpf")["encrypt"] is True


def test_validation_ok_and_previews():
    form, servers, rows = _filled()
    v = service.validate(service.build_contract(form, servers, rows))
    assert v.ok, [c for c in v.checks if c.level == "error"]
    assert "ingestion-config/vendas/cliente.ingestion.yml" in v.files
    assert any(k.startswith("vendas-transformation/") for k in v.files)


def test_validation_reports_missing_fields():
    form, servers, rows = _filled()
    form["rawPartitionColumn"] = ""
    servers[0]["secretId"] = ""
    for r in rows:
        r["primaryKey"] = False
    v = service.validate(service.build_contract(form, servers, rows))
    errors = {c.title for c in v.checks if c.level == "error"}
    assert {"Chave primária marcada", "Secret do ambiente prd", "Coluna de partição da raw"} <= errors
    assert not v.ok and v.files == {}


def test_validation_reports_naming_violation():
    form, servers, rows = _filled()
    contract = service.build_contract(form, servers, rows, {"nome": {"staging_field": "Nome Do Cliente", "comment": "x"}})
    v = service.validate(contract)
    naming = next(c for c in v.checks if c.title == "Padrão de nomenclatura")
    assert naming.level == "error" and "nome" in naming.detail


def test_generate_writes_everything(tmp_path):
    form, servers, rows = _filled()
    r = service.generate(service.build_contract(form, servers, rows), str(tmp_path))
    assert r.contract_path == tmp_path / "contracts" / "vendas" / "cliente.odcs.yaml"
    assert (tmp_path / "ingestion-config" / "vendas" / "cliente.ingestion.yml").exists()
    assert (tmp_path / "vendas-transformation" / "pyproject.toml").exists()
    assert (tmp_path / "naming" / "cliente.json").exists()
    cfg = yaml.safe_load((tmp_path / "ingestion-config" / "vendas" / "cliente.ingestion.yml").read_text(encoding="utf-8"))
    assert cfg["encryption"]["columns"] == ["nu_cpf"]


def test_generate_without_folder_uses_default(tmp_path, monkeypatch):
    monkeypatch.setenv(service.OUTPUT_DIR_ENV, str(tmp_path / "padrao"))
    form, servers, rows = _filled()
    r = service.generate(service.build_contract(form, servers, rows), "  ")
    assert r.output_dir == tmp_path / "padrao"
    assert (tmp_path / "padrao" / "contracts" / "vendas" / "cliente.odcs.yaml").exists()


def test_language_round_trips_through_contract(tmp_path):
    form, servers, rows = _filled()
    contract = service.build_contract({**form, "transformationLanguage": "scala"}, servers, rows)
    text = service.dump_contract(contract)
    assert "transformationLanguage" in text
    assert service.form_from_contract(text)[0]["transformationLanguage"] == "scala"
    r = service.generate(contract, str(tmp_path))
    assert (tmp_path / "vendas-transformation" / "build.sbt").exists()
    assert not (tmp_path / "vendas-transformation" / "main.py").exists()
    assert r.files


TWO_TABLES = DDL + """
CREATE TABLE public.pedido (
    id_pedido   INTEGER PRIMARY KEY,
    id_cliente  INTEGER REFERENCES public.cliente(id),
    vl_total    NUMERIC(12,2)
);
"""


def test_tables_from_ddl_reads_every_table():
    tables = service.tables_from_ddl(TWO_TABLES)
    assert [f["table"] for f, _ in tables] == ["cliente", "pedido"]
    assert tables[0][0]["loadMode"] == "incremental"  # tem coluna de data
    assert tables[1][0]["loadMode"] == "full"         # não tem
    assert tables[0][0]["id"] != tables[1][0]["id"]   # um contrato por tabela


def test_quality_rules_become_odcs_and_ingestion_checks():
    from framework.ingestion_config import _quality

    form, servers, rows = _filled()
    form["quality"] = [
        {"rule": "notNull", "columns": ["nome", "nu_cpf", "nao_existe"], "min": None, "severity": "error"},
        {"rule": "unique", "columns": [], "min": None, "severity": "error"},          # vazio = chave primária
        {"rule": "unique", "columns": ["nu_cpf"], "min": None, "severity": "warning"},
        {"rule": "rowCount", "columns": [], "min": 10, "severity": "warning"},
    ]
    contract = service.build_contract(form, servers, rows)
    load_contract(service.dump_contract(contract))  # continua ODCS válido
    table = contract["schema"][0]
    checks = _quality(table)
    assert {"check": "notNull", "columns": ["nome"], "severity": "error"} in checks
    assert {"check": "notNull", "columns": ["nu_cpf"], "severity": "error"} in checks
    assert {"check": "unique", "columns": ["id"], "severity": "error"} in checks
    assert {"check": "unique", "columns": ["nu_cpf"], "severity": "warning"} in checks
    assert {"check": "rowCount", "mustBeGreaterOrEqualTo": 10, "severity": "warning"} in checks
    assert not any("nao_existe" in c.get("columns", []) for c in checks)  # coluna que não existe é ignorada

    # e volta para a tela ao abrir o contrato
    back, _, _ = service.form_from_contract(service.dump_contract(contract))
    assert {"rule": "notNull", "columns": ["nu_cpf", "nome"], "min": None, "severity": "error"} in back["quality"] \
        or {"rule": "notNull", "columns": ["nome", "nu_cpf"], "min": None, "severity": "error"} in back["quality"]
    assert {"rule": "unique", "columns": [], "min": None, "severity": "error"} in back["quality"]
    assert {"rule": "rowCount", "columns": [], "min": 10, "severity": "warning"} in back["quality"]


def test_default_quality_for_new_tables():
    form, servers, rows = _filled()
    form.pop("quality")  # contrato antigo, sem regras na tela: vale o padrão
    quality = service.build_contract(form, servers, rows)["schema"][0]["quality"]
    assert [q["metric"] for q in quality] == ["duplicateValues", "rowCount"]


def test_cross_table_checks():
    form, servers, _ = _filled()
    contracts = [service.build_contract({**form, **f}, servers, rows) for f, rows in service.tables_from_ddl(TWO_TABLES)]
    assert all(c.level == "ok" for c in service.cross_table_checks(contracts))
    dup = service.cross_table_checks([contracts[0], contracts[0]])
    assert any(c.level == "error" and "cliente" in c.detail for c in dup)


def test_generate_all_puts_tables_in_one_project(tmp_path):
    form, servers, _ = _filled()
    contracts = [service.build_contract({**form, **f}, servers, rows) for f, rows in service.tables_from_ddl(TWO_TABLES)]
    results = service.generate_all(contracts, str(tmp_path))
    assert [r.contract_path.name for r in results] == ["cliente.odcs.yaml", "pedido.odcs.yaml"]
    for t in ("cliente", "pedido"):
        assert (tmp_path / "ingestion-config" / "vendas" / f"{t}.ingestion.yml").exists()
    project = "\n".join(p.as_posix() for p in (tmp_path / "vendas-transformation").rglob("*.py"))
    assert "cliente" in project and "pedido" in project  # as duas tabelas no mesmo projeto
