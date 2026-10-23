from pathlib import Path

import pytest

from ingestion.download_history import MESES, parse_year_page

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
