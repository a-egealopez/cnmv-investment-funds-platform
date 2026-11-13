import os

from pyspark.sql import SparkSession


def get_spark(app_name="cnmv_parser", driver_memory=None):
    """Local session.

    driver_memory: the default 1g OOMs on the Silver QA window scans
    (e.g. frozen-VL runs over ~3.8M rows). Override with SPARK_DRIVER_MEMORY.
    Passed to spark-submit before the JVM starts (pyspark java_gateway).
    """
    driver_memory = driver_memory or os.environ.get("SPARK_DRIVER_MEMORY", "3g")
    spark = (
        SparkSession.builder.master("local[*]")
        .appName(app_name)
        .config("spark.driver.memory", driver_memory)
        .getOrCreate()
    )
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    return spark
