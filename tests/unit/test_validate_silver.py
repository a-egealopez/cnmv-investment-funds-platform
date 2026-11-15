from datetime import date
from decimal import Decimal

from pyspark.sql import functions as F

from spark.jobs.validate_silver import (
    AUM_WITHOUT_HOLDERS,
    AUM_WITHOUT_NAV,
    FINDINGS,
    NAV_WITHOUT_AUM,
    NEG_DUST_MAX,
    Report,
    bronze_periods,
    check_estr_series,
    check_meta_schema,
    check_nav_schema,
    compare_periods,
    expected_artifact_periods,
    frozen_vl_runs,
    isin_changed_keys,
    isin_reused_keys,
    meta_without_nav,
    report_period_coverage,
    run_gate,
)
from spark.parsing.fondmens import EXPECTED_SCHEMA as NAV_SCHEMA
from spark.parsing.fondregistro import EXPECTED_SCHEMA as META_SCHEMA

DAYS = [date(2026, 1, d) for d in range(1, 16)]


def nav_row(
    value_date,
    vl="10.0",
    participes=100,
    patrimonio="1000.0",
    fecha="202601",
    reg=1,
    comp=1,
    clase=1,
    isin: str | None = "ES0000000001",
):
    return (
        fecha,
        "FI",
        reg,
        comp,
        clase,
        isin,
        value_date,
        Decimal(vl),
        participes,
        Decimal(patrimonio),
    )


def meta_row(fecha="202601", reg=1, comp=1, clase=1, isin="ES0000000001"):
    return (
        fecha,
        "FI",
        reg,
        "FONDO TEST, FI",
        False,
        comp,
        "COMP",
        clase,
        "CLASE",
        isin,
        "GESTORA",
        1,
        "SGI",
        "GRUPO",
        "DEPO",
        1,
        "GRUPO DEPO",
    )


def make_nav(spark, rows):
    return spark.createDataFrame(rows, schema=NAV_SCHEMA)


def make_meta(spark, rows):
    return spark.createDataFrame(rows, schema=META_SCHEMA)


def test_frozen_vl_detects_streak_of_five(spark):
    rows = [nav_row(d, vl="10.0") for d in DAYS[0:5]]
    runs = frozen_vl_runs(make_nav(spark, rows)).collect()
    assert len(runs) == 1
    assert runs[0].run_days == 5
    assert float(runs[0].vl_min) == 10.0
    assert float(runs[0].vl_max) == 10.0


def test_frozen_vl_ignores_streak_shorter_than_min(spark):
    rows = [nav_row(d, vl="10.0") for d in DAYS[0:4]]
    assert frozen_vl_runs(make_nav(spark, rows)).count() == 0


def test_frozen_vl_breaks_when_value_changes(spark):
    rows = [nav_row(d, vl="10.0") for d in DAYS[0:5]]
    rows.append(nav_row(DAYS[5], vl="11.0"))
    runs = frozen_vl_runs(make_nav(spark, rows)).collect()
    assert len(runs) == 1
    assert runs[0].run_days == 5


def test_frozen_vl_breaks_after_data_hole(spark):
    rows = [nav_row(d, vl="10.0") for d in DAYS[0:5]]
    rows += [nav_row(d, vl="10.0") for d in DAYS[9:14]]
    assert frozen_vl_runs(make_nav(spark, rows)).count() == 2


def test_frozen_vl_excludes_zero_nav(spark):
    rows = [nav_row(d, vl="0.0") for d in DAYS[0:6]]
    assert frozen_vl_runs(make_nav(spark, rows)).count() == 0


def test_frozen_vl_isolated_per_key(spark):
    rows = [nav_row(d, reg=1) for d in DAYS[0:5]]
    rows += [nav_row(d, reg=2) for d in DAYS[0:5]]
    assert frozen_vl_runs(make_nav(spark, rows)).count() == 2


def test_sign_contradiction_predicates_are_disjoint_on_clean_rows(spark):
    rows = [
        nav_row(DAYS[0], vl="10.0", participes=100, patrimonio="1000.0"),
        nav_row(DAYS[1], vl="0.0", participes=50, patrimonio="1000.0"),
        nav_row(DAYS[2], vl="10.0", participes=0, patrimonio="1000.0"),
        nav_row(DAYS[3], vl="10.0", participes=100, patrimonio="0.0"),
    ]
    df = make_nav(spark, rows)
    assert df.filter(AUM_WITHOUT_NAV).count() == 1
    assert df.filter(AUM_WITHOUT_HOLDERS).count() == 1
    assert df.filter(NAV_WITHOUT_AUM).count() == 1
    combined = " OR ".join(
        f"({p})" for p in (AUM_WITHOUT_NAV, AUM_WITHOUT_HOLDERS, NAV_WITHOUT_AUM)
    )
    assert df.filter(combined).count() == 3


