import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark():
    s = SparkSession.builder.master("local[1]").appName("tests").getOrCreate()
    s.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    yield s
    s.stop()
