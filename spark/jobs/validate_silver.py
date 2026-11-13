"""Data-quality gate for the Silver datasets.

Run:  python -m spark.jobs.validate_silver   # exit 0 = healthy, 1 = structural FAIL
Reads the Silver artifacts read-only; writes nothing.

Tiers (the `kind` of each FINDINGS entry):
- structural — schema, keys, nulls, referential integrity. The only tier that
  may FAIL: a FAIL exits non-zero and blocks promotion to dbt.
- semantic — financial anomalies (negatives, zeros, frozen runs, ISINs).
  Never FAIL; filtering and quarantining those rows is dbt's job.

Destinations: gate (PASS/WARN/FAIL) | documented-only (INFO) | quarantine
(SKIP until dbt implements it). Every entry mirrors a row of the findings
table in notebooks/exploration/01_fondmens_fondregistro__nav_metadata_anomaly_profiling.ipynb §8 (source of truth).
"""

from collections import Counter
from pathlib import Path

from pyspark.sql import Window
from pyspark.sql import functions as F

from config import BRONZE_DIR, SILVER_DIR
from spark.common.session import get_spark
from spark.parsing.estr import EXPECTED_SCHEMA as ESTR_EXPECTED_SCHEMA
from spark.parsing.fondcart import EXPECTED_SCHEMA as CART_EXPECTED_SCHEMA
from spark.parsing.fondmens import EXPECTED_SCHEMA as NAV_EXPECTED_SCHEMA
from spark.parsing.fondpatrimdisvar import DECIMAL_FIELDS as FIN_DECIMAL_FIELDS
from spark.parsing.fondpatrimdisvar import EXPECTED_SCHEMA as FIN_EXPECTED_SCHEMA
from spark.parsing.fondregistro import EXPECTED_SCHEMA as META_EXPECTED_SCHEMA
from spark.parsing.fondtrim import EXPECTED_SCHEMA as TRIM_EXPECTED_SCHEMA

NAV_PATH = str(SILVER_DIR / "fund_nav_daily")
META_PATH = str(SILVER_DIR / "fund_metadata")
TRIM_PATH = str(SILVER_DIR / "fund_quarterly")
CART_PATH = str(SILVER_DIR / "fund_holdings")
FIN_PATH = str(SILVER_DIR / "fund_period_financials")
ESTR_PATH = str(SILVER_DIR / "estr_daily")
SEMESTER_MONTHS = {"06", "12"}
EXPECTED_ESTR_SERIES = {"EST.B.EU000A2QQF08.CI", "EST.B.EU000A2QQF16.CR"}

# Partition column: on read-back Spark re-infers its type (int, not string) and
# appends it last, so schema checks are order-agnostic and exempt its type.
PARTITION_COL = "FechaDatos"

NAV_KEY = ["Tipo", "NumeroRegistro", "NumeroCompartimento", "NumeroClase", "value_date"]
META_KEY = [
    "FechaDatos",
    "Tipo",
    "NumeroRegistro",
    "NumeroCompartimento",
    "NumeroClase",
]
NAV_CLASS_KEY = ["Tipo", "NumeroRegistro", "NumeroCompartimento", "NumeroClase"]
TRIM_KEY = [
    "FechaDatos",
    "Tipo",
    "NumeroRegistro",
    "NumeroCompartimento",
    "NumeroClase",
]
FIN_KEY = ["FechaDatos", "Tipo", "NumeroRegistro", "NumeroCompartimento"]
# Verified cadence: FONDTRIM/FONDCART only ship at the six-month closings.
# FONDPATRIMDISVAR is documented as quarterly, but every downloaded archive
# 2023-2025 only contains 06/12; the gate keeps 03/09 accepted defensively.
TRIM_MONTHS = {"06", "12"}
FIN_MONTHS = {"03", "06", "09", "12"}
ISIN_PATTERN = "^[A-Z]{2}[A-Z0-9]{9}[0-9]$"

