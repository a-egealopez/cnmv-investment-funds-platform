#   python -m spark.jobs.build_silver                  # every bronze period
#   python -m spark.jobs.build_silver --period 202605  # a single period
import argparse
from pathlib import Path

from config import BRONZE_DIR, COMPLETE_MARKER, ECB_RAW_DIR, SILVER_DIR
from spark.common.session import get_spark
from spark.parsing.estr import (
    parse_estr_csv,
)
from spark.parsing.estr import (
    validate_schema as validate_estr,
)
from spark.parsing.estr import (
    write_silver as write_estr,
)
from spark.parsing.fondcart import (
    parse_fondcart_xml,
)
from spark.parsing.fondcart import (
    validate_schema as validate_fondcart,
)
from spark.parsing.fondcart import (
    write_silver as write_holdings,
)
from spark.parsing.fondmens import (
    parse_fondmens_xml,
)
from spark.parsing.fondmens import (
    validate_schema as validate_fondmens,
)
from spark.parsing.fondmens import (
    write_silver as write_nav,
)
from spark.parsing.fondpatrimdisvar import (
    parse_fondpatrimdisvar_xml,
)
from spark.parsing.fondpatrimdisvar import (
    validate_schema as validate_financials,
)
from spark.parsing.fondpatrimdisvar import (
    write_silver as write_financials,
)
from spark.parsing.fondregistro import (
    parse_fondregistro_xml,
)
from spark.parsing.fondregistro import (
    validate_schema as validate_fondregistro,
)
from spark.parsing.fondregistro import (
    write_silver as write_metadata,
)
from spark.parsing.fondtrim import (
    parse_fondtrim_xml,
)
from spark.parsing.fondtrim import (
    validate_schema as validate_fondtrim,
)
from spark.parsing.fondtrim import (
    write_silver as write_quarterly,
)

NAV_OUT = str(SILVER_DIR / "fund_nav_daily")
META_OUT = str(SILVER_DIR / "fund_metadata")
QUARTERLY_OUT = str(SILVER_DIR / "fund_quarterly")
HOLDINGS_OUT = str(SILVER_DIR / "fund_holdings")
FINANCIALS_OUT = str(SILVER_DIR / "fund_period_financials")
ESTR_OUT = str(SILVER_DIR / "estr_daily")
ECB_DIR = ECB_RAW_DIR


def periods_in(bronze_dir: Path) -> list[str]:
    """Sorted YYYYMM periods available under the bronze dir."""
    return sorted(
        d.name.removeprefix("cnmv_") for d in bronze_dir.glob("cnmv_*") if d.is_dir()
    )


PROCESSED_DIR = SILVER_DIR / "_processed"


def bronze_fingerprint(bronze_dir: Path, periodo: str) -> str | None:
    """sha256 of the zip behind a bronze period; None if its extraction is incomplete."""
    marker = bronze_dir / f"cnmv_{periodo}" / COMPLETE_MARKER
    return marker.read_text().strip() if marker.exists() else None


def processed_fingerprint(processed_dir: Path, periodo: str) -> str | None:
    """Fingerprint the period had when it was last built into Silver, if ever."""
    marker = processed_dir / f"cnmv_{periodo}"
    return marker.read_text().strip() if marker.exists() else None


def mark_processed(processed_dir: Path, periodo: str, fingerprint: str) -> None:
    processed_dir.mkdir(parents=True, exist_ok=True)
    (processed_dir / f"cnmv_{periodo}").write_text(fingerprint + "\n")


def pending_periods(bronze_dir: Path, processed_dir: Path) -> list[str]:
    """Complete bronze periods never built, or whose source zip changed since."""
    pending = []
    for periodo in periods_in(bronze_dir):
        fingerprint = bronze_fingerprint(bronze_dir, periodo)
        if fingerprint is None:
            continue  # extraction unfinished: do not build from a partial period
        if fingerprint != processed_fingerprint(processed_dir, periodo):
            pending.append(periodo)
    return pending


