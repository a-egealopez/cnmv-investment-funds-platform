from pyspark.sql.functions import col, explode
from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    LongType,
    StringType,
    StructField,
    StructType,
)

from config import SILVER_DIR

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
                        StructField("Denominacion", StringType(), True),
                        StructField("ETF", StringType(), True),
                        StructField(
                            "Gestora",
                            StructType(
                                [
                                    StructField(
                                        "DenominacionGestora", StringType(), True
                                    ),
                                    StructField(
                                        "NumeroRegistroGestora", StringType(), True
                                    ),
                                    StructField("TipoGestora", StringType(), True),
                                    StructField(
                                        "GrupoGestora",
                                        StructType(
                                            [
                                                StructField(
                                                    "DenominacionGrupoGestora",
                                                    StringType(),
                                                    True,
                                                ),
                                            ]
                                        ),
                                        True,
                                    ),
                                ]
                            ),
                            True,
                        ),
                        StructField(
                            "Depositario",
                            StructType(
                                [
                                    StructField(
                                        "DenominacionDepositario", StringType(), True
                                    ),
                                    StructField(
                                        "NumeroRegistroDepositario", StringType(), True
                                    ),
                                    StructField(
                                        "GrupoDepositario",
                                        StructType(
                                            [
                                                StructField(
                                                    "DenominacionGrupoDepositario",
                                                    StringType(),
                                                    True,
                                                ),
                                            ]
                                        ),
                                        True,
                                    ),
                                ]
                            ),
                            True,
                        ),
                        StructField(
                            "Compartimento",
                            ArrayType(
                                StructType(
                                    [
                                        StructField(
                                            "NumeroCompartimento", StringType(), True
                                        ),
                                        StructField(
                                            "DenominacionCompartimento",
                                            StringType(),
                                            True,
                                        ),
                                        StructField(
                                            "Clase",
                                            ArrayType(
                                                StructType(
                                                    [
                                                        StructField(
                                                            "NumeroClase",
                                                            StringType(),
                                                            True,
                                                        ),
                                                        StructField(
                                                            "DenominacionClase",
                                                            StringType(),
                                                            True,
                                                        ),
                                                        StructField(
                                                            "ISIN", StringType(), True
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
            ),
            True,
        ),
    ]
)

# OUTPUT schema: contract of the Silver dataset.
EXPECTED_SCHEMA = StructType(
    [
        StructField("FechaDatos", StringType(), True),
        StructField("Tipo", StringType(), True),
        StructField("NumeroRegistro", LongType(), True),
        StructField("Denominacion", StringType(), True),
        StructField("ETF", BooleanType(), True),
        StructField("NumeroCompartimento", LongType(), True),
        StructField("DenominacionCompartimento", StringType(), True),
        StructField("NumeroClase", LongType(), True),
        StructField("DenominacionClase", StringType(), True),
        StructField("ISIN", StringType(), True),
        StructField("DenominacionGestora", StringType(), True),
        StructField("NumeroRegistroGestora", LongType(), True),
        StructField("TipoGestora", StringType(), True),
        StructField("DenominacionGrupoGestora", StringType(), True),
        StructField("DenominacionDepositario", StringType(), True),
        StructField("NumeroRegistroDepositario", LongType(), True),
        StructField("DenominacionGrupoDepositario", StringType(), True),
    ]
)


def parse_fondregistro_xml(spark, path):
    df = spark.read.schema(INPUT_SCHEMA).xml(path, rowTag="FondRegistro")

    # Flatten entity, compartment and class levels
    df = df.select("FechaDatos", explode("Entidad").alias("ent"))
    df = df.select(
        "FechaDatos",
        "ent.Tipo",
        "ent.NumeroRegistro",
        "ent.Denominacion",
        "ent.ETF",
        "ent.Gestora",
        "ent.Depositario",
        explode("ent.Compartimento").alias("comp"),
    )
    df = df.select(
        "FechaDatos",
        "Tipo",
        "NumeroRegistro",
        "Denominacion",
        "ETF",
        "Gestora",
        "Depositario",
        col("comp.NumeroCompartimento").alias("NumeroCompartimento"),
        col("comp.DenominacionCompartimento").alias("DenominacionCompartimento"),
        explode("comp.Clase").alias("clase"),
    )

    # Cast to final types and flatten nested fields
    df = df.select(
        col("FechaDatos").cast(StringType()),
        col("Tipo"),
        col("NumeroRegistro").cast(LongType()),
        col("Denominacion"),
        (col("ETF") == "YES").alias("ETF"),
        col("NumeroCompartimento").cast(LongType()),
        col("DenominacionCompartimento"),
        col("clase.NumeroClase").cast(LongType()).alias("NumeroClase"),
        col("clase.DenominacionClase").alias("DenominacionClase"),
        col("clase.ISIN"),
        col("Gestora.DenominacionGestora"),
        col("Gestora.NumeroRegistroGestora")
        .cast(LongType())
        .alias("NumeroRegistroGestora"),
        col("Gestora.TipoGestora"),
        col("Gestora.GrupoGestora.DenominacionGrupoGestora"),
        col("Depositario.DenominacionDepositario"),
        col("Depositario.NumeroRegistroDepositario")
        .cast(LongType())
        .alias("NumeroRegistroDepositario"),
        col("Depositario.GrupoDepositario.DenominacionGrupoDepositario"),
    )
    return df


def validate_schema(df):
    assert df.schema == EXPECTED_SCHEMA, (
        f"Schema mismatch:\nExpected: {EXPECTED_SCHEMA}\nGot: {df.schema}"
    )


def write_silver(df, path=str(SILVER_DIR / "fund_metadata")):
    # Needs partitionOverwriteMode=dynamic (set in get_spark)
    df.write.mode("overwrite").partitionBy("FechaDatos").parquet(path)
