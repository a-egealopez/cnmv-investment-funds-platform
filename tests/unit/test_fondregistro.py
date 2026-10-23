import pytest
from pyspark.sql.types import StringType, StructField, StructType

from spark.parsing.fondregistro import (
    parse_fondregistro_xml,
    validate_schema,
    write_silver,
)

CLASE = """      <Clase>
        <NumeroClase>1</NumeroClase>
        <DenominacionClase>Class A</DenominacionClase>
        <ISIN>ES0123456789</ISIN>
      </Clase>
      <Clase>
        <NumeroClase>2</NumeroClase>
        <DenominacionClase>Class B</DenominacionClase>
        <ISIN>ES0123456790</ISIN>
      </Clase>"""

COMPARTIMENTO = f"""    <Compartimento>
      <NumeroCompartimento>1</NumeroCompartimento>
      <DenominacionCompartimento>Compartment A</DenominacionCompartimento>
{CLASE}
    </Compartimento>
    <Compartimento>
      <NumeroCompartimento>2</NumeroCompartimento>
      <DenominacionCompartimento>Compartment B</DenominacionCompartimento>
{CLASE}
    </Compartimento>"""

ENTIDAD = f"""  <Entidad>
    <Tipo>FI</Tipo>
    <NumeroRegistro>1234</NumeroRegistro>
    <Denominacion>Test Fund</Denominacion>
    <ETF>YES</ETF>
    <Gestora>
      <DenominacionGestora>Manager A</DenominacionGestora>
      <NumeroRegistroGestora>100</NumeroRegistroGestora>
      <TipoGestora>SICAV</TipoGestora>
      <GrupoGestora>
        <DenominacionGrupoGestora>Group A</DenominacionGrupoGestora>
      </GrupoGestora>
    </Gestora>
    <Depositario>
      <DenominacionDepositario>Depositary A</DenominacionDepositario>
      <NumeroRegistroDepositario>200</NumeroRegistroDepositario>
      <GrupoDepositario>
        <DenominacionGrupoDepositario>Group B</DenominacionGrupoDepositario>
      </GrupoDepositario>
    </Depositario>
{COMPARTIMENTO}
  </Entidad>
  <Entidad>
    <Tipo>FI</Tipo>
    <NumeroRegistro>5678</NumeroRegistro>
    <Denominacion>Test Fund 2</Denominacion>
    <ETF>NO</ETF>
    <Gestora>
      <DenominacionGestora>Manager B</DenominacionGestora>
      <NumeroRegistroGestora>300</NumeroRegistroGestora>
      <TipoGestora>SICAV</TipoGestora>
      <GrupoGestora>
        <DenominacionGrupoGestora>Group C</DenominacionGrupoGestora>
      </GrupoGestora>
    </Gestora>
    <Depositario>
      <DenominacionDepositario>Depositary B</DenominacionDepositario>
      <NumeroRegistroDepositario>400</NumeroRegistroDepositario>
      <GrupoDepositario>
        <DenominacionGrupoDepositario>Group D</DenominacionGrupoDepositario>
      </GrupoDepositario>
    </Depositario>
{COMPARTIMENTO}
  </Entidad>"""

# One entity, one compartment, one class
SINGLE_ENTIDAD = """  <Entidad>
    <Tipo>FI</Tipo>
    <NumeroRegistro>9</NumeroRegistro>
    <Denominacion>Single Fund</Denominacion>
    <ETF>NO</ETF>
    <Gestora>
      <DenominacionGestora>Manager Z</DenominacionGestora>
      <NumeroRegistroGestora>500</NumeroRegistroGestora>
      <TipoGestora>SGIIC</TipoGestora>
      <GrupoGestora>
        <DenominacionGrupoGestora>Group Z</DenominacionGrupoGestora>
      </GrupoGestora>
    </Gestora>
    <Depositario>
      <DenominacionDepositario>Depositary Z</DenominacionDepositario>
      <NumeroRegistroDepositario>600</NumeroRegistroDepositario>
      <GrupoDepositario>
        <DenominacionGrupoDepositario>Group Y</DenominacionGrupoDepositario>
      </GrupoDepositario>
    </Depositario>
    <Compartimento>
      <NumeroCompartimento>0</NumeroCompartimento>
      <DenominacionCompartimento>Single</DenominacionCompartimento>
      <Clase>
        <NumeroClase>1</NumeroClase>
        <DenominacionClase>Single Class</DenominacionClase>
        <ISIN>ES0999999999</ISIN>
      </Clase>
    </Compartimento>
  </Entidad>"""