# Participes counts *holders*, not units (FONDMENS PDF in bronze), so
# Patrimonio = VL * Participes is not an identity; these are the sign-coherence
# combos the source does support. SQL strings so the module imports without Spark.
AUM_WITHOUT_NAV = "Patrimonio > 0 AND VL <= 0"
AUM_WITHOUT_HOLDERS = "Patrimonio > 0 AND Participes <= 0"
NAV_WITHOUT_AUM = "VL > 0 AND Participes > 0 AND Patrimonio <= 0"

# >= FROZEN_VL_MIN_STREAK consecutive days with identical positive VL;
# a data hole longer than FROZEN_VL_MAX_GAP_DAYS starts a new run.
FROZEN_VL_MIN_STREAK = 5
FROZEN_VL_MAX_GAP_DAYS = 3

# |v| > 1 = material anomaly (dbt will quarantine), <= 1 = rounding dust. Both WARN.
NEG_DUST_MAX = 1


class Report:
    """Collects check results; FAIL (structural only) sets a non-zero exit code."""

    def __init__(self):
        self.results: list[tuple[str, str, str]] = []
        self.kinds: dict[str, str] = {}

    def add(
        self, status: str, name: str, detail: str, kind: str = "structural"
    ) -> None:
        self.results.append((status, name, detail))
        self.kinds[name] = kind
        print(f"{status:5} {name}: {detail}")

    def summary(self) -> int:
        counts = Counter(status for status, _, _ in self.results)
        by_kind = {
            kind: Counter(
                status
                for status, name, _ in self.results
                if self.kinds.get(name) == kind
            )
            for kind in ("structural", "semantic")
        }
        struct, sem = by_kind["structural"], by_kind["semantic"]
        print(
            "\n"
            f"structural: {struct['FAIL']} FAIL, {struct['PASS']} PASS | "
            f"semantic: {sem['WARN']} WARN, {sem['FAIL']} FAIL, "
            f"{sem['PASS']} PASS | {counts['INFO']} INFO, "
            f"{counts['SKIP']} SKIP"
        )
        return 1 if counts["FAIL"] else 0


def bronze_periods(bronze_dir=BRONZE_DIR) -> set[str]:
    """Periods present as Bronze directories (YYYYMM)."""
    return {
        p.name.removeprefix("cnmv_")
        for p in Path(bronze_dir).glob("cnmv_*")
        if p.is_dir()
    }


def expected_artifact_periods(artifact: str, bronze_dir=BRONZE_DIR) -> set[str]:
    """Periods a Silver artifact must cover, inferred from Bronze contents."""
    periodos = bronze_periods(bronze_dir)
    if artifact in {"fund_nav_daily", "fund_metadata"}:
        return periodos
    if artifact in {"fund_quarterly", "fund_holdings"}:
        return {p for p in periodos if p[4:6] in SEMESTER_MONTHS}
    if artifact == "fund_period_financials":
        explicit = {
            p.parent.name.removeprefix("cnmv_")
            for p in Path(bronze_dir).glob("cnmv_*/FONDPATRIMDISVAR_*.xml")
        }
        return {p for p in periodos if p[4:6] in SEMESTER_MONTHS} | explicit
    raise ValueError(f"unknown Silver artifact: {artifact}")


def compare_periods(
    actual: set[str], expected: set[str]
) -> tuple[list[str], list[str]]:
    """Return (missing, extra) periods, sorted for stable reporting."""
    return sorted(expected - actual), sorted(actual - expected)


def load_artifact(spark, report: Report, path: str, label: str):
    """Read a required Silver artifact; report FAIL when absent or empty."""
    p = Path(path)
    if not p.exists():
        report.add("FAIL", f"{label}_present", f"missing {p}", "structural")
        return None
    df = spark.read.parquet(str(p))
    if df.limit(1).count() == 0:
        report.add("FAIL", f"{label}_present", f"empty {p}", "structural")
        return None
    report.add("PASS", f"{label}_present", f"present and non-empty ({p})")
    return df


def report_period_coverage(report: Report, df, label: str, expected: set[str]) -> None:
    """Compare the partitions in Silver with the periods available in Bronze."""
    actual = {
        str(row[0])
        for row in df.select(F.col(PARTITION_COL).cast("string")).distinct().collect()
    }
    missing, extra = compare_periods(actual, expected)
    status = "PASS" if not missing and not extra else "FAIL"
    report.add(
        status,
        f"{label}_period_coverage",
        f"missing={missing}; extra={extra}",
        "structural",
    )