def build_one(spark, periodo: str, bronze_dir: Path) -> None:
    """Parse and write the silver datasets available for one period."""
    mes = bronze_dir / f"cnmv_{periodo}"

    df = parse_fondmens_xml(spark, str(mes / f"FONDMENS_{periodo}.xml"))
    validate_fondmens(df)
    write_nav(df, NAV_OUT)

    df = parse_fondregistro_xml(spark, str(mes / f"FONDREGISTRO_{periodo}.xml"))
    validate_fondregistro(df)
    write_metadata(df, META_OUT)

    # FONDTRIM/FONDCART ship at the semi-annual closings (06/12).
    # FONDPATRIMDISVAR is documented as quarterly but the downloaded CNMV
    # archives only contain 06/12; parse whichever file exists.
    patrim = mes / f"FONDPATRIMDISVAR_{periodo}.xml"
    if patrim.exists():
        df = parse_fondpatrimdisvar_xml(spark, str(patrim))
        validate_financials(df)
        write_financials(df, FINANCIALS_OUT)

    trim = mes / f"FONDTRIM_{periodo}.xml"
    if trim.exists():
        df = parse_fondtrim_xml(spark, str(trim))
        validate_fondtrim(df)
        write_quarterly(df, QUARTERLY_OUT)

    cart = mes / f"FONDCART_{periodo}.xml"
    if cart.exists():
        df = parse_fondcart_xml(spark, str(cart))
        validate_fondcart(df)
        write_holdings(df, HOLDINGS_OUT)


def build_estr(spark) -> int:
    """Parse the ECB series once per run (absent until list downloaded)."""
    paths = sorted(ECB_DIR.glob("estr_*.csv"))
    if not paths:
        return 0
    df = parse_estr_csv(spark, [str(p) for p in paths])
    validate_estr(df)
    write_estr(df, ESTR_OUT)
    return df.count()


def select_periods(available: list[str], period: str | None) -> list[str]:
    if period is None:
        return available
    if period not in available:
        raise ValueError(f"period {period} not in bronze (have {len(available)})")
    return [period]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Silver from Bronze")
    parser.add_argument("--bronze-dir", type=Path, default=BRONZE_DIR)

    which = parser.add_mutually_exclusive_group()
    which.add_argument(
        "--period", metavar="YYYYMM", help="build a single period, e.g. 202605"
    )
    which.add_argument(
        "--pending",
        action="store_true",
        help="build only periods that are new or whose bronze changed since last built",
    )
    args = parser.parse_args(argv)

    available = periods_in(args.bronze_dir)
    if not available:
        print(f"No bronze periods under {args.bronze_dir}: run the ingestion first")
        return 1
    try:
        if args.pending:
            periodos = pending_periods(args.bronze_dir, PROCESSED_DIR)
        else:
            periodos = select_periods(available, args.period)
    except ValueError as e:
        print(f"FAILED: {e}")
        return 1
    if periodos:
        print(f"{len(periodos)} bronze periods: {periodos[0]}..{periodos[-1]}")
    else:
        print("0 periods pending: Silver is up to date")

    spark = get_spark("cnmv_build_silver")
    hechos: list[str] = []
    try:
        for periodo in periodos:
            try:
                build_one(spark, periodo, args.bronze_dir)
                fingerprint = bronze_fingerprint(args.bronze_dir, periodo)
                if fingerprint is not None:
                    mark_processed(PROCESSED_DIR, periodo, fingerprint)
                hechos.append(periodo)
                print(f"OK {periodo}")
            except Exception as e:  # noqa: BLE001 — bulk load: one bad period must not stop the run
                print(f"FAILED {periodo}: {e}")

        n_estr = build_estr(spark)
    finally:
        spark.stop()

    if n_estr:
        print(f"OK estr_daily ({n_estr} rows)")

    print(f"{len(hechos)}/{len(periodos)} periods done")
    return 0 if len(hechos) == len(periodos) else 1


if __name__ == "__main__":
    raise SystemExit(main())
