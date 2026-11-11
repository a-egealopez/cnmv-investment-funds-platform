from pyspark.sql.functions import col, explode
from pyspark.sql.types import (
    ArrayType,
    DecimalType,
    LongType,
    StringType,
    StructField,
    StructType,
)

from spark.common.session import get_spark

# Reusable types mirroring the XSD restrictions
_DEC2 = DecimalType(18, 2)  # TipoDecimal2: fractionDigits 2
_TRIM_FIELDS = ("TrimestreActual", "T_1", "T_2", "T_3")


def _quarterly_struct(prefix, fields=_TRIM_FIELDS, type_=_DEC2):
    """Struct <prefix>_<f> for f in fields (all optional in the XSD)."""
    return StructType([StructField(f"{prefix}_{f}", type_, True) for f in fields])


def _class_struct():
    """Clase with its scalars plus the three quarterly metric structs."""
    return StructType(
        [
            StructField("NumeroClase", StringType(), True),
            StructField("ISIN", StringType(), True),
            StructField("CodigoDivisa", StringType(), True),
            StructField("NumeroParticipaciones", StringType(), True),
            StructField("NumeroParticipes", StringType(), True),
            StructField("Beneficio_Dividendo_Bruto", StringType(), True),
            StructField("Patrimonio", StringType(), True),
            StructField("ValorLiquidativo", StringType(), True),
            StructField("ComisionGestion", StringType(), True),
            StructField("BaseCalculo_ComisionGestion", StringType(), True),
            StructField("ComisionDepositario", StringType(), True),
            StructField("SistemaImputacionComisiones", StringType(), True),
            StructField("ComisionSuscripcionMaxima", StringType(), True),
            StructField("ComisionSuscripcionMinima", StringType(), True),
            StructField("ComisionReembolsoMaxima", StringType(), True),
            StructField("ComisionReembolsoMinima", StringType(), True),
            StructField("ComisionDescuentoFavorFondoMaxima", StringType(), True),
            StructField("ComisionDescuentoFavorFondoMinima", StringType(), True),
            StructField("Rentabilidad", _quarterly_struct("Rentabilidad"), True),
            StructField("PeriodicidadCalculoVL", StringType(), True),
            StructField(
                "Volatilidad_VL",
                StructType(
                    [
                        StructField(f"Volatilidad_{f}", _DEC2, True)
                        for f in ("TrimestreActual", "T_1", "T_2", "T_3")
                    ]
                ),
                True,
            ),
            StructField("RatioTotalGastos", _quarterly_struct("RatioTotalGastos")),
        ]
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
                        # entity level: repeats inside every class row
                        StructField("CodigoDivisaIIC", StringType(), True),
                        StructField(
                            "Compartimento",
                            ArrayType(
                                StructType(
                                    [
                                        StructField(
                                            "NumeroCompartimento", StringType(), True
                                        ),
                                        # compartment level: repeats likewise
                                        StructField("ClaseFondo", StringType(), True),
                                        StructField(
                                            "VocacionInversora", StringType(), True
                                        ),
                                        StructField(
                                            "Clase", ArrayType(_class_struct()), True
                                        ),
                                    ]
                                )
                            ),
                            True,
                        ),
                    ]
                )
            ),
            True,
        ),
    ]
)

# OUTPUT schema: contract of the Silver dataset. Grain: one row per class/month;
# entity and compartment fields repeat on every class row (parsing_decisions.md).
EXPECTED_SCHEMA = StructType(
    [
        # all listed flat, XSD order: entity, compartment, class, quarterly metrics
        StructField("FechaDatos", StringType(), True),
        StructField("Tipo", StringType(), True),
        StructField("NumeroRegistro", LongType(), True),
        StructField("CodigoDivisaIIC", StringType(), True),
        StructField("NumeroCompartimento", LongType(), True),
        StructField("VocacionInversora", StringType(), True),
        StructField("ClaseFondo", StringType(), True),
        StructField("NumeroClase", LongType(), True),
        StructField("ISIN", StringType(), True),
        StructField("CodigoDivisa", StringType(), True),
        StructField("NumeroParticipes", LongType(), True),
        StructField("NumeroParticipaciones", _DEC2),
        StructField("Beneficio_Dividendo_Bruto", _DEC2),
        StructField("Patrimonio", _DEC2),
        StructField("ValorLiquidativo", DecimalType(18, 4)),
        StructField("ComisionGestion", _DEC2),
        StructField("BaseCalculo_ComisionGestion", StringType(), True),
        StructField("ComisionDepositario", _DEC2),
        StructField("SistemaImputacionComisiones", StringType(), True),
        StructField("ComisionSuscripcionMaxima", _DEC2),
        StructField("ComisionSuscripcionMinima", _DEC2),
        StructField("ComisionReembolsoMaxima", _DEC2),
        StructField("ComisionReembolsoMinima", _DEC2),
        StructField("ComisionDescuentoFavorFondoMaxima", _DEC2),
        StructField("ComisionDescuentoFavorFondoMinima", _DEC2),
        *[StructField(f"Rentabilidad_{f}", _DEC2, True) for f in _TRIM_FIELDS],
        StructField("PeriodicidadCalculoVL", StringType(), True),
        *[StructField(f"Volatilidad_{f}", _DEC2, True) for f in _TRIM_FIELDS],
        *[StructField(f"RatioTotalGastos_{f}", _DEC2, True) for f in _TRIM_FIELDS],
    ]
)