def frozen_vl_runs(
    nav, min_streak=FROZEN_VL_MIN_STREAK, max_gap_days=FROZEN_VL_MAX_GAP_DAYS
):
    """Runs of >= min_streak consecutive days with an identical positive VL.

    Zeros are excluded (covered by nav_zero_vl); a hole longer than
    max_gap_days starts a new run. One row per run.
    """
    w = Window.partitionBy(*NAV_CLASS_KEY).orderBy("value_date")
    flagged = (
        nav.filter(F.col("VL") > 0)
        .withColumn("prev_vl", F.lag("VL").over(w))
        .withColumn("prev_date", F.lag("value_date").over(w))
        .withColumn(
            "new_run",
            F.when(
                F.col("prev_date").isNull()
                | (F.date_diff(F.col("value_date"), F.col("prev_date")) > max_gap_days)
                | (F.col("VL") != F.col("prev_vl")),
                F.lit(1),
            ).otherwise(F.lit(0)),
        )
        .withColumn("run_id", F.sum("new_run").over(w))
    )
    return (
        flagged.groupBy(*NAV_CLASS_KEY, "run_id")
        .agg(
            F.count("*").alias("run_days"),
            F.min("value_date").alias("run_start"),
            F.max("value_date").alias("run_end"),
            F.min("VL").alias("vl_min"),
            F.max("VL").alias("vl_max"),
        )
        .filter(F.col("run_days") >= min_streak)
    )


def isin_changed_keys(nav):
    """Class keys whose ISIN is not stable across the history."""
    return (
        nav.filter(F.col("ISIN").isNotNull() & (F.trim(F.col("ISIN")) != ""))
        .groupBy(*NAV_CLASS_KEY)
        .agg(F.count_distinct("ISIN").alias("n_isins"))
        .filter(F.col("n_isins") > 1)
    )


def isin_reused_keys(meta):
    """ISINs on more than one class key — legitimate when the FONDMENS XSD scopes
    the ISIN to the compartimento/fund instead of the class, so WARN, never FAIL."""
    return (
        meta.filter(F.col("ISIN").isNotNull() & (F.trim(F.col("ISIN")) != ""))
        .groupBy("ISIN")
        .agg(F.count_distinct(*NAV_CLASS_KEY).alias("n_keys"))
        .filter(F.col("n_keys") > 1)
    )


def meta_without_nav(meta, nav):
    """Metadata class-months with no NAV rows (funds without a published daily series)."""
    return (
        meta.select(*META_KEY)
        .distinct()
        .join(nav.select(*META_KEY).distinct(), META_KEY, "left_anti")
    )


def schema_problems(df, expected):
    """Column/type drift vs EXPECTED_SCHEMA, ignoring column order and the
    partition column's type (see PARTITION_COL); every column must be present."""
    want = {f.name: f.dataType.simpleString() for f in expected}
    got = {f.name: f.dataType.simpleString() for f in df.schema}
    problems = [f"missing {c}" for c in want if c not in got]
    problems += [f"unexpected {c}: {t}" for c, t in got.items() if c not in want]
    problems += [
        f"{c}: expected {want[c]}, got {t}"
        for c, t in got.items()
        if c in want and c != PARTITION_COL and t != want[c]
    ]
    return problems


def check_nav_schema(nav, meta):
    problems = schema_problems(nav, NAV_EXPECTED_SCHEMA)
    detail = "; ".join(problems) if problems else "columns and types match"
    return len(problems), detail


def check_meta_schema(nav, meta):
    problems = schema_problems(meta, META_EXPECTED_SCHEMA)
    detail = "; ".join(problems) if problems else "columns and types match"
    return len(problems), detail


# ---------------------------------------------------------------- checks
# check(nav, meta) -> (violations, detail); the runner maps violations to status.


def nav_count(predicate, what):
    def check(nav, meta):
        n = nav.filter(predicate).count()
        return n, f"{n} {what}"

    return check


def meta_count(predicate, what):
    def check(nav, meta):
        n = meta.filter(predicate).count()
        return n, f"{n} {what}"

    return check


