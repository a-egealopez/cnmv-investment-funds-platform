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
