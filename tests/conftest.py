import pytest

from spark.common.session import get_spark


@pytest.fixture(scope="session")
def spark():
    # The production session, so tests run with its settings (e.g. dynamic
    # partition overwrite, which keeps Silver rewrites idempotent).
    s = get_spark("tests", driver_memory="1g")
    yield s
    s.stop()