def test_isin_changed_key_detected(spark):
    rows = [
        nav_row(DAYS[0], isin="ES0000000001"),
        nav_row(DAYS[1], isin="ES0000000002"),
    ]
    assert isin_changed_keys(make_nav(spark, rows)).count() == 1


def test_isin_stable_key_not_flagged(spark):
    rows = [nav_row(DAYS[0]), nav_row(DAYS[1])]
    assert isin_changed_keys(make_nav(spark, rows)).count() == 0


def test_isin_changed_ignores_null_and_empty(spark):
    rows = [
        nav_row(DAYS[0], isin=None),
        nav_row(DAYS[1], isin=""),
        nav_row(DAYS[2], isin="ES0000000001"),
    ]
    assert isin_changed_keys(make_nav(spark, rows)).count() == 0


def test_isin_reused_across_keys_detected(spark):
    rows = [
        meta_row(clase=1, isin="ES0000000001"),
        meta_row(clase=2, isin="ES0000000001"),
    ]
    assert isin_reused_keys(make_meta(spark, rows)).count() == 1


def test_isin_unique_per_key_not_flagged(spark):
    rows = [
        meta_row(clase=1, isin="ES0000000001"),
        meta_row(clase=2, isin="ES0000000002"),
    ]
    assert isin_reused_keys(make_meta(spark, rows)).count() == 0


def test_meta_without_nav_detected(spark):
    meta = make_meta(spark, [meta_row(fecha="202601")])
    nav = make_nav(spark, [nav_row(DAYS[0], fecha="202602")])
    assert meta_without_nav(meta, nav).count() == 1


def test_meta_with_nav_not_flagged(spark):
    meta = make_meta(spark, [meta_row(fecha="202601")])
    nav = make_nav(spark, [nav_row(DAYS[0], fecha="202601")])
    assert meta_without_nav(meta, nav).count() == 0


def test_findings_ids_are_unique():
    ids = [f["id"] for f in FINDINGS]
    assert len(ids) == len(set(ids))


def test_findings_destinations_and_levels_are_valid():
    valid_destinations = {"gate", "quarantine", "documented-only"}
    for f in FINDINGS:
        assert f["destination"] in valid_destinations, f["id"]
        if f["destination"] == "gate":
            assert f["level"] in {"FAIL", "WARN"}, f["id"]
        if f["destination"] == "quarantine":
            assert "implemented" in f, f["id"]


def test_findings_gate_checks_are_callable():
    for f in FINDINGS:
        if f["destination"] in {"gate", "documented-only"}:
            assert callable(f["check"]), f["id"]


def test_every_finding_declares_kind():
    for f in FINDINGS:
        assert f["kind"] in {"structural", "semantic"}, f["id"]


def test_semantic_findings_never_declare_fail():
    for f in FINDINGS:
        if f["kind"] == "semantic":
            assert f.get("level") != "FAIL", f["id"]


def test_structural_failure_sets_nonzero_exit(spark):
    rows = [nav_row(DAYS[0]), nav_row(DAYS[0])]
    nav = make_nav(spark, rows)
    meta = make_meta(spark, [meta_row(fecha="202601")])
    report = Report()
    run_gate(nav, meta, report)
    statuses = {name: status for status, name, _ in report.results}
    assert statuses["nav_duplicate_keys"] == "FAIL"
    assert report.summary() == 1


def test_neg_dust_max_is_one():
    assert NEG_DUST_MAX == 1


def test_run_gate_on_clean_data_all_pass(spark):
    rows = [
        nav_row(d, vl=f"{10 + i}.0", patrimonio=f"{1000 + i}.0")
        for i, d in enumerate(DAYS)
    ]
    nav = make_nav(spark, rows)
    meta = make_meta(spark, [meta_row(fecha="202601")])
    report = Report()
    run_gate(nav, meta, report)
    statuses = {name: status for status, name, _ in report.results}
    assert all(s in ("PASS", "INFO", "SKIP") for s in statuses.values()), statuses
    assert report.summary() == 0


def test_run_gate_warns_on_material_negative_vl(spark):
    rows = [nav_row(DAYS[0], vl="10.0"), nav_row(DAYS[1], vl=f"{-NEG_DUST_MAX - 1}.5")]
    nav = make_nav(spark, rows)
    meta = make_meta(spark, [meta_row(fecha="202601")])
    report = Report()
    run_gate(nav, meta, report)
    statuses = {name: status for status, name, _ in report.results}
    assert statuses["nav_neg_vl_material"] == "WARN"
    assert statuses["nav_neg_vl_dust"] == "PASS"
    assert report.summary() == 0


