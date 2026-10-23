"""Data-quality gate for the Silver datasets.

Run:  python -m spark.jobs.validate_silver   # exit 0 = healthy, 1 = structural FAIL
Reads data/silver/{fund_nav_daily,fund_metadata} read-only; writes nothing.

Tiers (the `kind` of each FINDINGS entry):
- structural — schema, keys, nulls, referential integrity. The only tier that
  may FAIL: a FAIL exits non-zero and blocks promotion to dbt.
- semantic — financial anomalies (negatives, zeros, frozen runs, ISINs).
  Never FAIL; filtering and quarantining those rows is dbt's job.

Destinations: gate (PASS/WARN/FAIL) | documented-only (INFO) | quarantine
(SKIP until dbt implements it). Every entry mirrors a row of the findings
table in notebooks/exploration/01_profiling_silver.ipynb §8 (source of truth).
"""

from collections import Counter

from pyspark.sql import Window
from pyspark.sql import functions as F

from spark.common.session import get_spark
from spark.parsing.fondmens import EXPECTED_SCHEMA as NAV_EXPECTED_SCHEMA
from spark.parsing.fondregistro import EXPECTED_SCHEMA as META_EXPECTED_SCHEMA

NAV_PATH = "data/silver/fund_nav_daily"
META_PATH = "data/silver/fund_metadata"

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
        nav = spark.read.parquet(NAV_PATH)
        meta = spark.read.parquet(META_PATH)
        print(
            f"fund_nav_daily: {nav.count()} rows | fund_metadata: {meta.count()} rows\n"
        )
        run_gate(nav, meta, report)
        print_coverage(nav)
    finally:
        spark.stop()
    return report.summary()


if __name__ == "__main__":
    raise SystemExit(main())