def parse_fondtrim_xml(spark, path):
    df = spark.read.schema(INPUT_SCHEMA).xml(path, rowTag="FondTrim")

    # Flatten entity, compartment and class levels
    df = df.select("FechaDatos", explode("Entidad").alias("ent"))
    df = df.select(
        "FechaDatos",
        "ent.Tipo",
        "ent.NumeroRegistro",
        "ent.CodigoDivisaIIC",
        explode("ent.Compartimento").alias("comp"),
    )
    df = df.select(
        "FechaDatos",
        "Tipo",
        "NumeroRegistro",
        "CodigoDivisaIIC",
        col("comp.NumeroCompartimento").alias("NumeroCompartimento"),
        "comp.VocacionInversora",
        "comp.ClaseFondo",
        explode("comp.Clase").alias("clase"),
    )

    # Nested metric structs flattened to top-level columns (keep the XSD names)
    df = df.select(
        "FechaDatos",
        "Tipo",
        "NumeroRegistro",
        "CodigoDivisaIIC",
        "NumeroCompartimento",
        "VocacionInversora",
        "ClaseFondo",
        col("clase.NumeroClase").alias("NumeroClase"),
        "clase.ISIN",
        "clase.CodigoDivisa",
        "clase.NumeroParticipes",
        "clase.NumeroParticipaciones",
        "clase.Beneficio_Dividendo_Bruto",
        "clase.Patrimonio",
        "clase.ValorLiquidativo",
        "clase.ComisionGestion",
        "clase.BaseCalculo_ComisionGestion",
        "clase.ComisionDepositario",
        "clase.SistemaImputacionComisiones",
        "clase.ComisionSuscripcionMaxima",
        "clase.ComisionSuscripcionMinima",
        "clase.ComisionReembolsoMaxima",
        "clase.ComisionReembolsoMinima",
        "clase.ComisionDescuentoFavorFondoMaxima",
        "clase.ComisionDescuentoFavorFondoMinima",
        *[f"clase.Rentabilidad.Rentabilidad_{f}" for f in _TRIM_FIELDS],
        "clase.PeriodicidadCalculoVL",
        *[f"clase.Volatilidad_VL.Volatilidad_{f}" for f in _TRIM_FIELDS],
        *[f"clase.RatioTotalGastos.RatioTotalGastos_{f}" for f in _TRIM_FIELDS],
    )

    # Cast to final types
    df = df.select(
        col("FechaDatos").cast(StringType()),
        col("Tipo"),
        col("NumeroRegistro").cast(LongType()),
        "CodigoDivisaIIC",
        col("NumeroCompartimento").cast(LongType()),
        "VocacionInversora",
        "ClaseFondo",
        col("NumeroClase").cast(LongType()),
        "ISIN",
        "CodigoDivisa",
        col("NumeroParticipes").cast(LongType()),
        col("NumeroParticipaciones").cast(_DEC2),
        col("Beneficio_Dividendo_Bruto").cast(_DEC2),
        col("Patrimonio").cast(_DEC2),
        col("ValorLiquidativo").cast(DecimalType(18, 4)),
        col("ComisionGestion").cast(_DEC2),
        "BaseCalculo_ComisionGestion",
        col("ComisionDepositario").cast(_DEC2),
        "SistemaImputacionComisiones",
        col("ComisionSuscripcionMaxima").cast(_DEC2),
        col("ComisionSuscripcionMinima").cast(_DEC2),
        col("ComisionReembolsoMaxima").cast(_DEC2),
        col("ComisionReembolsoMinima").cast(_DEC2),
        col("ComisionDescuentoFavorFondoMaxima").cast(_DEC2),
        col("ComisionDescuentoFavorFondoMinima").cast(_DEC2),
        *[col(f"Rentabilidad_{f}").cast(_DEC2) for f in _TRIM_FIELDS],
        "PeriodicidadCalculoVL",
        *[col(f"Volatilidad_{f}").cast(_DEC2) for f in _TRIM_FIELDS],
        *[col(f"RatioTotalGastos_{f}").cast(_DEC2) for f in _TRIM_FIELDS],
    )
    return df


def validate_schema(df):
    assert df.schema == EXPECTED_SCHEMA, (
        f"Schema mismatch:\nExpected: {EXPECTED_SCHEMA}\nGot: {df.schema}"
    )


def write_silver(df, path="data/silver/fund_quarterly"):
    # Needs partitionOverwriteMode=dynamic (set in get_spark)
    df.write.mode("overwrite").partitionBy("FechaDatos").parquet(path)


def main(input_path: str, output_path: str):
    spark = get_spark("fondtrim_parser")
    try:
        df = parse_fondtrim_xml(spark, input_path)
        validate_schema(df)
        write_silver(df, output_path)
    finally:
        spark.stop()


if __name__ == "__main__":
    import sys

    # Example: python -m spark.parsing.fondtrim data/bronze/cnmv_202512/FONDTRIM_202512.xml data/silver/fund_quarterly
    main(sys.argv[1], sys.argv[2])
