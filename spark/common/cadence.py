"""Reporting cadence that Silver keeps for the periodic CNMV sources.

FONDTRIM, FONDCART and FONDPATRIMDISVAR: Silver keeps the semiannual closings
only. CNMV published them quarterly until 2022 (03/06/09/12, with 202109 absent
from the archive) and semiannually from 2023 (06/12). Loading 06/12 keeps one
homogeneous cadence from 2020 on; Bronze still keeps the quarterly files, so the
decision is reversible without downloading again.
"""

SEMESTER_MONTHS = frozenset({"06", "12"})


def is_semester_period(periodo: str) -> bool:
    """True for a YYYYMM period at a semiannual closing (June or December)."""
    return periodo[4:6] in SEMESTER_MONTHS
