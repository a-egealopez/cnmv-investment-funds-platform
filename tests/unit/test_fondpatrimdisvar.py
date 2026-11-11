from decimal import Decimal

import pytest
from pyspark.sql.types import StringType, StructField, StructType

from spark.jobs.validate_silver import (
    FIN_FINDINGS,
    Report,
    check_fin_duplicate_keys,
    check_fin_negative_turnover,
    check_fin_nonpositive_patrimony,
    check_fin_period_months,
    run_artifact,
)
from spark.parsing.fondpatrimdisvar import (
    DECIMAL_FIELDS,
    EXPECTED_SCHEMA,
    parse_fondpatrimdisvar_xml,
    validate_schema,
    write_silver,
)

_DEFAULTS = {name: "0.00" for name in DECIMAL_FIELDS}
_DEFAULTS.update(
    {
        "IndiceRotacionCarteraActual": "0.01",
        "IndiceRotacionCarteraAnterior": "0.42",
        "TotalPatrimonio": "1000.00",
        "PatrimonioFinPeriodoAnterior": "900.00",
        "PatrimonioFinPeriodoActual": "1000.00",
    }
)


def _compartment(numero, omit=(), **overrides):
    values = {**_DEFAULTS, **overrides}
    tags = "".join(
        f"<{name}>{value}</{name}>"
        for name, value in values.items()
        if name not in omit and value is not None
    )
    return f"""<Compartimento>
  <NumeroCompartimento>{numero}</NumeroCompartimento>
  {tags}
</Compartimento>"""


def _entidad(registro, compartimentos, tipo="FI", divisa="EUR"):
    return f"""<Entidad>
  <Tipo>{tipo}</Tipo>
  <NumeroRegistro>{registro}</NumeroRegistro>
  <CodigoDivisaIIC>{divisa}</CodigoDivisaIIC>
  {"".join(compartimentos)}
</Entidad>"""


def _write_xml(tmp_path, fecha, entidades, name="fondpatrimdisvar.xml"):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<FondPatrimDisVar>
  <FechaDatos>{fecha}</FechaDatos>
  {"".join(entidades)}
