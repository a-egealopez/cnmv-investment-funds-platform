from datetime import date
from decimal import Decimal

import pytest
from pyspark.sql.types import StringType, StructField, StructType

from spark.parsing.estr import (
    EXPECTED_SCHEMA,
    parse_estr_csv,
    validate_schema,
    write_silver,
)


def _csv(key, rows, name="estr.csv"):
    lines = ["KEY,FREQ,BENCHMARK_ITEM,DATA_TYPE_EST,TIME_PERIOD,OBS_VALUE,OBS_STATUS"]
    for tp, value, status in rows:
        lines.append(f"{key},B,EU000A2QQF16,CR,{tp},{value},{status}")
    return "\n".join(lines) + "\n"


def _write(tmp_path, files: dict[str, str]):
    out = []
    for name, content in files.items():
        path = tmp_path / name
        path.write_text(content, encoding="utf-8")
        out.append(str(path))
    return out


@pytest.fixture
def parsed(spark, tmp_path):
    paths = _write(
        tmp_path,
        {
            "estr_cr.csv": _csv(
                "EST.B.EU000A2QQF16.CR",
                [
                    ("2026-05-05", "2.44057", "A"),
                    ("2026-05-06", "not-a-number", "A"),
                    ("2026-05-07", "2.47085", ""),
                ],
            ),
            "estr_ci.csv": _csv(
                "EST.B.EU000A2QQF08.CI",
                [("2026-05-05", "110.03236357", "A")],
            ),
        },
    )
    return parse_estr_csv(spark, paths)


def test_columns_and_types(parsed):
    assert set(parsed.columns) == {"series", "value_date", "obs_value", "obs_status"}


def test_long_format_and_values(parsed):
    rows = parsed.orderBy("series", "value_date").collect()
    assert len(rows) == 4
    first = rows[0]
    assert first.series == "EST.B.EU000A2QQF08.CI"
    assert first.value_date == date(2026, 5, 5)
    assert first.obs_value == Decimal("110.03236357")


def test_malformed_value_and_blank_status(parsed):
    rows = {r.value_date: r for r in parsed.collect()}
    assert rows[date(2026, 5, 6)].obs_value is None
    assert rows[date(2026, 5, 7)].obs_status is None


def test_validate_schema_valid(spark, tmp_path):
    paths = _write(
        tmp_path,
        {"estr_cr.csv": _csv("EST.B.EU000A2QQF16.CR", [("2026-05-05", "2.44", "A")])},
    )
    validate_schema(parse_estr_csv(spark, paths))


def test_validate_schema_invalid(spark):
    bad_df = spark.createDataFrame(
        [], StructType([StructField("wrong_col", StringType(), True)])
    )
    with pytest.raises(AssertionError, match="Schema mismatch"):
        validate_schema(bad_df)


def test_write_silver_roundtrip_no_partitions(spark, tmp_path):
    paths = _write(
        tmp_path,
        {"estr_cr.csv": _csv("EST.B.EU000A2QQF16.CR", [("2026-05-05", "2.44", "A")])},
    )
    df = parse_estr_csv(spark, paths)
    out = str(tmp_path / "silver")
    write_silver(df, out)
    assert not [d for d in (tmp_path / "silver").glob("*=*")]  # no hive partitions
    assert spark.read.parquet(out).count() == 1


def test_write_silver_overwrite_is_idempotent(spark, tmp_path):
    paths = _write(
        tmp_path,
        {"estr_cr.csv": _csv("EST.B.EU000A2QQF16.CR", [("2026-05-05", "2.44", "A")])},
    )
    df = parse_estr_csv(spark, paths)
    out = str(tmp_path / "silver")
    write_silver(df, out)
    write_silver(df, out)
    assert spark.read.parquet(out).count() == 1


def test_expected_schema_contract():
    names = [f.name for f in EXPECTED_SCHEMA.fields]
    assert names == ["series", "value_date", "obs_value", "obs_status"]
