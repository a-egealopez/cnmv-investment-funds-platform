import zipfile
from pathlib import Path

import pytest

from ingestion.download_history import (
    COMPLETE_MARKER,
    MESES,
    extract_to_bronze,
    parse_year_page,
    sha256_of,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "cnmv_2025.html"


def test_fixture_has_all_months():
    assert len(MESES) == 12
    assert list(MESES.values()) == [f"{i:02d}" for i in range(1, 13)]


def test_parse_year_page_returns_12_periods():
    pares = parse_year_page(FIXTURE.read_text(encoding="utf-8"), 2025)
    assert len(pares) == 12
    assert pares[0] == ("202501", pares[0][1])
    assert pares[-1] == ("202512", pares[-1][1])
    assert [p for p, _ in pares] == sorted(p for p, _ in pares)


def test_parse_year_page_urls_point_to_cnmv_zip_service():
    pares = parse_year_page(FIXTURE.read_text(encoding="utf-8"), 2025)
    for _, url in pares:
        assert url.startswith("https://www.cnmv.es/webservices/verdocumento/ver?e=")


def test_parse_year_page_rejects_unknown_month():
    html = "<table id='ctl00_ContentPrincipal_grdDescargas'><tbody><tr><td>Smarch</td><td><a href='ver?e=x'/></td></tr></tbody></table>"
    with pytest.raises(ValueError, match="unexpected month"):
        parse_year_page(html, 2024)


def test_parse_year_page_rejects_missing_grid():
    with pytest.raises(ValueError, match="download grid not found"):
        parse_year_page("<html><body></body></html>", 2024)


def test_parse_year_page_rejects_incomplete_closed_year():
    html = "<table id='ctl00_ContentPrincipal_grdDescargas'><tbody><tr><td>Enero</td><td><a href='https://www.cnmv.es/webservices/verdocumento/ver?e=x'/></td></tr></tbody></table>"
    with pytest.raises(ValueError, match="expected 12"):
        parse_year_page(html, 2024)


def _zip_with(tmp_path: Path, periodo: str, names: list[str]) -> Path:
    path = tmp_path / f"cnmv_{periodo}.zip"
    with zipfile.ZipFile(path, "w") as zf:
        for name in names:
            zf.writestr(name, f"<{name} />")
    return path


def test_extract_to_bronze_writes_complete_marker(tmp_path):
    periodo = "202501"
    zip_path = _zip_with(
        tmp_path,
        periodo,
        [f"FONDMENS_{periodo}.xml", f"FONDREGISTRO_{periodo}.xml"],
    )

    destino = extract_to_bronze(periodo, zip_path, bronze_dir=tmp_path / "bronze")

    marker = destino / COMPLETE_MARKER
    assert marker.read_text().strip() == sha256_of(zip_path)
    assert (destino / f"FONDMENS_{periodo}.xml").exists()
    assert (destino / f"FONDREGISTRO_{periodo}.xml").exists()


def test_extract_to_bronze_rebuilds_incomplete_directory(tmp_path):
    periodo = "202502"
    zip_path = _zip_with(
        tmp_path,
        periodo,
        [f"FONDMENS_{periodo}.xml", f"FONDREGISTRO_{periodo}.xml"],
    )
    destino = tmp_path / "bronze" / f"cnmv_{periodo}"
    destino.mkdir(parents=True)
    (destino / f"FONDMENS_{periodo}.xml").write_text("partial")

    result = extract_to_bronze(periodo, zip_path, bronze_dir=tmp_path / "bronze")

    assert (result / f"FONDREGISTRO_{periodo}.xml").exists()
    assert (result / COMPLETE_MARKER).read_text().strip() == sha256_of(zip_path)


def test_extract_to_bronze_does_not_mark_missing_core_file(tmp_path):
    periodo = "202503"
    zip_path = _zip_with(tmp_path, periodo, [f"FONDMENS_{periodo}.xml"])

    with pytest.raises(ValueError, match="FONDREGISTRO"):
        extract_to_bronze(periodo, zip_path, bronze_dir=tmp_path / "bronze")

    assert not (tmp_path / "bronze" / f"cnmv_{periodo}" / COMPLETE_MARKER).exists()


def _patch_pipeline(monkeypatch, pares, fail_on=()):
    import ingestion.download_history as mod

    monkeypatch.setattr(mod, "fetch_year_html", lambda year: "")
    monkeypatch.setattr(mod, "parse_year_page", lambda html, year: pares)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    seen = []

    def fake_ingest(periodo, url):
        if periodo in fail_on:
            raise ValueError("boom")
        seen.append(periodo)

    monkeypatch.setattr(mod, "ingest_period", fake_ingest)
    return seen


PARES = [("202601", "u1"), ("202602", "u2")]


def test_run_history_reports_failed_periods(monkeypatch):
    from ingestion.download_history import run_history

    seen = _patch_pipeline(monkeypatch, PARES, fail_on={"202602"})
    hechos, fallidos = run_history(range(2026, 2027))

    assert hechos == ["202601"]
    assert fallidos == ["202602"]
    assert seen == ["202601"]


def test_main_run_exits_nonzero_when_a_period_fails(monkeypatch):
    from ingestion.download_history import main

    _patch_pipeline(monkeypatch, PARES, fail_on={"202602"})
    assert main(["--run", "2026-2026"]) == 1


def test_main_run_exits_zero_when_all_ok(monkeypatch):
    from ingestion.download_history import main

    _patch_pipeline(monkeypatch, PARES)
    assert main(["--run", "2026-2026"]) == 0


def test_main_period_ingests_only_that_month(monkeypatch):
    from ingestion.download_history import main

    seen = _patch_pipeline(monkeypatch, PARES)
    assert main(["--period", "202602"]) == 0
    assert seen == ["202602"]


def test_main_period_not_published_is_a_failure(monkeypatch):
    from ingestion.download_history import main

    seen = _patch_pipeline(monkeypatch, PARES)
    assert main(["--period", "202612"]) == 1
    assert seen == []


def test_main_period_rejects_bad_format(monkeypatch):
    from ingestion.download_history import main

    _patch_pipeline(monkeypatch, PARES)
    with pytest.raises(SystemExit):
        main(["--period", "2026-05"])


def test_run_history_since_skips_earlier_periods(monkeypatch):
    from ingestion.download_history import run_history

    seen = _patch_pipeline(monkeypatch, PARES)
    hechos, fallidos = run_history(range(2026, 2027), since="202602")

    assert hechos == ["202602"]
    assert fallidos == []
    assert seen == ["202602"]


def test_main_since_exits_zero_when_all_ok(monkeypatch):
    from ingestion.download_history import main

    _patch_pipeline(monkeypatch, PARES)
    assert main(["--since", "202601"]) == 0


def test_main_since_rejects_bad_format(monkeypatch):
    from ingestion.download_history import main

    _patch_pipeline(monkeypatch, PARES)
    with pytest.raises(SystemExit):
        main(["--since", "2026"])


def test_main_since_cannot_be_combined_with_period(monkeypatch):
    from ingestion.download_history import main

    _patch_pipeline(monkeypatch, PARES)
    with pytest.raises(SystemExit):
        main(["--since", "202601", "--period", "202602"])


def _patch_year_pages(monkeypatch, missing_year):
    import ingestion.download_history as mod

    def fake_parse(html, year):
        if year == missing_year:
            raise mod.YearNotPublished("download grid not found")
        return [(f"{year}12", "u")]

    monkeypatch.setattr(mod, "fetch_year_html", lambda year: "")
    monkeypatch.setattr(mod, "parse_year_page", fake_parse)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(mod, "ingest_period", lambda periodo, url: None)
    return mod


def test_since_tolerates_a_current_year_without_downloads(monkeypatch):
    import datetime as dt

    this_year = dt.date.today().year
    mod = _patch_year_pages(monkeypatch, missing_year=this_year)

    hechos, fallidos = mod.run_history(
        range(this_year - 1, this_year + 1), since="202001"
    )

    assert fallidos == []
    assert hechos == [f"{this_year - 1}12"]


def test_since_still_fails_when_a_closed_year_has_no_grid(monkeypatch):
    import datetime as dt

    this_year = dt.date.today().year
    mod = _patch_year_pages(monkeypatch, missing_year=this_year - 1)

    _, fallidos = mod.run_history(range(this_year - 1, this_year + 1), since="202001")

    assert fallidos == [f"year {this_year - 1}"]
