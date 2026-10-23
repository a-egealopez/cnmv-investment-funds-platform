from pyspark.sql import SparkSession

from spark.common.session import get_spark


def test_get_spark_returns_session_with_dynamic_overwrite():
    spark = get_spark("test_session")
    assert isinstance(spark, SparkSession)
    assert spark.conf.get("spark.sql.sources.partitionOverwriteMode") == "dynamic"
