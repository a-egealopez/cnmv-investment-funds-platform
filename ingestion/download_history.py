#    python -m ingestion.download_history 2025                 # list (periodo, url) pairs
#    python -m ingestion.download_history --run 2023-2025      # full historical run

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import time
import zipfile
from pathlib import Path

import lxml.html
import requests

BASE_URL = (
    "https://www.cnmv.es/portal/publicaciones/descarga-informacion-individual.aspx"
)
TABLE_ID = "ctl00_ContentPrincipal_grdDescargas"

RAW_DIR = Path("data/raw")
BRONZE_DIR = Path("data/bronze")
MANIFEST_PATH = RAW_DIR / "manifest.csv"
MANIFEST_FIELDS = ["periodo", "url", "downloaded_at", "sha256", "bytes", "zip_name"]

MESES = {
    "Enero": "01",
    "Febrero": "02",
    "Marzo": "03",
    "Abril": "04",
    "Mayo": "05",
    "Junio": "06",
    "Julio": "07",
    "Agosto": "08",
    "Septiembre": "09",
    "Octubre": "10",
    "Noviembre": "11",
    "Diciembre": "12",
}


# Step 1 — index page -> [(periodo, url)]


def fetch_year_html(year: int, timeout: int = 30) -> str:
    """Download the CNMV index page for one year."""
    resp = requests.get(f"{BASE_URL}?ejercicio={year}", timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_year_page(html: str, year: int) -> list[tuple[str, str]]:
    """Extract (periodo, zip_url) pairs from a year index page."""
    doc = lxml.html.fromstring(html)
    tables = doc.xpath(f'//*[@id="{TABLE_ID}"]')
    if not tables:
        raise ValueError(f"download grid not found (id={TABLE_ID})")

    pares: list[tuple[str, str]] = []
    for tr in tables[0].xpath("./tbody/tr"):
        tds = tr.xpath("./td")
        mes = tds[0].text_content().strip()
        if mes not in MESES:
            raise ValueError(f"unexpected month cell: {mes!r}")
        url = tds[1].xpath(".//a/@href")[0]
        if "verdocumento" not in url:
            raise ValueError(f"unexpected download url for {mes}: {url!r}")
        pares.append((f"{year}{MESES[mes]}", url))

    periodos = [p for p, _ in pares]
    if len(periodos) != len(set(periodos)):
        raise ValueError(f"duplicate periods: {sorted(periodos)}")
    if not pares:
        raise ValueError("no download rows found")

    # Closed years must have all 12 months published.
    if year < dt.date.today().year and len(pares) != 12:
        raise ValueError(f"year {year} has {len(pares)} months, expected 12")

    return sorted(pares)


# Step 2 — (periodo, url) -> data/raw/cnmv_YYYYMM.zip


def download_zip(periodo: str, url: str, dest_dir: Path = RAW_DIR) -> Path:
    """Download one CNMV zip. Returns the path of the finished file."""
    dest = dest_dir / f"cnmv_{periodo}.zip"
    part = dest_dir / f"cnmv_{periodo}.zip.part"

    if dest.exists():
        return dest

    dest_dir.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with open(part, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    # every zip starts with the PK magic bytes; anything else is an error page
    with open(part, "rb") as f:
        if f.read(2) != b"PK":
            part.unlink()
            raise ValueError(f"not a zip: {part}")

    # atomic rename: dest only ever exists complete
    part.replace(dest)
    return dest


# Step 3 — sha256 + manifest.csv (real idempotency)


def sha256_of(path: Path) -> str:
    """Hex digest of a file, read in 1 MB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def append_manifest(row: dict, manifest: Path = MANIFEST_PATH) -> None:
    """Append one row to data/raw/manifest.csv, writing the header only once."""
    manifest.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not manifest.exists()
    with open(manifest, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if nuevo:
            w.writeheader()
        w.writerow(row)


def download_with_manifest(periodo: str, url: str) -> Path:
    """Download unless the manifest already has this periodo with a matching sha256."""
    zip_path = RAW_DIR / f"cnmv_{periodo}.zip"

    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, newline="") as f:
            registrados = [
                r["sha256"] for r in csv.DictReader(f) if r["periodo"] == periodo
            ]
        if registrados and zip_path.exists():
            # last manifest row wins; hash matches disk -> already downloaded
            if sha256_of(zip_path) == registrados[-1]:
                return zip_path
            zip_path.unlink()  # hash mismatch -> garbage; force re-download

    zip_path = download_zip(periodo, url)
    append_manifest(
        {
            "periodo": periodo,
            "url": url,
            "downloaded_at": dt.datetime.now(dt.UTC).isoformat(),
            "sha256": sha256_of(zip_path),
            "bytes": zip_path.stat().st_size,
            "zip_name": zip_path.name,
        }
    )
    return zip_path


# Step 4 — data/raw/cnmv_YYYYMM.zip -> data/bronze/cnmv_YYYYMM/


def extract_to_bronze(
    periodo: str, zip_path: Path, bronze_dir: Path = BRONZE_DIR
) -> Path:
    """Unzip into bronze/cnmv_YYYYMM/ and validate the expected files."""
    destino = bronze_dir / f"cnmv_{periodo}"

    # FONDMENS present -> a previous extraction completed (idempotency sentinel)
    if (destino / f"FONDMENS_{periodo}.xml").exists():
        return destino

    destino.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(destino)

    # drop Windows Zone.Identifier streams that were bundled into the zip
    for residuo in destino.glob("*Zone.Identifier"):
        residuo.unlink()

    # some periods ship undated/uppercase names (e.g. FONDMENS.XML); normalize
    for base in ("FONDMENS", "FONDREGISTRO"):
        canonical = destino / f"{base}_{periodo}.xml"
        if canonical.exists():
            continue
        match = next(
            (p for p in destino.iterdir() if p.name.lower() == f"{base.lower()}.xml"),
            None,
        )
        if match:
            match.rename(canonical)

    # both business XMLs must be present for downstream processing
    faltantes = [
        nombre
        for nombre in (f"FONDMENS_{periodo}.xml", f"FONDREGISTRO_{periodo}.xml")
        if not (destino / nombre).exists()
    ]
    if faltantes:
        raise ValueError(f"missing expected files in {destino}: {', '.join(faltantes)}")

    return destino


# Step 5 — loop a year range end to end


def run_history(years: range, delay: float = 1.0) -> list[str]:
    """List, download and extract every month in the given years."""
    hechos: list[str] = []
    for year in years:
        try:
            pares = parse_year_page(fetch_year_html(year), year)
        except Exception as e:  # noqa: BLE001 — bulk load: one bad year must not stop the run
            print(f"FAILED year {year}: {e}")
            continue
        for periodo, url in pares:
            try:
                zip_path = download_with_manifest(periodo, url)
                extract_to_bronze(periodo, zip_path)
                hechos.append(periodo)
            except Exception as e:  # noqa: BLE001 — bulk load: one bad period must not stop the run
                print(f"FAILED {periodo}: {e}")
            time.sleep(delay)
    print(f"{len(hechos)} periods done")
    return hechos


# CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CNMV historical download")
    parser.add_argument("year", type=int, nargs="?", help="exercise year, e.g. 2025")
    parser.add_argument(
        "--run",
        metavar="START-END",
        help="STEP 5: download and extract a year range, e.g. 2023-2025",
    )
    args = parser.parse_args(argv)

    if args.run:
        start, end = (int(y) for y in args.run.split("-"))
        run_history(range(start, end + 1))
        return 0

    if args.year is None:
        parser.error("give a year to list, or --run START-END for the full run")

    pares = parse_year_page(fetch_year_html(args.year), args.year)
    for periodo, url in pares:
        print(f"{periodo} {url}")
    print(f"{len(pares)} periods")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