def check_nav_duplicate_keys(nav, meta):
    n = nav.groupBy(*NAV_KEY).count().filter("count > 1").count()
    return n, f"{n} duplicate key groups"


def check_meta_duplicate_keys(nav, meta):
    n = meta.groupBy(*META_KEY).count().filter("count > 1").count()
    return n, f"{n} duplicate key groups"


def check_frozen_vl_runs(nav, meta):
    frozen = frozen_vl_runs(nav)
    n = frozen.count()
    n_funds = frozen.select(*NAV_CLASS_KEY).distinct().count() if n else 0
    return n, f"{n} runs >= {FROZEN_VL_MIN_STREAK} days across {n_funds} funds"


def check_isin_changed(nav, meta):
    n = isin_changed_keys(nav).count()
    return n, f"{n} class keys with a non-stable ISIN"


def check_isin_format(nav, meta):
    n = (
        meta.select("ISIN")
        .distinct()
        .filter(f"NOT ISIN rlike '{ISIN_PATTERN}'")
        .count()
    )
    return n, f"{n} distinct ISINs fail the format pattern"


def check_nav_without_metadata(nav, meta):
    anti = (
        nav.select("FechaDatos", *NAV_CLASS_KEY)
        .distinct()
        .join(meta.select(*META_KEY).distinct(), META_KEY, "left_anti")
    )
    n = anti.count()
    return n, f"{n} class-months"


def check_isin_reused(nav, meta):
    n = isin_reused_keys(meta).count()
    return n, f"{n} ISINs appear on more than one class key"


def check_meta_without_nav(nav, meta):
    n = meta_without_nav(meta, nav).count()
    return n, f"{n} class-months"


# ---------------------------------------------------------------- quarterly (FONDTRIM)

# Metrics that must respect the sign conventions of a fund report; a negative
# expense ratio (observed: min -1.74) or negative volatility is a data error.
TRIM_NUM_POSITIVE = [
    "Patrimonio",
    "NumeroParticipes",
    "ValorLiquidativo",
    "Volatilidad_TrimestreActual",
    "Volatilidad_T_1",
    "Volatilidad_T_2",
    "Volatilidad_T_3",
    "RatioTotalGastos_TrimestreActual",
    "RatioTotalGastos_T_1",
    "RatioTotalGastos_T_2",
    "RatioTotalGastos_T_3",
]


def check_trim_schema(trim):
    problems = schema_problems(trim, TRIM_EXPECTED_SCHEMA)
    detail = "; ".join(problems) if problems else "columns and types match"
    return len(problems), detail


def check_trim_duplicate_keys(trim):
    n = trim.groupBy(*TRIM_KEY).count().filter("count > 1").count()
    return n, f"{n} duplicate key groups"


def check_trim_null_keys(trim):
    n = trim.filter(
        "FechaDatos IS NULL OR Tipo IS NULL OR NumeroRegistro IS NULL"
        " OR NumeroCompartimento IS NULL OR NumeroClase IS NULL"
    ).count()
    return n, f"{n} rows with null keys"


def check_trim_period_months(trim):
    n = (
        trim.filter(F.expr("substr(FechaDatos, 5, 2)") != F.lit("06"))
        .filter(F.expr("substr(FechaDatos, 5, 2)") != F.lit("12"))
        .count()
    )
    return n, f"{n} rows outside months {sorted(TRIM_MONTHS)}"


def check_trim_negative_metrics(trim):
    predicate = " OR ".join(f"{c} < 0" for c in TRIM_NUM_POSITIVE)
    n = trim.filter(predicate).count()
    return n, f"{n} rows with a negative known-nonnegative metric"


def check_trim_null_divisa_iic(trim):
    n = trim.filter("CodigoDivisaIIC IS NULL").count()
    return n, f"{n} rows with a null CodigoDivisaIIC"


# ---------------------------------------------------------------- financials (FONDPATRIMDISVAR)

