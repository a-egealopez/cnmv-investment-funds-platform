import pytest

from spark.jobs.build_silver import main, periods_in, select_periods

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
