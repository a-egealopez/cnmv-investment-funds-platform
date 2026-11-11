import pytest

from ingestion.download_ecb_estr import CSV_HEADER, save_key_from_csv

KEY = "EST.B.EU000A2QQF16.CR"


def _csv(keys, header=CSV_HEADER):
    rows = "\n".join(f"{k},B,EU000A2QQF16,CR,2026-05-05,2.44,A" for k in keys)
    header_csv = ",".join(header[:7])
    return f"{header_csv}\n{rows}\n"


def test_accepts_valid_payload(tmp_path):
    path = tmp_path / "estr.csv"
    path.write_text(_csv([KEY]))
    assert save_key_from_csv(path) == KEY


def test_rejects_unexpected_header(tmp_path):
    path = tmp_path / "estr.csv"
    path.write_text("FOO,BAR\nEST.K,1.0\n")
    with pytest.raises(ValueError, match="unexpected CSV header"):
        save_key_from_csv(path)


def test_rejects_multiple_series_keys(tmp_path):
    path = tmp_path / "estr.csv"
    path.write_text(_csv([KEY, "EST.B.EU000A2QQF08.CI"]))
    with pytest.raises(ValueError, match="single series key"):
        save_key_from_csv(path)


def test_series_keys_are_expected():
    from ingestion.download_ecb_estr import SERIES

    assert set(SERIES) == {"B.EU000A2QQF08.CI", "B.EU000A2QQF16.CR"}
    assert {name for name, _ in SERIES.values()} == {"estr_ci.csv", "estr_cr.csv"}
