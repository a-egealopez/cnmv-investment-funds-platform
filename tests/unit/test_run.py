import pytest

from ingestion import download_ecb_estr, download_history, run


@pytest.fixture
def calls(monkeypatch):
    seen = {"cnmv": None, "ecb": 0}

    def fake_cnmv(argv):
        seen["cnmv"] = argv
        return seen.get("cnmv_status", 0)

    def fake_ecb(argv):
        seen["ecb"] += 1
        return seen.get("ecb_status", 0)

    monkeypatch.setattr(download_history, "main", fake_cnmv)
    monkeypatch.setattr(download_ecb_estr, "main", fake_ecb)
    return seen


def test_runs_both_steps_and_passes_the_period(calls):
    assert run.main(["--period", "202606"]) == 0
    assert calls["cnmv"] == ["--period", "202606"]
    assert calls["ecb"] == 1


def test_cnmv_failure_still_runs_ecb_and_fails(calls):
    calls["cnmv_status"] = 1
    assert run.main(["--period", "202606"]) == 1
    assert calls["ecb"] == 1


def test_ecb_failure_fails_the_run(calls):
    calls["ecb_status"] = 1
    assert run.main(["--period", "202606"]) == 1


def test_ecb_exception_becomes_a_failure(monkeypatch, calls):
    def boom(argv):
        raise RuntimeError("network down")

    monkeypatch.setattr(download_ecb_estr, "main", boom)
    assert run.main(["--period", "202606"]) == 1


def test_period_is_required():
    with pytest.raises(SystemExit) as exc:
        run.main([])
    assert exc.value.code == 2


def test_since_is_forwarded(calls):
    assert run.main(["--since", "202301"]) == 0
    assert calls["cnmv"] == ["--since", "202301"]


def test_period_and_since_are_mutually_exclusive():
    with pytest.raises(SystemExit) as exc:
        run.main(["--period", "202606", "--since", "202301"])
    assert exc.value.code == 2
