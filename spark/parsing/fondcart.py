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

# INPUT schema: explicit so single elements are still arrays; all strings, cast later.
# Compartimentos without positions produce no rows; a source property, not a parse error.
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
                                            "InversionesFinancieras",
                                            ArrayType(
                                                StructType(
                                                    [
                                                        StructField(
                                                            "ClaseIF",
                                                            StringType(),
                                                            True,
                                                        ),
                                                        StructField(
                                                            "DescripcionIF",
                                                            StringType(),
                                                            True,
                                                        ),
                                                        StructField(
                                                            "CodigoISIN",
                                                            StringType(),
                                                            True,
                                                        ),
                                                        StructField(
                                                            "DescripcionValor",
                                                            StringType(),
                                                            True,
                                                        ),
                                                        StructField(
                                                            "Divisa", StringType(), True
                                                        ),
                                                        StructField(
                                                            "ValorMercado",
                                                            StringType(),
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

# OUTPUT schema: contract of the Silver dataset. Grain: one raw position line;
# repeated same-instrument lines are aggregated in the transformation layer.
EXPECTED_SCHEMA = StructType(
    [
        StructField("FechaDatos", StringType(), True),
        StructField("Tipo", StringType(), True),
        StructField("NumeroRegistro", LongType(), True),
        StructField("NumeroCompartimento", LongType(), True),
        StructField("ClaseIF", StringType(), True),
        StructField("DescripcionIF", StringType(), True),
        StructField("CodigoISIN", StringType(), True),
        StructField("DescripcionValor", StringType(), True),
        StructField("Divisa", StringType(), True),
        StructField("ValorMercado", DecimalType(18, 2), True),
    ]
)


def parse_fondcart_xml(spark, path):
    df = spark.read.schema(INPUT_SCHEMA).xml(path, rowTag="FondCart")

    # Flatten entity, compartment and position levels
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
        explode("comp.InversionesFinancieras").alias("pos"),
    )

    # Cast to final types
    df = df.select(
        col("FechaDatos").cast(StringType()),
        col("Tipo"),
        col("NumeroRegistro").cast(LongType()),
        col("NumeroCompartimento").cast(LongType()),
        col("pos.ClaseIF").alias("ClaseIF"),
        col("pos.DescripcionIF").alias("DescripcionIF"),
        col("pos.CodigoISIN").alias("CodigoISIN"),
        col("pos.DescripcionValor").alias("DescripcionValor"),
        col("pos.Divisa").alias("Divisa"),
        # try_cast from SQL: malformed decimals become NULL instead of
        # failing the job (the Python API has no try_cast)
        expr("try_cast(pos.ValorMercado AS DECIMAL(18,2))").alias("ValorMercado"),
    )
    return df


def validate_schema(df):
    assert df.schema == EXPECTED_SCHEMA, (
        f"Schema mismatch:\nExpected: {EXPECTED_SCHEMA}\nGot: {df.schema}"
    )


def write_silver(df, path="data/silver/fund_holdings"):
    # Needs partitionOverwriteMode=dynamic (set in get_spark)
    df.write.mode("overwrite").partitionBy("FechaDatos").parquet(path)


def main(input_path: str, output_path: str):
    spark = get_spark("fondcart_parser")
    try:
        df = parse_fondcart_xml(spark, input_path)
        validate_schema(df)
        write_silver(df, output_path)
    finally:
        spark.stop()


if __name__ == "__main__":
    import sys

    # Example: python -m spark.parsing.fondcart data/bronze/cnmv_202512/FONDCART_202512.xml data/silver/fund_holdings
    main(sys.argv[1], sys.argv[2])
