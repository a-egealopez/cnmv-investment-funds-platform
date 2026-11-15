from decimal import Decimal

import pytest
from pyspark.sql.types import StringType, StructField, StructType

from spark.parsing.fondcart import (
    parse_fondcart_xml,
    validate_schema,
    write_silver,
)


def _posicion(
    isin: str | None = "ES0000000001",
    valor="1000.55",
    clase_if="EXTERIOR",
    divisa="EUR",
):
    isin_tag = f"<CodigoISIN>{isin}</CodigoISIN>" if isin is not None else ""
    return f"""<InversionesFinancieras>
  <ClaseIF>{clase_if}</ClaseIF>
  <DescripcionIF>Renta variable</DescripcionIF>
  {isin_tag}
  <DescripcionValor>Bono</DescripcionValor>
  <Divisa>{divisa}</Divisa>
  <ValorMercado>{valor}</ValorMercado>
</InversionesFinancieras>"""


def _compartimento(numero, posiciones):
    return f"""<Compartimento>
  <NumeroCompartimento>{numero}</NumeroCompartimento>
  {"".join(posiciones)}
</Compartimento>"""


def _entidad(registro, compartimentos):
    return f"""<Entidad>
  <Tipo>FI</Tipo>
  <NumeroRegistro>{registro}</NumeroRegistro>
  {"".join(compartimentos)}
</Entidad>"""


def _write_xml(tmp_path, fecha, entidades, name="fondcart.xml"):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<FondCart>
  <FechaDatos>{fecha}</FechaDatos>
  {"".join(entidades)}
</FondCart>"""
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
                1234,
                [
                    _compartimento(
                        0,
                        [
                            _posicion(),
                            _posicion(isin="ES0000000002", valor="2500.00"),
                        ],
                    )
                ],
            ),
            _entidad(
                5678,
                [
                    _compartimento(1, [_posicion()]),  # same instrument as 1234/0
                    _compartimento(9, []),  # no InversionesFinancieras at all
                ],
            ),
        ],
    )


@pytest.fixture
def parsed(spark, sample_xml):
    return parse_fondcart_xml(spark, sample_xml)


def test_columns(parsed):
    assert set(parsed.columns) == {
        "FechaDatos",
        "Tipo",
        "NumeroRegistro",
        "NumeroCompartimento",
        "ClaseIF",
        "DescripcionIF",
        "CodigoISIN",
        "DescripcionValor",
        "Divisa",
        "ValorMercado",
    }


def test_raw_line_grain_with_no_aggregation(parsed):
    # same instrument in two compartments must stay as two raw lines
    rows = parsed.filter(
        "NumeroRegistro = 1234 OR (NumeroRegistro = 5678 AND NumeroCompartimento = 1)"
    ).collect()
    assert len(rows) == 3
    assert sum(1 for r in rows if r.NumeroRegistro == 5678) == 1


def test_compartment_without_positions_produces_no_rows(parsed):
    # entity 5678 keeps one compartment with data and one empty one
    filas_5678 = [r for r in parsed.collect() if r.NumeroRegistro == 5678]
    assert len(filas_5678) == 1
    assert filas_5678[0].NumeroCompartimento == 1


def test_types_are_cast(parsed):
    fila = parsed.filter(
        "NumeroRegistro = 1234 AND CodigoISIN = 'ES0000000002'"
    ).first()
    assert fila.NumeroRegistro == 1234
    assert fila.ValorMercado == Decimal("2500.00")


def test_repeated_instrument_lines_survive(tmp_path, spark):
    path = _write_xml(
        tmp_path,
        "202512",
        [
            _entidad(
                1234,
                [_compartimento(0, [_posicion(), _posicion(valor="55.00")])],
            )
        ],
    )
    df = parse_fondcart_xml(spark, path)
    assert df.count() == 2  # the parser must not dedupe


def test_null_isin_and_malformed_value_cast_to_null(tmp_path, spark):
    path = _write_xml(
        tmp_path,
        "202512",
        [
            _entidad(
                1234,
                [
                    _compartimento(
                        0,
                        [_posicion(isin=None, valor="not-a-number")],
                    )
                ],
            )
        ],
    )
    df = parse_fondcart_xml(spark, path)
    row = df.first()
    assert row.CodigoISIN is None
    assert row.ValorMercado is None


def test_validate_schema_valid(spark, sample_xml):
    validate_schema(parse_fondcart_xml(spark, sample_xml))


def test_validate_schema_invalid(spark):
    bad_df = spark.createDataFrame(
        [], StructType([StructField("wrong_col", StringType(), True)])
    )
    with pytest.raises(AssertionError, match="Schema mismatch"):
        validate_schema(bad_df)


def test_write_silver_roundtrip_and_partitions(spark, sample_xml, tmp_path):
    out = str(tmp_path / "silver")
    df = parse_fondcart_xml(spark, sample_xml)
    write_silver(df, out)
    assert (tmp_path / "silver" / "FechaDatos=202512").is_dir()
    assert spark.read.parquet(out).count() == df.count()


def test_write_silver_is_idempotent_and_semestral_safe(spark, tmp_path):
    out = str(tmp_path / "silver")

    def entidad():
        return [_entidad(1, [_compartimento(0, [_posicion()])])]

    p2506 = parse_fondcart_xml(
        spark, _write_xml(tmp_path, "202506", entidad(), "jun.xml")
    )
    p2512 = parse_fondcart_xml(
        spark, _write_xml(tmp_path, "202512", entidad(), "dec.xml")
    )

    write_silver(p2506, out)
    write_silver(p2512, out)
    write_silver(p2506, out)  # rerun June

    result = spark.read.parquet(out)
    assert result.filter("FechaDatos = '202506'").count() == p2506.count()
    assert result.filter("FechaDatos = '202512'").count() == p2512.count()
