from decimal import Decimal

import pytest
from pyspark.sql.types import StringType, StructField, StructType

from spark.parsing.fondtrim import (
    EXPECTED_SCHEMA,
    parse_fondtrim_xml,
    validate_schema,
    write_silver,
)


def _metrics(values=None):
    """Quarterly struct with optional nested sub-blocks (Rentabilidad etc.)."""
    if not values:
        return ""
    rend = "".join(
        f"<Rentabilidad_{f}>{values[f]}</Rentabilidad_{f}>"
        for f in ("TrimestreActual", "T_1", "T_2", "T_3")
        if f in values
    )
    vol = "".join(
        f"<Volatilidad_{f}>{values[f]}</Volatilidad_{f}>"
        for f in ("TrimestreActual", "T_1", "T_2", "T_3")
        if f in values
    )
    gastos = "".join(
        f"<RatioTotalGastos_{f}>{values[f]}</RatioTotalGastos_{f}>"
        for f in ("TrimestreActual", "T_1", "T_2", "T_3")
        if f in values
    )
    return (
        "<Rentabilidad>"
        f"{rend}"
        "</Rentabilidad>"
        "<Volatilidad_VL>"
        f"{vol}"
        "</Volatilidad_VL>"
        "<RatioTotalGastos>"
        f"{gastos}"
        "</RatioTotalGastos>"
    )


def _clase(numero, isin, metrics=None, fees="1.25", vl="100.1234"):
    return f"""<Clase>
  <NumeroClase>{numero}</NumeroClase>
  <ISIN>{isin}</ISIN>
  <CodigoDivisa>EUR</CodigoDivisa>
  <NumeroParticipaciones>100</NumeroParticipaciones>
  <NumeroParticipes>50</NumeroParticipes>
  <Beneficio_Dividendo_Bruto>1.50</Beneficio_Dividendo_Bruto>
  <Patrimonio>10000.25</Patrimonio>
  <ValorLiquidativo>{vl}</ValorLiquidativo>
  <ComisionGestion>{fees}</ComisionGestion>
  <BaseCalculo_ComisionGestion>Patrimonio</BaseCalculo_ComisionGestion>
  <ComisionDepositario>0.05</ComisionDepositario>
  <SistemaImputacionComisiones>O</SistemaImputacionComisiones>
  <ComisionSuscripcionMaxima>2.00</ComisionSuscripcionMaxima>
  <ComisionSuscripcionMinima>0</ComisionSuscripcionMinima>
  <ComisionReembolsoMaxima>0.50</ComisionReembolsoMaxima>
  <ComisionReembolsoMinima>0.10</ComisionReembolsoMinima>
  <ComisionDescuentoFavorFondoMaxima>0</ComisionDescuentoFavorFondoMaxima>
  <ComisionDescuentoFavorFondoMinima>0</ComisionDescuentoFavorFondoMinima>
  {_metrics(metrics)}
  <PeriodicidadCalculoVL>D</PeriodicidadCalculoVL>
</Clase>"""


def _compartimento(numero, clases, vocacion="Renta Fija Euro", clase_fondo="Otros"):
    return f"""<Compartimento>
  <NumeroCompartimento>{numero}</NumeroCompartimento>
  <VocacionInversora>{vocacion}</VocacionInversora>
  <ClaseFondo>{clase_fondo}</ClaseFondo>
  {"".join(clases)}
</Compartimento>"""


def _entidad(registro, compartimentos, divisa_iic="EUR"):
    return f"""<Entidad>
  <Tipo>FI</Tipo>
  <NumeroRegistro>{registro}</NumeroRegistro>
  <CodigoDivisaIIC>{divisa_iic}</CodigoDivisaIIC>
  {"".join(compartimentos)}
</Entidad>"""


def _write_xml(tmp_path, fecha, entidades, name="fondtrim.xml"):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<FondTrim>
  <FechaDatos>{fecha}</FechaDatos>
  {"".join(entidades)}