def test_run_gate_warns_on_dust_negative(spark):
    rows = [nav_row(DAYS[0], vl="10.0"), nav_row(DAYS[1], patrimonio="-0.01")]
    nav = make_nav(spark, rows)
    meta = make_meta(spark, [meta_row(fecha="202601")])
    report = Report()
    run_gate(nav, meta, report)
    statuses = {name: status for status, name, _ in report.results}
    assert statuses["nav_neg_aum_dust"] == "WARN"
    assert statuses["nav_neg_aum_material"] == "PASS"
    assert report.summary() == 0


def test_run_gate_skips_unimplemented_quarantine(spark):
    nav = make_nav(spark, [nav_row(DAYS[0])])
    meta = make_meta(spark, [meta_row(fecha="202601")])
    report = Report()
    run_gate(nav, meta, report)
    quarantine = [
        (s, d) for s, name, d in report.results if name == "quarantine_negatives"
    ]
    assert quarantine and quarantine[0][0] == "SKIP"


def test_schema_checks_pass_on_parser_schema(spark):
    nav = make_nav(spark, [nav_row(DAYS[0])])
    meta = make_meta(spark, [meta_row()])
    assert check_nav_schema(nav, meta)[0] == 0
    assert check_meta_schema(nav, meta)[0] == 0


def test_nav_schema_flags_missing_column(spark):
    nav = make_nav(spark, [nav_row(DAYS[0])]).drop("Patrimonio")
    n, detail = check_nav_schema(nav, None)
    assert n == 1
    assert "missing Patrimonio" in detail


def test_meta_schema_flags_missing_column(spark):
    meta = make_meta(spark, [meta_row()]).drop("ISIN")
    n, detail = check_meta_schema(None, meta)
    assert n == 1
    assert "missing ISIN" in detail


def test_nav_schema_flags_type_drift(spark):
    nav = make_nav(spark, [nav_row(DAYS[0])]).withColumn(
        "Participes", F.col("Participes").cast("string")
    )
    n, detail = check_nav_schema(nav, None)
    assert n == 1
    assert "Participes" in detail


def test_schema_check_exempts_partition_column_type_and_order(spark):
    nav = make_nav(spark, [nav_row(DAYS[0])])
    read_back = nav.select(
        *[F.col(c) for c in nav.columns if c != "FechaDatos"],
        F.col("FechaDatos").cast("int"),
    )
    assert check_nav_schema(read_back, None)[0] == 0


def test_bronze_periods_only_counts_cnmv_directories(tmp_path):
    (tmp_path / "cnmv_202301").mkdir()
    (tmp_path / "cnmv_202312").mkdir()
    (tmp_path / "not_a_period").mkdir()

    assert bronze_periods(tmp_path) == {"202301", "202312"}


def test_expected_artifact_periods_follow_source_cadence(tmp_path):
    for periodo in ("202301", "202306", "202309", "202312"):
        (tmp_path / f"cnmv_{periodo}").mkdir()
    (tmp_path / "cnmv_202309" / "FONDPATRIMDISVAR_202309.xml").write_text("<x />")

    assert expected_artifact_periods("fund_nav_daily", tmp_path) == {
        "202301",
        "202306",
        "202309",
        "202312",
    }
    assert expected_artifact_periods("fund_quarterly", tmp_path) == {
        "202306",
        "202312",
    }
    # Silver keeps only the semiannual closings, even when Bronze has a 03/09 file.
    assert expected_artifact_periods("fund_period_financials", tmp_path) == {
        "202306",
        "202312",
    }


def test_compare_periods_reports_missing_and_extra():
    missing, extra = compare_periods({"202301", "202305"}, {"202301", "202306"})
    assert missing == ["202306"]
    assert extra == ["202305"]


def test_period_coverage_casts_partition_column_to_string(spark):
    report = Report()
    df = spark.createDataFrame([(202301,), (202306,)], ["FechaDatos"])

    report_period_coverage(report, df, "test", {"202301"})

    assert (
        "FAIL",
        "test_period_coverage",
        "missing=[]; extra=['202306']",
    ) in report.results


def test_estr_series_detects_missing_rate_series(spark):
    df = spark.createDataFrame([("EST.B.EU000A2QQF08.CI",)], ["series"])

    violations, detail = check_estr_series(df)

    assert violations == 1
    assert "EST.B.EU000A2QQF16.CR" in detail
