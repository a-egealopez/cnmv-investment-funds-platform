import pytest

from config import COMPLETE_MARKER
from spark.jobs.build_silver import (
    main,
    mark_processed,
    pending_periods,
    periods_in,
    select_periods,
)

AVAILABLE = ["202601", "202602", "202603"]


def test_select_periods_all_by_default():
    assert select_periods(AVAILABLE, None) == AVAILABLE


def test_select_periods_single():
    assert select_periods(AVAILABLE, "202602") == ["202602"]


def test_select_periods_rejects_unknown():
    with pytest.raises(ValueError, match="not in bronze"):
        select_periods(AVAILABLE, "209901")


def test_periods_in_reads_bronze_dirs(tmp_path):
    for p in ("cnmv_202602", "cnmv_202601"):
        (tmp_path / p).mkdir()
    (tmp_path / "stray.txt").write_text("x")
    assert periods_in(tmp_path) == ["202601", "202602"]


def test_main_fails_cleanly_on_empty_bronze(tmp_path, capsys):
    # fresh container: the data volume exists but ingestion has not run yet
    assert main(["--bronze-dir", str(tmp_path)]) == 1
    assert "run the ingestion first" in capsys.readouterr().out


def test_main_fails_on_unknown_period(tmp_path, capsys):
    (tmp_path / "cnmv_202601").mkdir()
    assert main(["--bronze-dir", str(tmp_path), "--period", "209901"]) == 1
    assert "not in bronze" in capsys.readouterr().out


def _bronze(tmp_path, periodo, fingerprint):
    d = tmp_path / "bronze" / f"cnmv_{periodo}"
    d.mkdir(parents=True)
    if fingerprint is not None:
        (d / COMPLETE_MARKER).write_text(fingerprint + "\n")
    return tmp_path / "bronze", tmp_path / "processed"


def test_new_period_is_pending(tmp_path):
    bronze, processed = _bronze(tmp_path, "202601", "aaa")
    assert pending_periods(bronze, processed) == ["202601"]


def test_processed_period_is_not_pending(tmp_path):
    bronze, processed = _bronze(tmp_path, "202601", "aaa")
    mark_processed(processed, "202601", "aaa")
    assert pending_periods(bronze, processed) == []


def test_republished_period_is_pending_again(tmp_path):
    bronze, processed = _bronze(tmp_path, "202601", "bbb")
    mark_processed(processed, "202601", "aaa")
    assert pending_periods(bronze, processed) == ["202601"]


def test_incomplete_period_is_skipped(tmp_path):
    bronze, processed = _bronze(tmp_path, "202601", None)
    assert pending_periods(bronze, processed) == []


def test_pending_and_period_are_mutually_exclusive(tmp_path):
    with pytest.raises(SystemExit):
        main(["--bronze-dir", str(tmp_path), "--pending", "--period", "202601"])
