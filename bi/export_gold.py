from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data/gold/cnmv.duckdb"
DEFAULT_OUT = ROOT / "data/exports/gold_bi"

PREFIXES = ("dim_", "fact_", "mart_", "meta_")
EXCLUDED = {
    "quarantine_nav_daily",
    "known_data_issues",
    "vocacion_family",
    "vocation_aliases",
}


def bi_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    rows = con.execute(
        """
        select table_name
        from information_schema.tables
        where table_schema = 'main' and table_type = 'BASE TABLE'
        order by table_name
        """
    ).fetchall()
    return [
        name for (name,) in rows if name.startswith(PREFIXES) and name not in EXCLUDED
    ]


def run_meta(con: duckdb.DuckDBPyConnection, tables: list[str]) -> dict | None:
    if "meta_run" not in tables:
        return None
    row = con.execute(
        'select as_of_period, cast(as_of_month_start_date as varchar), cast(built_at as varchar) from main."meta_run" limit 1'
    ).fetchone()
    if not row:
        return None
    return {
        "as_of_period": row[0],
        "as_of_month_start_date": row[1],
        "built_at": row[2],
    }


def hidden_columns(columns: list[str]) -> list[str]:
    """Columns to hide in the Power BI model: relationship and natural keys."""
    return [c for c in columns if c.endswith(("_id", "_key"))]


def export_table(con: duckdb.DuckDBPyConnection, table: str, out_dir: Path) -> dict:
    dest = out_dir / f"{table}.parquet"
    dest_sql = str(dest).replace("'", "''")
    con.execute(
        f"copy (select * from main.\"{table}\") to '{dest_sql}' "
        "(format parquet, compression zstd)"
    )
    rows = con.execute(f'select count(*) from main."{table}"').fetchone()[0]
    columns = [
        r[0] for r in con.execute(f'describe select * from main."{table}"').fetchall()
    ]
    return {
        "rows": rows,
        "bytes": dest.stat().st_size,
        "columns": columns,
        "hidden_columns": hidden_columns(columns),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Gold BI tables to Parquet")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    con = duckdb.connect(str(args.db), read_only=True)
    tables = bi_tables(con)
    args.out.mkdir(parents=True, exist_ok=True)

    manifest: dict = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "source_db": str(args.db),
        "run": run_meta(con, tables),
        "tables": {},
    }

    for table in tables:
        manifest["tables"][table] = export_table(con, table, args.out)
        print(f"{table}: {manifest['tables'][table]['rows']} rows")

    expected = {f"{table}.parquet" for table in tables}
    for stale in args.out.glob("*.parquet"):
        if stale.name not in expected:
            stale.unlink()

    (args.out / "_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    con.close()
    print(f"manifest: {args.out / '_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