# TotalPatrimonio is the period-end AUM. A non-positive value is a financial
# anomaly, not a parse failure; the same goes for a negative turnover index.
FIN_NONPOSITIVE_PATRIMONY = "TotalPatrimonio <= 0 OR PatrimonioFinPeriodoActual <= 0"
FIN_NEGATIVE_TURNOVER = (
    "IndiceRotacionCarteraActual < 0 OR IndiceRotacionCarteraAnterior < 0"
)


def check_fin_schema(fin):
    problems = schema_problems(fin, FIN_EXPECTED_SCHEMA)
    detail = "; ".join(problems) if problems else "columns and types match"
    return len(problems), detail


def check_fin_duplicate_keys(fin):
    n = fin.groupBy(*FIN_KEY).count().filter("count > 1").count()
    return n, f"{n} duplicate key groups"


def check_fin_null_keys(fin):
    n = fin.filter(
        "FechaDatos IS NULL OR Tipo IS NULL OR NumeroRegistro IS NULL"
        " OR NumeroCompartimento IS NULL"
    ).count()
    return n, f"{n} rows with null keys"


def check_fin_period_months(fin):
    n = (
        fin.filter(F.expr("substr(FechaDatos, 5, 2)") != F.lit("03"))
        .filter(F.expr("substr(FechaDatos, 5, 2)") != F.lit("06"))
        .filter(F.expr("substr(FechaDatos, 5, 2)") != F.lit("09"))
        .filter(F.expr("substr(FechaDatos, 5, 2)") != F.lit("12"))
        .count()
    )
    return n, f"{n} rows outside months {sorted(FIN_MONTHS)}"


def check_fin_non_fi(fin):
    n = fin.filter("Tipo IS NULL OR Tipo != 'FI'").count()
    return n, f"{n} rows outside the FI-only universe"


def check_fin_nonpositive_patrimony(fin):
    n = fin.filter(FIN_NONPOSITIVE_PATRIMONY).count()
    return n, f"{n} rows with non-positive period-end patrimony"


def check_fin_negative_turnover(fin):
    n = fin.filter(FIN_NEGATIVE_TURNOVER).count()
    return n, f"{n} rows with negative turnover index"


def check_fin_null_metrics(fin):
    predicate = " OR ".join(f"{name} IS NULL" for name in FIN_DECIMAL_FIELDS)
    n = fin.filter(predicate).count()
    return n, f"{n} rows with at least one null decimal field (optional in XSD)"


# ---------------------------------------------------------------- holdings (FONDCART)


def check_cart_schema(cart):
    problems = schema_problems(cart, CART_EXPECTED_SCHEMA)
    detail = "; ".join(problems) if problems else "columns and types match"
    return len(problems), detail


def check_cart_null_keys(cart):
    n = cart.filter(
        "FechaDatos IS NULL OR Tipo IS NULL OR NumeroRegistro IS NULL"
        " OR NumeroCompartimento IS NULL"
    ).count()
    return n, f"{n} rows with null keys"


def check_cart_nonpositive_value(cart):
    n = cart.filter("ValorMercado <= 0").count()
    return n, f"{n} positions with ValorMercado <= 0"


def check_cart_repeated_instrument(cart):
    n = (
        cart.groupBy(
            "Tipo",
            "NumeroRegistro",
            "NumeroCompartimento",
            "FechaDatos",
            "CodigoISIN",
            "ClaseIF",
        )
        .count()
        .filter("count > 1")
        .count()
    )
    return n, f"{n} same-instrument line groups in one compartment (aggregated in dbt)"


# ---------------------------------------------------------------- contract
# One entry per row of notebook 01 §8; list order = report order.
# Entry: id, kind, destination, level, check(nav, meta) -> (violations, detail);
# violations == 0 => PASS. documented-only / quarantine omit level.


def structural(id: str, check) -> dict:
    """Tier 1: may FAIL; FAIL exits 1 and blocks promotion to dbt."""
    return {
        "id": id,
        "kind": "structural",
        "destination": "gate",
        "level": "FAIL",
        "check": check,
    }


def semantic(id: str, check) -> dict:
    """Tier 2: never FAIL (dbt filters/quarantines those rows); WARN only."""
    return {
        "id": id,
        "kind": "semantic",
        "destination": "gate",
        "level": "WARN",
        "check": check,
    }