</FondTrim>"""
    path = tmp_path / name
    path.write_text(xml, encoding="utf-8")
    return str(path)


@pytest.fixture
def sample_xml(tmp_path):
    # one entity, one compartment, two classes (compartment fields must repeat)
    return _write_xml(
        tmp_path,
        "202512",
        [
            _entidad(
                1234,
                [
                    _compartimento(
                        0,
                        [
                            _clase(
                                1,
                                "ES0000000001",
                                metrics={
                                    "TrimestreActual": "3.10",
                                    "T_1": "2.50",
                                    "T_2": "1.10",
                                    "T_3": "-0.30",
                                },
                            ),
                            _clase(2, "ES0000000002"),  # no metric sub-blocks
                        ],
                    )
                ],
            )
        ],
    )


@pytest.fixture
def parsed(spark, sample_xml):
    return parse_fondtrim_xml(spark, sample_xml)


def test_expected_schema_column_names():
    names = {f.name for f in EXPECTED_SCHEMA.fields}
    assert {
        "FechaDatos",
        "Tipo",
        "NumeroRegistro",
        "CodigoDivisaIIC",
        "NumeroCompartimento",
        "VocacionInversora",
        "ClaseFondo",
        "NumeroClase",
        "ISIN",
        "CodigoDivisa",
        "Patrimonio",
        "ValorLiquidativo",
        "Rentabilidad_TrimestreActual",
        "Volatilidad_TrimestreActual",
        "RatioTotalGastos_TrimestreActual",
    } <= names


def test_grain_is_one_row_per_class(parsed, spark):
    rows = parsed.collect()
    assert len(rows) == 2
    assert (
        parsed.select("Tipo", "NumeroRegistro", "NumeroCompartimento", "NumeroClase")
        .distinct()
        .count()
        == 2
    )


def test_compartment_and_entity_fields_repeat_on_every_class_row(parsed):
    vocaciones = {r.VocacionInversora for r in parsed.collect()}
    divisa_iic = {r.CodigoDivisaIIC for r in parsed.collect()}
    assert vocaciones == {"Renta Fija Euro"}
    assert divisa_iic == {"EUR"}


def test_types_are_cast(parsed):
    primera = parsed.filter("NumeroClase = 1").first()
    assert primera.NumeroRegistro == 1234
    assert isinstance(primera.NumeroClase, int)
    assert primera.Patrimonio == Decimal("10000.25")
    assert primera.ValorLiquidativo == Decimal("100.1234")
    assert primera.Rentabilidad_TrimestreActual == Decimal("3.10")
    assert primera.Rentabilidad_T_3 == Decimal("-0.30")


def test_optional_metric_structs_yield_nulls(parsed):
    segunda = parsed.filter("NumeroClase = 2").first()
    assert segunda.Rentabilidad_TrimestreActual is None
    assert segunda.Volatilidad_TrimestreActual is None
    assert segunda.RatioTotalGastos_TrimestreActual is None


def test_single_entity_single_class_without_arrays(tmp_path, spark):
    # single elements must still be parsed as arrays
    path = _write_xml(
        tmp_path,
        "202506",
        [_entidad(1, [_compartimento(0, [_clase(1, "ES0000000001")])])],
    )
    df = parse_fondtrim_xml(spark, path)
    assert df.count() == 1


def test_validate_schema_valid(spark, sample_xml):
    validate_schema(parse_fondtrim_xml(spark, sample_xml))


def test_validate_schema_invalid(spark):
    bad_df = spark.createDataFrame(
        [], StructType([StructField("wrong_col", StringType(), True)])
    )
    with pytest.raises(AssertionError, match="Schema mismatch"):
        validate_schema(bad_df)


def test_write_silver_roundtrip_and_partitions(spark, sample_xml, tmp_path):
    out = str(tmp_path / "silver")
    df = parse_fondtrim_xml(spark, sample_xml)
    write_silver(df, out)
    assert (tmp_path / "silver" / "FechaDatos=202512").is_dir()
    assert spark.read.parquet(out).count() == df.count()


def test_write_silver_is_idempotent_and_semestral_safe(spark, tmp_path):
    # two semiannual periods written twice must keep one partition each
    out = str(tmp_path / "silver")

    def entidad(reg, comp):
        return [_entidad(reg, [_compartimento(comp, [_clase(1, "ES0000000001")])])]

    p2506 = parse_fondtrim_xml(
        spark, _write_xml(tmp_path, "202506", entidad(1, 0), "jun.xml")
    )
    p2512 = parse_fondtrim_xml(
        spark, _write_xml(tmp_path, "202512", entidad(2, 0), "dec.xml")
    )

    write_silver(p2506, out)
    write_silver(p2512, out)
    write_silver(p2506, out)  # rerun June

    result = spark.read.parquet(out)
    assert result.filter("FechaDatos = '202506'").count() == p2506.count()
    assert result.filter("FechaDatos = '202512'").count() == p2512.count()
