#   python -m spark.jobs.build_silver
#   python -m spark.jobs.build_silver data/bronze
from pathlib import Path

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

NAV_OUT = "data/silver/fund_nav_daily"
META_OUT = "data/silver/fund_metadata"
QUARTERLY_OUT = "data/silver/fund_quarterly"
HOLDINGS_OUT = "data/silver/fund_holdings"
FINANCIALS_OUT = "data/silver/fund_period_financials"
ESTR_OUT = "data/silver/estr_daily"
ECB_DIR = Path("data/raw/ecb")


def periods_in(bronze_dir: Path) -> list[str]:
    """Sorted YYYYMM periods available under the bronze dir."""
    return sorted(
        d.name.removeprefix("cnmv_") for d in bronze_dir.glob("cnmv_*") if d.is_dir()
    )


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


def main(bronze_dir: str = "data/bronze") -> int:
    periodos = periods_in(Path(bronze_dir))
    print(f"{len(periodos)} bronze periods: {periodos[0]}..{periodos[-1]}")

    spark = get_spark("cnmv_build_silver")
    hechos: list[str] = []
    try:
        for periodo in periodos:
            try:
                build_one(spark, periodo, Path(bronze_dir))
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
    import sys

    raise SystemExit(main(*sys.argv[1:2]))