def _write_xml(tmp_path, entidades, fecha="202601", name="sample_fondregistro.xml"):
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<FondRegistro>
  <FechaDatos>{fecha}</FechaDatos>
{entidades}
</FondRegistro>"""
    xml_path = tmp_path / name
    xml_path.write_text(xml_content, encoding="utf-8")
    return str(xml_path)


@pytest.fixture
def sample_xml(tmp_path):
    return _write_xml(tmp_path, ENTIDAD)


def test_columns(spark, sample_xml):
    df = parse_fondregistro_xml(spark, sample_xml)
    assert set(df.columns) == {
        "FechaDatos",
        "Tipo",
        "NumeroRegistro",
        "Denominacion",
        "ETF",
        "NumeroCompartimento",
        "DenominacionCompartimento",
        "NumeroClase",
        "DenominacionClase",
        "ISIN",
        "DenominacionGestora",
        "NumeroRegistroGestora",
        "TipoGestora",
        "DenominacionGrupoGestora",
        "DenominacionDepositario",
        "NumeroRegistroDepositario",
        "DenominacionGrupoDepositario",
    }


def test_exact_row_count(spark, sample_xml):
    df = parse_fondregistro_xml(spark, sample_xml)
    assert df.count() == 2 * 2 * 2  # entities x compartments x classes


def test_fecha_datos_real_format(spark, sample_xml):
    df = parse_fondregistro_xml(spark, sample_xml)
    fechas = {r.FechaDatos for r in df.select("FechaDatos").distinct().collect()}
    assert fechas == {"202601"}


def test_concrete_row_values(spark, sample_xml):
    df = parse_fondregistro_xml(spark, sample_xml)
    rows = df.filter(
        "NumeroRegistro = 1234 AND NumeroCompartimento = 1 AND NumeroClase = 1"
    ).collect()
    assert len(rows) == 1
    row = rows[0]
    assert row.Tipo == "FI"
    assert row.Denominacion == "Test Fund"
    assert row.ETF is True
    assert row.DenominacionCompartimento == "Compartment A"
    assert row.DenominacionClase == "Class A"
    assert row.ISIN == "ES0123456789"
    assert row.DenominacionGestora == "Manager A"
    assert row.NumeroRegistroGestora == 100
    assert row.TipoGestora == "SICAV"
    assert row.DenominacionGrupoGestora == "Group A"
    assert row.DenominacionDepositario == "Depositary A"
    assert row.NumeroRegistroDepositario == 200
    assert row.DenominacionGrupoDepositario == "Group B"


def test_etf_boolean_values(spark, sample_xml):
    df = parse_fondregistro_xml(spark, sample_xml)
    etf_values = {r.ETF for r in df.select("ETF").distinct().collect()}
    assert etf_values == {True, False}


def test_etf_matches_each_entity(spark, sample_xml):
    df = parse_fondregistro_xml(spark, sample_xml)
    etf_by_fund = {
        r.NumeroRegistro: r.ETF
        for r in df.select("NumeroRegistro", "ETF").distinct().collect()
    }
    assert etf_by_fund == {1234: True, 5678: False}


def test_single_entity_compartment_and_class(spark, tmp_path):
    # Single elements must still be parsed as arrays
    path = _write_xml(tmp_path, SINGLE_ENTIDAD, name="single.xml")
    df = parse_fondregistro_xml(spark, path)
    assert df.count() == 1
    row = df.collect()[0]
    assert row.ISIN == "ES0999999999"
    assert row.ETF is False


def test_validate_schema_valid(spark, sample_xml):
    validate_schema(parse_fondregistro_xml(spark, sample_xml))


def test_validate_schema_invalid(spark):
    bad_df = spark.createDataFrame(
        [], StructType([StructField("wrong_col", StringType(), True)])
    )
    with pytest.raises(AssertionError, match="Schema mismatch"):
        validate_schema(bad_df)


def test_write_silver_roundtrip_and_partitions(spark, sample_xml, tmp_path):
    out = str(tmp_path / "silver")
    df = parse_fondregistro_xml(spark, sample_xml)
    write_silver(df, out)
    assert (tmp_path / "silver" / "FechaDatos=202601").is_dir()
    assert spark.read.parquet(out).count() == df.count()


def test_write_silver_is_idempotent_and_keeps_other_periods(spark, tmp_path):
    out = str(tmp_path / "silver")
    jan = parse_fondregistro_xml(
        spark, _write_xml(tmp_path, ENTIDAD, "202601", "jan.xml")
    )
    feb = parse_fondregistro_xml(
        spark, _write_xml(tmp_path, ENTIDAD, "202602", "feb.xml")
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
