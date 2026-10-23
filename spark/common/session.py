from pyspark.sql import SparkSession


def get_spark(app_name="cnmv_parser", driver_memory="3g"):
    """Local session.

    driver_memory: the default 1g OOMs on the Silver QA window scans
    (e.g. frozen-VL runs over ~3.8M rows); 3g sized for this machine.
    Passed to spark-submit before the JVM starts (pyspark java_gateway).
    """
    spark = (
        SparkSession.builder.master("local[*]")
        .appName(app_name)
        .config("spark.driver.memory", driver_memory)
        .getOrCreate()
    )
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    return spark
