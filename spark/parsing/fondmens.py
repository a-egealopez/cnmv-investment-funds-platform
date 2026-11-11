from pyspark.sql.functions import col, explode, expr
from pyspark.sql.types import (
    ArrayType,
    DateType,
    DecimalType,
    LongType,
    StringType,
    StructField,
    StructType,
)

from spark.common.session import get_spark


def _daily_struct(prefix):
    """Struct with <prefix>_Dia1..31 as strings."""
    return StructType(
        [StructField(f"{prefix}_Dia{d}", StringType(), True) for d in range(1, 32)]
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
                        StructField(
                            "Compartimento",
                            ArrayType(
                                StructType(
                                    [
                                        StructField(
                                            "NumeroCompartimento", StringType(), True
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
                                                            "ISIN", StringType(), True
                                                        ),
                                                        StructField(
                                                            "VLDiario",
                                                            _daily_struct("VL"),
                                                            True,
                                                        ),
                                                        StructField(
                                                            "ParticipesDiario",
                                                            _daily_struct("Participes"),
                                                            True,
                                                        ),
                                                        StructField(
                                                            "PatrimonioDiario",
                                                            _daily_struct("Patrimonio"),
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
        StructField("NumeroCompartimento", LongType(), True),
        StructField("NumeroClase", LongType(), True),
        StructField("ISIN", StringType(), True),
        StructField("value_date", DateType(), True),
        StructField("VL", DecimalType(18, 4), True),
        StructField("Participes", LongType(), True),
        StructField("Patrimonio", DecimalType(18, 2), True),
    ]
)


def parse_fondmens_xml(spark, path):
    df = spark.read.schema(INPUT_SCHEMA).xml(path, rowTag="FondMens")

    # Flatten entity, compartment and class levels
    df = df.select("FechaDatos", explode("Entidad").alias("ent"))
    df = df.select(
        "FechaDatos",
        "ent.Tipo",
        "ent.NumeroRegistro",
        explode("ent.Compartimento").alias("comp"),
    )
    df = df.select(
        "FechaDatos",
        "Tipo",
        "NumeroRegistro",
        col("comp.NumeroCompartimento").alias("NumeroCompartimento"),
        explode("comp.Clase").alias("clase"),
    )
    df = df.select(
        "FechaDatos",
        "Tipo",
        "NumeroRegistro",
        "NumeroCompartimento",
        col("clase.NumeroClase").alias("NumeroClase"),
        col("clase.ISIN"),
        col("clase.VLDiario"),
        col("clase.ParticipesDiario"),
        col("clase.PatrimonioDiario"),
    )

    # Unpivot the 31 daily columns into rows
    day_columns = [
        f"{d}, VLDiario.VL_Dia{d}, ParticipesDiario.Participes_Dia{d}, PatrimonioDiario.Patrimonio_Dia{d}"
        for d in range(1, 32)
    ]
    stack_expr = (
        f"stack(31, {', '.join(day_columns)}) AS (day, VL, Participes, Patrimonio)"
    )
    df = df.select(
        "FechaDatos",
        "Tipo",
        "NumeroRegistro",
        "NumeroCompartimento",
        "NumeroClase",
        "ISIN",
        expr(stack_expr),
    )

    # Drop days without data (e.g. days 29-31 in short months)
    df = df.filter(
        col("VL").isNotNull()
        | col("Participes").isNotNull()
        | col("Patrimonio").isNotNull()
    )

    # CNMV zero-fills impossible days (e.g. Dia31 in April); try_to_date maps those
    # to NULL instead of raising, and padding rows are dropped right after
    df = df.withColumn(
        "value_date",
        expr(
            "try_to_date(concat(substr(FechaDatos, 1, 4), substr(FechaDatos, 5, 2), lpad(day, 2, '0')), 'yyyyMMdd')"
        ),
    )
    df = df.filter(col("value_date").isNotNull())

    # Cast to final types
    df = df.select(
        col("FechaDatos").cast(StringType()),
        col("Tipo"),
        col("NumeroRegistro").cast(LongType()),
        col("NumeroCompartimento").cast(LongType()),
        col("NumeroClase").cast(LongType()),
        col("ISIN"),
        col("value_date"),
        col("VL").cast(DecimalType(18, 4)),
        col("Participes").cast(LongType()),
        col("Patrimonio").cast(DecimalType(18, 2)),
    )
    return df


def validate_schema(df):
    assert df.schema == EXPECTED_SCHEMA, (
        f"Schema mismatch:\nExpected: {EXPECTED_SCHEMA}\nGot: {df.schema}"
    )


def write_silver(df, path="data/silver/fund_nav_daily"):
    # Needs partitionOverwriteMode=dynamic (set in get_spark)
    df.write.mode("overwrite").partitionBy("FechaDatos").parquet(path)


def main(input_path: str, output_path: str):
    spark = get_spark("fondmens_parser")
    try:
        df = parse_fondmens_xml(spark, input_path)
        validate_schema(df)
        write_silver(df, output_path)
    finally:
        spark.stop()


if __name__ == "__main__":
    import sys

    # Example: python -m spark.parsing.fondmens data/bronze/cnmv_202601/FONDMENS_202601.xml data/silver/fund_nav_daily
    main(sys.argv[1], sys.argv[2])
