#    python -m ingestion.run --period 202606

from __future__ import annotations

import argparse

from ingestion import download_ecb_estr, download_history


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CNMV period + ECB €STR ingestion")
    parser.add_argument("--period", required=True, metavar="YYYYMM", help="e.g. 202606")
    args = parser.parse_args(argv)

    cnmv_status = download_history.main(["--period", args.period])

    try:
        ecb_status = download_ecb_estr.main([])
    except Exception as e:  # noqa: BLE001 — report and fail, but only after the CNMV step ran
        print(f"FAILED ECB €STR: {e}")
        ecb_status = 1

    return 1 if cnmv_status or ecb_status else 0


if __name__ == "__main__":
    raise SystemExit(main())
