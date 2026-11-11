from pyspark.sql.functions import col, expr
from pyspark.sql.types import (
    DateType,
    DecimalType,
    StringType,
    StructField,
    StructType,
)

from spark.common.session import get_spark

_DEC8 = DecimalType(18, 8)

# OUTPUT schema: contract of the Silver dataset. Grain: one row per series/day;
# unique business key (value_date, series); no partitions, full overwrite.
EXPECTED_SCHEMA = StructType(
    [
        StructField("series", StringType(), True),
        StructField("value_date", DateType(), True),
        StructField("obs_value", _DEC8),
        StructField("obs_status", StringType(), True),
    ]
)


def parse_estr_csv(spark, paths):
    """Read the raw ECB CSVs (data/raw/ecb/estr_*.csv) into the Silver contract."""
    df = spark.read.csv(paths, header=True)
    df = df.select(
        col("KEY").alias("series"),
        # try_cast: malformed dates or values become NULL instead of failing the job
        expr("try_cast(TIME_PERIOD AS DATE)").alias("value_date"),
        expr("try_cast(OBS_VALUE AS DECIMAL(18,8))").alias("obs_value"),
        col("OBS_STATUS").alias("obs_status"),
    )
    return df


def validate_schema(df):
    assert df.schema == EXPECTED_SCHEMA, (
        f"Schema mismatch:\nExpected: {EXPECTED_SCHEMA}\nGot: {df.schema}"
    )


def write_silver(df, path="data/silver/estr_daily"):
    # Needs partitionOverwriteMode=dynamic only when partitioned; the table is
    # small enough for a plain full overwrite, which is idempotent by design.
    df.write.mode("overwrite").parquet(path)


def main(input_paths: list[str], output_path: str):
    spark = get_spark("estr_parser")
    try:
        df = parse_estr_csv(spark, input_paths)
        validate_schema(df)
        write_silver(df, output_path)
    finally:
        spark.stop()


if __name__ == "__main__":
    import sys

    # Example: python -m spark.parsing.estr data/raw/ecb/estr_ci.csv,data/raw/ecb/estr_cr.csv data/silver/estr_daily
    paths = sys.argv[1].split(",")
    main(paths, sys.argv[2])
