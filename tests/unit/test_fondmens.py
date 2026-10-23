from datetime import date
from decimal import Decimal

import pytest
from pyspark.sql.types import StringType, StructField, StructType

from spark.parsing.fondmens import (
    parse_fondmens_xml,
    validate_schema,
    write_silver,
)


def _clase(numero, isin, ndays=31):
    days = range(1, ndays + 1)
    vl = "\n".join(f"<VL_Dia{d}>{d}</VL_Dia{d}>" for d in days)
    part = "\n".join(f"<Participes_Dia{d}>{1000 + d}</Participes_Dia{d}>" for d in days)
    pat = "\n".join(f"<Patrimonio_Dia{d}>{d * 1000}</Patrimonio_Dia{d}>" for d in days)
    return f"""<Clase>
  <NumeroClase>{numero}</NumeroClase>
  <ISIN>{isin}</ISIN>
  <VLDiario>{vl}</VLDiario>
  <ParticipesDiario>{part}</ParticipesDiario>
  <PatrimonioDiario>{pat}</PatrimonioDiario>
</Clase>"""


def _compartimento(numero, clases):
    return f"""<Compartimento>
  <NumeroCompartimento>{numero}</NumeroCompartimento>
  {"".join(clases)}
</Compartimento>"""


def _entidad(registro, compartimentos):
    return f"""<Entidad>
  <Tipo>FI</Tipo>
  <NumeroRegistro>{registro}</NumeroRegistro>
  {"".join(compartimentos)}
</Entidad>"""


def _write_xml(tmp_path, fecha, entidades, name="fondmens.xml"):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<FondMens>
  <FechaDatos>{fecha}</FechaDatos>
  {"".join(entidades)}
</FondMens>"""
    path = tmp_path / name
    path.write_text(xml, encoding="utf-8")
    return str(path)


@pytest.fixture
def sample_xml(tmp_path):
    # 2 entities, 4 classes, January 2026 (real YYYYMM format)
    entidades = [
        _entidad(
            1234,
            [
                _compartimento(
                    1, [_clase(1, "ES0000000001"), _clase(2, "ES0000000002")]
                ),
                _compartimento(2, [_clase(1, "ES0000000003")]),
            ],
        ),
        _entidad(
            5678,
            [
                _compartimento(1, [_clase(1, "ES0000000004")]),
            ],
        ),
    ]
    return _write_xml(tmp_path, "202601", entidades)


def test_columns(spark, sample_xml):
    df = parse_fondmens_xml(spark, sample_xml)
    assert set(df.columns) == {
        "FechaDatos",
        "Tipo",
        "NumeroRegistro",
        "NumeroCompartimento",
        "NumeroClase",
        "ISIN",
        "value_date",
        "VL",
        "Participes",
        "Patrimonio",
    }


def test_exact_row_count(spark, sample_xml):
    df = parse_fondmens_xml(spark, sample_xml)
    assert df.count() == 4 * 31


def test_values_aligned_with_day(spark, sample_xml):
    # A misaligned stack would break VL == day number
    df = parse_fondmens_xml(spark, sample_xml)
    rows = df.filter("value_date = '2026-01-15' AND ISIN = 'ES0000000001'").collect()
    assert len(rows) == 1
    assert rows[0].VL == Decimal(15)
    assert rows[0].Participes == 1015
    assert rows[0].Patrimonio == Decimal(15000)


def test_value_date_range(spark, sample_xml):
    df = parse_fondmens_xml(spark, sample_xml)
    dates = {r.value_date for r in df.select("value_date").distinct().collect()}
    assert min(dates) == date(2026, 1, 1)
    assert max(dates) == date(2026, 1, 31)
    assert len(dates) == 31


def test_short_month_has_no_extra_rows(spark, tmp_path):
    # February 2026 has 28 days
    path = _write_xml(
        tmp_path,
        "202602",
        [
            _entidad(1234, [_compartimento(1, [_clase(1, "ES0000000001", ndays=28)])]),
        ],
    )
    df = parse_fondmens_xml(spark, path)
    assert df.count() == 28
    assert df.agg({"value_date": "max"}).collect()[0][0] == date(2026, 2, 28)


def test_single_entity_single_class(spark, tmp_path):
    # Single elements must still be parsed as arrays
    path = _write_xml(
        tmp_path,
        "202601",
        [
            _entidad(1234, [_compartimento(1, [_clase(1, "ES0000000001")])]),
        ],
    )
    df = parse_fondmens_xml(spark, path)
    assert df.count() == 31


def test_validate_schema_valid(spark, sample_xml):
    validate_schema(parse_fondmens_xml(spark, sample_xml))


def test_validate_schema_invalid(spark):
    bad_df = spark.createDataFrame(
        [], StructType([StructField("wrong_col", StringType(), True)])
    )
    with pytest.raises(AssertionError, match="Schema mismatch"):
        validate_schema(bad_df)


def test_write_silver_roundtrip_and_partitions(spark, sample_xml, tmp_path):
    out = str(tmp_path / "silver")
    df = parse_fondmens_xml(spark, sample_xml)
    write_silver(df, out)
    assert (tmp_path / "silver" / "FechaDatos=202601").is_dir()
    assert spark.read.parquet(out).count() == df.count()


def test_write_silver_is_idempotent_and_keeps_other_periods(spark, tmp_path):
    out = str(tmp_path / "silver")

    def entities(ndays):
        return [
            _entidad(1, [_compartimento(1, [_clase(1, "ES0000000001", ndays=ndays)])])
        ]

    jan = parse_fondmens_xml(
        spark, _write_xml(tmp_path, "202601", entities(31), "jan.xml")
    )
    feb = parse_fondmens_xml(
        spark, _write_xml(tmp_path, "202602", entities(28), "feb.xml")
    )

    write_silver(jan, out)
    write_silver(feb, out)
    write_silver(jan, out)  # rerun January

    result = spark.read.parquet(out)
    assert (
        result.filter("FechaDatos = '202601'").count() == jan.count()
    )  # no duplicates
    assert (
        result.filter("FechaDatos = '202602'").count() == feb.count()
    )  # not overwritten