FINDINGS = [
    # structural — schema (artifact-level counterpart of the parsers' assert)
    structural("nav_schema", check_nav_schema),
    structural("meta_schema", check_meta_schema),
    # structural — keys and coherence
    structural("nav_duplicate_keys", check_nav_duplicate_keys),
    structural(
        "nav_null_keys",
        nav_count(
            "value_date IS NULL OR NumeroRegistro IS NULL"
            " OR NumeroCompartimento IS NULL OR NumeroClase IS NULL",
            "rows with null keys",
        ),
    ),
    structural(
        "nav_date_vs_fecha",
        nav_count(
            "date_format(value_date, 'yyyyMM') != FechaDatos",
            "rows where value_date month != FechaDatos",
        ),
    ),
    structural("meta_duplicate_keys", check_meta_duplicate_keys),
    structural(
        "meta_null_denominacion",
        meta_count("Denominacion IS NULL", "rows with null Denominacion"),
    ),
    structural("meta_null_isin", meta_count("ISIN IS NULL", "rows with null ISIN")),
    # structural — cross-table referential integrity
    structural("nav_without_metadata", check_nav_without_metadata),
    # semantic — negative values, split by the material/dust threshold
    semantic(
        "nav_neg_vl_material",
        nav_count(f"VL < -{NEG_DUST_MAX}", "rows with VL < -1 (material)"),
    ),
    semantic(
        "nav_neg_vl_dust",
        nav_count(f"VL >= -{NEG_DUST_MAX} AND VL < 0", "rows with -1 <= VL < 0 (dust)"),
    ),
    semantic(
        "nav_neg_aum_material",
        nav_count(
            f"Patrimonio < -{NEG_DUST_MAX}", "rows with Patrimonio < -1 (material)"
        ),
    ),
    semantic(
        "nav_neg_aum_dust",
        nav_count(
            f"Patrimonio >= -{NEG_DUST_MAX} AND Patrimonio < 0",
            "rows with -1 <= Patrimonio < 0 (dust)",
        ),
    ),
    semantic(
        "nav_neg_holders_material",
        nav_count(
            f"Participes < -{NEG_DUST_MAX}", "rows with Participes < -1 (material)"
        ),
    ),
    semantic(
        "nav_neg_holders_dust",
        nav_count(
            f"Participes >= -{NEG_DUST_MAX} AND Participes < 0",
            "rows with -1 <= Participes < 0 (dust)",
        ),
    ),
    # semantic — zeros and sign coherence
    semantic("nav_zero_vl", nav_count("VL = 0", "rows with VL = 0")),
    semantic(
        "nav_aum_without_nav",
        nav_count(AUM_WITHOUT_NAV, "rows with positive AUM and no NAV"),
    ),
    semantic(
        "nav_aum_without_holders",
        nav_count(AUM_WITHOUT_HOLDERS, "rows with positive AUM and no holders"),
    ),
    semantic(
        "nav_nav_without_aum",
        nav_count(NAV_WITHOUT_AUM, "rows with NAV+holders and no AUM"),
    ),
    # semantic — temporal continuity and ISIN stability
    semantic("nav_frozen_vl_runs", check_frozen_vl_runs),
    semantic("nav_isin_changed", check_isin_changed),
    # semantic — ISIN quality and coverage
    semantic("meta_isin_format", check_isin_format),
    semantic("meta_isin_reused", check_isin_reused),
    semantic("meta_without_nav", check_meta_without_nav),
    # the two exceptions keep an explicit dict (they need extra keys)
    {
        "id": "nav_metric_nulls",
        "kind": "semantic",
        "destination": "documented-only",
        "check": nav_count(
            "VL IS NULL OR Patrimonio IS NULL OR Participes IS NULL",
            "rows with any metric null",
        ),
    },
    {
        "id": "quarantine_negatives",
        "kind": "semantic",
        "destination": "quarantine",
        "implemented": False,
        "note": "negative-value rows (material + dust); wire up with the dbt quarantine layer",
    },
]

SECTIONS = (
    ("structural", "--- structural (blocking) ---"),
    ("semantic", "--- semantic (observability; quarantine lives in dbt) ---"),
)

