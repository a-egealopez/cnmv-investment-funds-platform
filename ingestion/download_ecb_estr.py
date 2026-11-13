#    python -m ingestion.download_ecb_estr          # download both series
#    python -m ingestion.download_ecb_estr --check  # report shape of saved files

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
from pathlib import Path

import requests

from config import ECB_RAW_DIR as RAW_DIR

# ECB Data Portal, dataset EST (euro short-term rate). The two series we use:
#   CI: compounded index, base 100 at 2019-10-01 (a NAV-like series)
#   CR: compounded daily rate in percentage points (the actual benchmark rate)
SERIES = {
    "B.EU000A2QQF08.CI": ("estr_ci.csv", "estr compounded index"),
    "B.EU000A2QQF16.CR": ("estr_cr.csv", "estr compounded rate (%)"),
}
BASE_URL = "https://data-api.ecb.europa.eu/service/data/EST"
MANIFEST_PATH = RAW_DIR / "manifest.csv"
MANIFEST_FIELDS = ["series_key", "file_name", "downloaded_at", "sha256", "bytes"]
CSV_HEADER = [
    "KEY",
    "FREQ",
    "BENCHMARK_ITEM",
    "DATA_TYPE_EST",
    "TIME_PERIOD",
    "OBS_VALUE",
    "OBS_STATUS",
]


def save_key_from_csv(path: Path) -> str:
    """Validate the saved CSV shape and return its series key."""
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    header = lines[0].split(",")
    if header[: len(CSV_HEADER)] != CSV_HEADER:
        raise ValueError(f"unexpected CSV header in {path}: {header}")
    keys = {line.split(",", 1)[0] for line in lines[1:]}
    if len(keys) != 1:
        raise ValueError(f"expected a single series key in {path}: {sorted(keys)}")
    return keys.pop()


def append_manifest(row: dict, manifest: Path = MANIFEST_PATH) -> None:
    """Append one download row to data/raw/ecb/manifest.csv (last row wins)."""
    manifest.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not manifest.exists()
    with open(manifest, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if nuevo:
            w.writeheader()
        w.writerow(row)


def download_series(key: str, dest_dir: Path = RAW_DIR) -> tuple[Path, bool]:
    """Always fetch (the series grows daily); keep the new file only if valid and
    different. Returns (path, changed); the manifest logs only real changes."""
    name, _ = SERIES[key]
    dest = dest_dir / name
    part = dest_dir / f"{name}.part"

    dest_dir.mkdir(parents=True, exist_ok=True)
    url = f"{BASE_URL}/{key}?format=csvdata"
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with open(part, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    try:
        save_key_from_csv(part)
    except Exception:
        part.unlink(missing_ok=True)
        raise

    new_hash = sha256_of(part)
    if dest.exists() and sha256_of(dest) == new_hash:
        part.unlink()
        return dest, False

    part.replace(dest)
    append_manifest(
        {
            "series_key": key,
            "file_name": name,
            "downloaded_at": dt.datetime.now(dt.UTC).isoformat(),
            "sha256": new_hash,
            "bytes": dest.stat().st_size,
        }
    )
    return dest, True


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def check_saved(dest_dir: Path = RAW_DIR) -> list[str]:
    """Report shape of every saved series: rows, dates, value range."""
    informe: list[str] = []
    for ser, (name, label) in SERIES.items():
        path = dest_dir / name
        if not path.exists():
            informe.append(f"{label}: missing")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()[1:]
        filas = [line.split(",") for line in lines if line]
        dates = [f[4] for f in filas]
        values = [float(f[5]) for f in filas]
        informe.append(
            f"{label} ({ser}): {len(filas)} obs, "
            f"{min(dates)} to {max(dates)}, value {min(values)} to {max(values)}"
        )
    return informe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ECB EST series download")
    parser.add_argument("--check", action="store_true", help="inspect saved files")
    args = parser.parse_args(argv)

    if args.check:
        for line in check_saved():
            print(line)
        return 0

    for key, (_, label) in SERIES.items():
        path, changed = download_series(key)
        estado = "updated" if changed else "unchanged"
        print(f"{label}: {path} {estado} (sha256 {sha256_of(path)[:16]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
