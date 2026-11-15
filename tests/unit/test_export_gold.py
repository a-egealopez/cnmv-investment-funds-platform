import json

import pytest

from bi.export_gold import hidden_columns, main


def test_hides_relationship_and_natural_keys():
    cols = ["class_id", "class_key", "date_key", "display_name", "aum", "isin"]
    assert hidden_columns(cols) == ["class_id", "class_key", "date_key"]


def test_manifest_lists_hidden_columns(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    db = tmp_path / "gold.duckdb"
    con = duckdb.connect(str(db))
    con.execute("create table dim_class as select 1 as class_id, 'a' as display_name")
    con.execute(
        "create table meta_run as select '202605' as as_of_period, "
        "date '2026-05-01' as as_of_month_start_date, current_timestamp as built_at"
    )
    con.close()

    out = tmp_path / "out"
    assert main(["--db", str(db), "--out", str(out)]) == 0

    manifest = json.loads((out / "_manifest.json").read_text())
    table = manifest["tables"]["dim_class"]
    assert table["columns"] == ["class_id", "display_name"]
    assert table["hidden_columns"] == ["class_id"]


def test_child_dimension_drops_attributes_repeated_from_parent(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    db = tmp_path / "gold.duckdb"
    con = duckdb.connect(str(db))
    con.execute(
        "create table dim_compartment as select 7 as compartment_id, "
        "'F' as fund_name, 'RF' as vocation, 'Fund F' as display_name"
    )
    con.execute(
        "create table dim_class as select 1 as class_id, 7 as compartment_id, "
        "'A' as class_name, 'F' as fund_name, 'RF' as vocation, 'F · A' as display_name"
    )
    con.close()

    out = tmp_path / "out"
    assert main(["--db", str(db), "--out", str(out)]) == 0

    manifest = json.loads((out / "_manifest.json").read_text())
    dim_class = manifest["tables"]["dim_class"]
    # Keeps its own columns and the key to its parent; the parent's attributes go
    assert dim_class["columns"] == [
        "class_id",
        "compartment_id",
        "class_name",
        "display_name",
    ]
    assert dim_class["dropped_columns"] == ["fund_name", "vocation"]

    con = duckdb.connect()
    exported = con.execute(
        f"describe select * from '{out / 'dim_class.parquet'}'"
    ).fetchall()
    assert [r[0] for r in exported] == dim_class["columns"]
    # The parent dimension itself is exported whole
    assert manifest["tables"]["dim_compartment"]["dropped_columns"] == []