</FondPatrimDisVar>"""
    path = tmp_path / name
    path.write_text(xml, encoding="utf-8")
    return str(path)


@pytest.fixture
def sample_xml(tmp_path):
    return _write_xml(
        tmp_path,
        "202512",
        [
            _entidad(
                9,
                [
                    _compartment(0),
                    _compartment(
                        1,
                        Suscripciones_Reembolsos_Netos="-4.88",
                        GastosRepercutidos="-1.00",
                        ComisionGestion="-0.95",
                        RendimientosGestion="3.15",
                        Ingresos="0.00",
                    ),
                ],
            ),
            _entidad(11, [_compartment(0, TotalPatrimonio="2500.00")]),
        ],
    )


@pytest.fixture
def parsed(spark, sample_xml):
    return parse_fondpatrimdisvar_xml(spark, sample_xml)


def _financials(spark, rows):
    return spark.createDataFrame(rows, schema=EXPECTED_SCHEMA)


def test_expected_schema_column_names():
    names = {f.name for f in EXPECTED_SCHEMA.fields}
    assert {
        "FechaDatos",
        "Tipo",
        "NumeroRegistro",
        "CodigoDivisaIIC",
        "NumeroCompartimento",
        "IndiceRotacionCarteraActual",
        "TotalPatrimonio",
        "Suscripciones_Reembolsos_Netos",
        "GastosRepercutidos",
        "RendimientosNetos",
        "PatrimonioFinPeriodoActual",
    } <= names


def test_grain_is_one_row_per_compartment(parsed):
    assert parsed.count() == 3
    assert (
        parsed.select("Tipo", "NumeroRegistro", "NumeroCompartimento", "FechaDatos")
        .distinct()
        .count()
        == 3
    )


def test_entity_fields_repeat_on_every_compartment_row(parsed):
    assert {r.CodigoDivisaIIC for r in parsed.collect()} == {"EUR"}
    assert {r.Tipo for r in parsed.collect()} == {"FI"}


def test_types_and_source_units_are_preserved(parsed):
    row = parsed.filter("NumeroRegistro = 9 AND NumeroCompartimento = 1").first()
    assert row.NumeroRegistro == 9
    assert isinstance(row.NumeroCompartimento, int)
    assert row.TotalPatrimonio == Decimal("1000.00")
    assert row.Suscripciones_Reembolsos_Netos == Decimal("-4.88")
    assert row.GastosRepercutidos == Decimal("-1.00")
    assert row.ComisionGestion == Decimal("-0.95")
    assert row.RendimientosGestion == Decimal("3.15")


def test_optional_fields_absent_yield_nulls(tmp_path, spark):
    path = _write_xml(
        tmp_path,
        "202509",
        [
            _entidad(
                1,
                [
                    _compartment(
                        0,
                        omit={
                            "IndiceRotacionCarteraAnterior",
                            "BeneficiosBrutosDistribuidos",
                            "ResultadosRentaFija",
                        },
                    )
                ],
            )
        ],
    )
    row = parse_fondpatrimdisvar_xml(spark, path).first()
    assert row.IndiceRotacionCarteraAnterior is None
    assert row.BeneficiosBrutosDistribuidos is None
    assert row.ResultadosRentaFija is None


def test_malformed_decimal_becomes_null_without_dropping_the_row(tmp_path, spark):
    path = _write_xml(
        tmp_path,
        "202503",
        [
            _entidad(
                1,
                [_compartment(0, RendimientosNetos="not-a-number")],
            )
        ],
    )
    df = parse_fondpatrimdisvar_xml(spark, path)
    assert df.count() == 1
    assert df.first().RendimientosNetos is None


def test_single_entity_single_compartment_without_arrays(tmp_path, spark):
    path = _write_xml(tmp_path, "202506", [_entidad(1, [_compartment(0)])])
    assert parse_fondpatrimdisvar_xml(spark, path).count() == 1


def test_validate_schema_valid(spark, sample_xml):
    validate_schema(parse_fondpatrimdisvar_xml(spark, sample_xml))


def test_validate_schema_invalid(spark):
    bad_df = spark.createDataFrame(
        [], StructType([StructField("wrong_col", StringType(), True)])
    )
    with pytest.raises(AssertionError, match="Schema mismatch"):
        validate_schema(bad_df)


def test_write_silver_roundtrip_and_partitions(spark, sample_xml, tmp_path):
    out = str(tmp_path / "silver")
    df = parse_fondpatrimdisvar_xml(spark, sample_xml)
    write_silver(df, out)
    assert (tmp_path / "silver" / "FechaDatos=202512").is_dir()
    assert spark.read.parquet(out).count() == df.count()


def test_write_silver_is_idempotent_and_quarterly_safe(spark, tmp_path):
    out = str(tmp_path / "silver")

    def entidad(reg):
        return [_entidad(reg, [_compartment(0)])]

    p2503 = parse_fondpatrimdisvar_xml(
        spark, _write_xml(tmp_path, "202503", entidad(1), "mar.xml")
    )
    p2506 = parse_fondpatrimdisvar_xml(
        spark, _write_xml(tmp_path, "202506", entidad(2), "jun.xml")
    )

    write_silver(p2503, out)
    write_silver(p2506, out)
    write_silver(p2503, out)  # rerun March

    result = spark.read.parquet(out)
    assert result.filter("FechaDatos = '202503'").count() == p2503.count()
    assert result.filter("FechaDatos = '202506'").count() == p2506.count()


def test_gate_period_months_rejects_non_quarterly_month(parsed, spark, tmp_path):
    bad = parse_fondpatrimdisvar_xml(
        spark,
        _write_xml(
            tmp_path,
            "202501",
            [_entidad(1, [_compartment(0)])],
            "jan.xml",
        ),
    )
    assert check_fin_period_months(parsed)[0] == 0
    assert check_fin_period_months(bad)[0] == 1


def test_gate_is_clean_for_parser_output(parsed):
    report = Report()
    run_artifact("financials", FIN_FINDINGS, report, parsed)
    statuses = {name: status for status, name, _ in report.results}
    assert statuses["fin_schema"] == "PASS"
    assert statuses["fin_duplicate_keys"] == "PASS"
    assert statuses["fin_period_months"] == "PASS"
    assert statuses["fin_non_fi"] == "PASS"
    assert statuses["fin_nonpositive_patrimony"] == "PASS"
    assert statuses["fin_negative_turnover"] == "PASS"
    assert report.summary() == 0


def test_gate_detects_duplicate_keys_and_negative_metrics(spark):
    row = (
        "202512",
        "FI",
        1,
        "EUR",
        0,
        *[
            Decimal("-1.00")
            if name in ("TotalPatrimonio", "PatrimonioFinPeriodoActual")
            else Decimal("0.00")
            for name in DECIMAL_FIELDS
        ],
    )
    fin = _financials(spark, [row, row])
    assert check_fin_duplicate_keys(fin)[0] == 1
    assert check_fin_nonpositive_patrimony(fin)[0] == 2
    assert check_fin_negative_turnover(fin)[0] == 0
