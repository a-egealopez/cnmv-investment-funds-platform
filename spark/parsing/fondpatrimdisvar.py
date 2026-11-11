from pyspark.sql.functions import col, explode, expr
from pyspark.sql.types import (
    ArrayType,
    DecimalType,
    LongType,
    StringType,
    StructField,
    StructType,
)

from spark.common.session import get_spark

# Every non-key compartment field is TipoDecimal2 in the XSD. Some are monetary
# (distribution and period-end patrimony), the rest are percentages since the
# previous year-end; Silver keeps the source unit and sign.
_DEC2 = DecimalType(18, 2)
DECIMAL_FIELDS = (
    "IndiceRotacionCarteraActual",
    "IndiceRotacionCarteraAnterior",
    "DPInversionesFinancieras",
    "CarteraInterior",
    "CarteraExterior",
    "InteresesCartera",
    "InversionesDudosas",
    "Liquidez",
    "Resto",
    "TotalPatrimonio",
    "PatrimonioFinPeriodoAnterior",
    "Suscripciones_Reembolsos_Netos",
    "BeneficiosBrutosDistribuidos",
    "RendimientosNetos",
    "RendimientosGestion",
    "Intereses",
    "Dividendos",
    "ResultadosRentaFija",
    "ResultadosRentaVariable",
    "ResultadosDepositos",
    "ResultadosDerivados",
    "ResultadosIIC",
    "OtrosResultados",
    "OtrosRendimientos",
    "GastosRepercutidos",
    "ComisionGestion",
    "ComisionDepositario",
    "GastosServiciosExteriores",
    "OtrosGastosGestion",
    "OtrosGastosRepercutidos",
    "Ingresos",
    "ComisionesDescuento",
    "ComisionesRetrocedidas",
    "OtrosIngresos",
    "PatrimonioFinPeriodoActual",
)


def _compartment_struct():
    """Compartment fields as strings; optional XSD fields stay nullable."""
    return StructType(
        [StructField("NumeroCompartimento", StringType(), True)]
        + [StructField(name, StringType(), True) for name in DECIMAL_FIELDS]
    )


# INPUT schema: explicit so single elements are still arrays; all strings, cast later.
INPUT_SCHEMA = StructType(
    [
        StructField("FechaDatos", StringType(), True),
        StructField(
            "Entidad",
            ArrayType(
                StructType(
                    [
                        StructField("Tipo", StringType(), True),
                        StructField("NumeroRegistro", StringType(), True),
                        StructField("CodigoDivisaIIC", StringType(), True),
                        StructField(
                            "Compartimento",
                            ArrayType(_compartment_struct()),
                            True,
                        ),
                    ]
                )
            ),
            True,
        ),
    ]
)

# OUTPUT schema: contract of the Silver dataset. Grain: one row per
# Tipo + NumeroRegistro + NumeroCompartimento + FechaDatos.
EXPECTED_SCHEMA = StructType(
    [
        StructField("FechaDatos", StringType(), True),
        StructField("Tipo", StringType(), True),
        StructField("NumeroRegistro", LongType(), True),
        StructField("CodigoDivisaIIC", StringType(), True),
        StructField("NumeroCompartimento", LongType(), True),
        *[StructField(name, _DEC2, True) for name in DECIMAL_FIELDS],
    ]
)


def parse_fondpatrimdisvar_xml(spark, path):
    df = spark.read.schema(INPUT_SCHEMA).xml(path, rowTag="FondPatrimDisVar")

    # Flatten entity and compartment levels
    df = df.select("FechaDatos", explode("Entidad").alias("ent"))
    df = df.select(
        "FechaDatos",
        "ent.Tipo",
        "ent.NumeroRegistro",
        "ent.CodigoDivisaIIC",
        explode("ent.Compartimento").alias("comp"),
    )

    # try_cast from SQL: malformed decimals become NULL instead of failing the
    # period; validate_silver counts them rather than discarding rows.
    df = df.select(
        col("FechaDatos").cast(StringType()),
        col("Tipo"),
        col("NumeroRegistro").cast(LongType()),
        col("CodigoDivisaIIC"),
        col("comp.NumeroCompartimento").cast(LongType()).alias("NumeroCompartimento"),
        *[
            expr(f"try_cast(comp.{name} AS DECIMAL(18,2))").alias(name)
            for name in DECIMAL_FIELDS
        ],
    )
    return df


def validate_schema(df):
    assert df.schema == EXPECTED_SCHEMA, (
        f"Schema mismatch:\nExpected: {EXPECTED_SCHEMA}\nGot: {df.schema}"
    )


def write_silver(df, path="data/silver/fund_period_financials"):
    # Needs partitionOverwriteMode=dynamic (set in get_spark)
    df.write.mode("overwrite").partitionBy("FechaDatos").parquet(path)


def main(input_path: str, output_path: str):
    spark = get_spark("fondpatrimdisvar_parser")
    try:
        df = parse_fondpatrimdisvar_xml(spark, input_path)
        validate_schema(df)
        write_silver(df, output_path)
    finally:
        spark.stop()


if __name__ == "__main__":
    import sys

    # Example: python -m spark.parsing.fondpatrimdisvar data/bronze/cnmv_202512/FONDPATRIMDISVAR_202512.xml data/silver/fund_period_financials
    main(sys.argv[1], sys.argv[2])