TRIM_FINDINGS = [
    structural("trim_schema", check_trim_schema),
    structural("trim_duplicate_keys", check_trim_duplicate_keys),
    structural("trim_null_keys", check_trim_null_keys),
    structural("trim_period_months", check_trim_period_months),
    semantic("trim_negative_metrics", check_trim_negative_metrics),
    semantic("trim_null_divisa_iic", check_trim_null_divisa_iic),
]

CART_FINDINGS = [
    structural("cart_schema", check_cart_schema),
    structural("cart_null_keys", check_cart_null_keys),
    semantic("cart_nonpositive_value", check_cart_nonpositive_value),
    semantic("cart_repeated_instrument", check_cart_repeated_instrument),
]
FIN_FINDINGS = [
    structural("fin_schema", check_fin_schema),
    structural("fin_duplicate_keys", check_fin_duplicate_keys),
    structural("fin_null_keys", check_fin_null_keys),
    structural("fin_period_months", check_fin_period_months),
    semantic("fin_non_fi", check_fin_non_fi),
    semantic("fin_nonpositive_patrimony", check_fin_nonpositive_patrimony),
    semantic("fin_negative_turnover", check_fin_negative_turnover),
    {
        "id": "fin_null_metrics",
        "kind": "semantic",
        "destination": "documented-only",
        "check": check_fin_null_metrics,
    },
]

# Orphan compartments (in cart but not in NAV) are checked by the dbt tests of §7;
# the gate does not cross two artifacts that live in different layers.

# ---------------------------------------------------------------- estr_daily (ECB EST)

# Compounded rate (series key ending .CR) hovers around the deposit facility
# rate; anything outside these bounds is a units mistake, not a rate. The
# compounded index (.CI) grows from base 100, and only decimal overflow or a
# units mistake could take it beyond these generous limits.
ESTR_RATE_BOUNDS = (-5.0, 10.0)
ESTR_INDEX_UPPER = 1000.0


def check_estr_schema(estr):
    problems = schema_problems(estr, ESTR_EXPECTED_SCHEMA)
    detail = "; ".join(problems) if problems else "columns and types match"
    return len(problems), detail


def check_estr_duplicate_keys(estr):
    n = estr.groupBy("series", "value_date").count().filter("count > 1").count()
    return n, f"{n} duplicate key groups"


def check_estr_null_keys(estr):
    n = estr.filter("series IS NULL OR value_date IS NULL OR obs_value IS NULL").count()
    return n, f"{n} rows with null keys or value"


def check_estr_series(estr):
    actual = {row[0] for row in estr.select("series").distinct().collect()}
    missing = sorted(EXPECTED_ESTR_SERIES - actual)
    return len(missing), f"missing series: {missing}"


def check_estr_range(estr):
    pred = (
        "(substr(series, -2, 2) = 'CR'"
        f" AND (obs_value < {ESTR_RATE_BOUNDS[0]} OR obs_value > {ESTR_RATE_BOUNDS[1]}))"
        " OR (substr(series, -2, 2) = 'CI'"
        f" AND (obs_value <= 0 OR obs_value > {ESTR_INDEX_UPPER}))"
    )
    n = estr.filter(pred).count()
    return n, (
        f"{n} rows outside the rate bounds {ESTR_RATE_BOUNDS} "
        f"or the index bounds (0, {ESTR_INDEX_UPPER}]"
    )


ESTR_FINDINGS = [
    structural("estr_schema", check_estr_schema),
    structural("estr_duplicate_keys", check_estr_duplicate_keys),
    structural("estr_null_keys", check_estr_null_keys),
    structural("estr_series", check_estr_series),
    semantic("estr_range", check_estr_range),
]


def evaluate_generic(finding, report, *dfs) -> None:
    """Same contract as evaluate(), but the check receives its own artifacts."""
    kind = finding["kind"]
    if finding["destination"] == "quarantine":
        if not finding.get("implemented"):
            report.add("SKIP", finding["id"], f"deferred: {finding['note']}", kind)
        return
    n, detail = finding["check"](*dfs)
    if finding["destination"] == "documented-only":
        report.add("INFO", finding["id"], detail, kind)
        return
    status = "PASS" if n == 0 else finding["level"]
    if kind == "semantic" and status == "FAIL":
        status = "WARN"
    report.add(status, finding["id"], detail, kind)


