# python -m ingestion.run --period 202606    # one period
# python -m ingestion.run --since 202301     # every published period from then on

from __future__ import annotations

import argparse

from ingestion import download_ecb_estr, download_history


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CNMV period + ECB €STR ingestion")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--period", metavar="YYYYMM", help="one period, e.g. 202606")
    group.add_argument(
        "--since",
        metavar="YYYYMM",
        help="every published period from YYYYMM on, e.g. 202301",
    )
    args = parser.parse_args(argv)

    cnmv_args = ["--period", args.period] if args.period else ["--since", args.since]
    cnmv_status = download_history.main(cnmv_args)

    try:
        ecb_status = download_ecb_estr.main([])
    except Exception as e:  # noqa: BLE001 — report and fail, but only after the CNMV step ran
        print(f"FAILED ECB €STR: {e}")
        ecb_status = 1

    return 1 if cnmv_status or ecb_status else 0


if __name__ == "__main__":
    raise SystemExit(main())
