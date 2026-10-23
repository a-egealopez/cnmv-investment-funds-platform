#   python -m spark.jobs.build_silver
#   python -m spark.jobs.build_silver data/bronze
from pathlib import Path

from spark.common.session import get_spark
from spark.parsing.fondmens import (
    parse_fondmens_xml,
)
from spark.parsing.fondmens import (
    validate_schema as validate_fondmens,
)
from spark.parsing.fondmens import (
    write_silver as write_nav,
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

NAV_OUT = "data/silver/fund_nav_daily"
META_OUT = "data/silver/fund_metadata"


def periods_in(bronze_dir: Path) -> list[str]:
    """Sorted YYYYMM periods available under the bronze dir."""
    return sorted(
        d.name.removeprefix("cnmv_") for d in bronze_dir.glob("cnmv_*") if d.is_dir()
    )


def build_one(spark, periodo: str, bronze_dir: Path) -> None:
    """Parse and write both silver datasets for one period."""
    mes = bronze_dir / f"cnmv_{periodo}"

    df = parse_fondmens_xml(spark, str(mes / f"FONDMENS_{periodo}.xml"))
    validate_fondmens(df)
    write_nav(df, NAV_OUT)

    df = parse_fondregistro_xml(spark, str(mes / f"FONDREGISTRO_{periodo}.xml"))
    validate_fondregistro(df)
    write_metadata(df, META_OUT)


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
    finally:
        spark.stop()

    print(f"{len(hechos)}/{len(periodos)} periods done")
    return 0 if len(hechos) == len(periodos) else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(main(*sys.argv[1:2]))
