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
