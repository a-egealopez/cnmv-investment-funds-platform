import pytest

from spark.common.cadence import SEMESTER_MONTHS, is_semester_period


@pytest.mark.parametrize(
    ("periodo", "expected"),
    [
        ("202006", True),
        ("202012", True),
        ("202003", False),  # quarterly closing published until 2022
        ("202009", False),
        ("202301", False),  # monthly-only period
    ],
)
def test_is_semester_period(periodo, expected):
    assert is_semester_period(periodo) is expected


def test_semester_months_are_june_and_december():
    assert SEMESTER_MONTHS == {"06", "12"}