def run_artifact(header: str, findings: list[dict], report: Report, *dfs) -> None:
    """Run the findings of one artifact (structural first, then semantic)."""
    print(f"\n{header}")
    for kind, kind_header in SECTIONS:
        print(f"\n{kind_header}")
        for finding in findings:
            if finding["kind"] == kind:
                evaluate_generic(finding, report, *dfs)


def evaluate(finding, nav, meta, report: Report) -> None:
    """Run one finding and record its status; semantic can never FAIL."""
    kind = finding["kind"]
    if finding["destination"] == "quarantine":
        if not finding.get("implemented"):
            report.add("SKIP", finding["id"], f"deferred: {finding['note']}", kind)
        return
    n, detail = finding["check"](nav, meta)
    if finding["destination"] == "documented-only":
        report.add("INFO", finding["id"], detail, kind)
        return
    status = "PASS" if n == 0 else finding["level"]
    if kind == "semantic" and status == "FAIL":
        status = "WARN"
    report.add(status, finding["id"], detail, kind)


def run_gate(nav, meta, report: Report) -> None:
    """Interpret the FINDINGS contract against the two Silver tables."""
    for kind, header in SECTIONS:
        print(f"\n{header}")
        for finding in FINDINGS:
            if finding["kind"] == kind:
                evaluate(finding, nav, meta, report)


def print_coverage(nav) -> None:
    print("\ncoverage (distinct funds per month):")
    (
        nav.groupBy("FechaDatos")
        .agg(F.count_distinct("NumeroRegistro").alias("funds"))
        .orderBy("FechaDatos")
        .show(45, truncate=False)
    )


def main() -> int:
    spark = get_spark("validate_silver")
    report = Report()
    try:
        nav = load_artifact(spark, report, NAV_PATH, "fund_nav_daily")
        meta = load_artifact(spark, report, META_PATH, "fund_metadata")
        if nav is None or meta is None:
            return report.summary()

        print(
            f"fund_nav_daily: {nav.count()} rows | fund_metadata: {meta.count()} rows\n"
        )
        run_gate(nav, meta, report)

        artifacts = [
            (
                TRIM_PATH,
                "fund_quarterly",
                "--- fund_quarterly (FONDTRIM, semestral 06/12) ---",
                TRIM_FINDINGS,
            ),
            (
                CART_PATH,
                "fund_holdings",
                "--- fund_holdings (FONDCART, semestral 06/12) ---",
                CART_FINDINGS,
            ),
            (
                FIN_PATH,
                "fund_period_financials",
                "--- fund_period_financials (FONDPATRIMDISVAR, nominal 03/06/09/12; observed 06/12) ---",
                FIN_FINDINGS,
            ),
        ]
        loaded = []
        for path, label, header, findings in artifacts:
            df = load_artifact(spark, report, path, label)
            if df is not None:
                loaded.append((df, label, header, findings))

        if Path(BRONZE_DIR).exists():
            report_period_coverage(
                report,
                nav,
                "fund_nav_daily",
                expected_artifact_periods("fund_nav_daily"),
            )
            report_period_coverage(
                report,
                meta,
                "fund_metadata",
                expected_artifact_periods("fund_metadata"),
            )
            for df, label, _, _ in loaded:
                report_period_coverage(
                    report, df, label, expected_artifact_periods(label)
                )
        else:
            report.add(
                "SKIP",
                "period_coverage",
                f"{BRONZE_DIR} not found; coverage not checked",
            )

        for df, label, header, findings in loaded:
            print(f"\n{label}: {df.count()} rows")
            run_artifact(header, findings, report, df)

        estr = load_artifact(spark, report, ESTR_PATH, "estr_daily")
        if estr is not None:
            print(f"\nestr_daily: {estr.count()} rows")
            run_artifact(
                "--- estr_daily (ECB EST, full history) ---",
                ESTR_FINDINGS,
                report,
                estr,
            )

        print_coverage(nav)
    finally:
        spark.stop()
    return report.summary()


if __name__ == "__main__":
    raise SystemExit(main())
