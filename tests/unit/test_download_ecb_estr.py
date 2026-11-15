import pytest

from ingestion.download_ecb_estr import CSV_HEADER, save_key_from_csv
from tests.unit.fake_http import FakeResponse

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


def _serve(monkeypatch, body: str):
    import ingestion.download_ecb_estr as mod

    monkeypatch.setattr(
        mod.requests, "get", lambda *a, **k: FakeResponse(body.encode())
    )


def test_download_series_first_time_saves_and_logs(tmp_path, monkeypatch):
    import ingestion.download_ecb_estr as mod

    rows = []
    monkeypatch.setattr(mod, "append_manifest", lambda row: rows.append(row))
    _serve(monkeypatch, _csv([KEY]))

    path, changed = mod.download_series("B.EU000A2QQF16.CR", tmp_path)

    assert changed is True
    assert path.exists()
    assert not (tmp_path / "estr_cr.csv.part").exists()
    assert len(rows) == 1


def test_download_series_same_content_is_unchanged(tmp_path, monkeypatch):
    import ingestion.download_ecb_estr as mod

    rows = []
    monkeypatch.setattr(mod, "append_manifest", lambda row: rows.append(row))
    _serve(monkeypatch, _csv([KEY]))

    mod.download_series("B.EU000A2QQF16.CR", tmp_path)
    _, changed = mod.download_series("B.EU000A2QQF16.CR", tmp_path)

    assert changed is False
    assert len(rows) == 1
    assert not (tmp_path / "estr_cr.csv.part").exists()


def test_download_series_new_content_replaces_and_logs(tmp_path, monkeypatch):
    import ingestion.download_ecb_estr as mod

    rows = []
    monkeypatch.setattr(mod, "append_manifest", lambda row: rows.append(row))
    _serve(monkeypatch, _csv([KEY]))
    mod.download_series("B.EU000A2QQF16.CR", tmp_path)

    _serve(monkeypatch, _csv([KEY, KEY]))
    path, changed = mod.download_series("B.EU000A2QQF16.CR", tmp_path)

    assert changed is True
    assert len(path.read_text().strip().splitlines()) == 3
    assert len(rows) == 2


def test_download_series_bad_payload_keeps_good_file(tmp_path, monkeypatch):
    import ingestion.download_ecb_estr as mod

    monkeypatch.setattr(mod, "append_manifest", lambda row: None)
    _serve(monkeypatch, _csv([KEY]))
    path, _ = mod.download_series("B.EU000A2QQF16.CR", tmp_path)
    good = path.read_text()

    _serve(monkeypatch, "FOO,BAR\nX,1\n")
    with pytest.raises(ValueError, match="unexpected CSV header"):
        mod.download_series("B.EU000A2QQF16.CR", tmp_path)

    assert path.read_text() == good
    assert not (tmp_path / "estr_cr.csv.part").exists()
