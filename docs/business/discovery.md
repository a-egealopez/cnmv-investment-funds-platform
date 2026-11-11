# CNMV Investment Funds Platform — Product Discovery

**Version**: 0.3 | **Date**: 2026-10-30 | **Status**: In development

---

## 1. Executive Summary

The CNMV Investment Funds Platform transforms raw CNMV regulatory XML and ECB benchmark data into a fund panorama, a candidate watchlist, and a flow/fee/quality layer. Up to 20 compartments are screened by **past** risk-adjusted performance (Sortino) within their CNMV investor vocation, backed by traceable quality screening. The watchlist is a filter on past performance, not a prediction. The project is also a dual-use portfolio: financial analysis for Deals/Financial Analytics roles and data engineering for Data Engineer roles.

## 2. Problem Statement

The CNMV publishes monthly and semiannual data on Spanish investment funds in XML format. While the data is official, free, and comprehensive, it is difficult to consume: files are large (15+ MB), deeply nested, and require significant processing before analysis is possible. There is no free tool that screens funds by risk-adjusted performance using this data. Investors who want a data-driven approach to fund research have no accessible option.

## 3. Target Users

**Primary (product)**: Individual investors seeking data-driven fund research. They want to identify funds with strong risk-adjusted returns and understand flows, fees and data quality without paying for expensive financial data services.

**Secondary (product)**: Financial analysts who need fund comparison and due-diligence tooling. They want to screen funds against peers, inspect concentration and detect unusual behaviour.

**Portfolio audience**: Deals/Financial Analytics teams (AUM bridge, fees, quality, anomalies, Power BI) and Data Engineering teams (PySpark, dbt, Airflow, Docker, Azure, CI/CD, observability).

## 4. Goals & Objectives

The platform produces (1) a **panorama**: every active share class with its status (eligible / quarantined with reason / short history), and (2) a **watchlist**: up to 20 compartments selected by Sortino percentile within CNMV investor vocation over a 36-month window, each with portfolio concentration metrics. Reading: the watchlist is a **past risk-adjusted performance filter** — it surfaces candidates to research, it does not predict future returns. Success means the pipeline runs end-to-end, covers 1,438 entities / 3,116 classes / 1,668 compartments, and produces metrics validated against source data. The watchlist is a candidate list, not investment advice.

## 5. Scope

**In scope (Release 1 — Deals/Analytics)**:
- PySpark parsing of FONDMENS, FONDREGISTRO, FONDTRIM, FONDCART and FONDPATRIMDISVAR XML into parquet tables (FONDPATRIMDISVAR pending)
- ECB €STR ingestion as risk-free benchmark (built)
- Quality gate and quarantine on the NAV series (`spark/jobs/validate_silver.py`, built)
- dbt models: weekly series, quality flags, metrics, panorama, watchlist, portfolio marts, flows, fees, scorecard and anomalies (next)
- Power BI dashboard with Executive Summary and Anomaly/Forensic tabs
- Jupyter notebooks for validation and calibration (partially built)

**In scope (Release 2 — Data Engineer)**:
- Airflow orchestration on Docker Compose
- ADLS Gen2, Azure SQL Database serverless, dbt-sqlserver
- Azure VM for Airflow, Key Vault, managed identity, Bicep, budget controls
- GitHub Actions with OIDC, observability and runbook

**Deferred**:
- IPP per-fund holdings parsing (portfolio uses FONDCART instead)
- FONDDERI ingestion (derivative usage signal)
- Databricks, ADF, Fabric, Kafka, Kubernetes, Terraform (not justified by the MVP)
- Web dashboard

## 6. User Stories

**US1**: As an investor, I want a shortlist of candidate funds screened by past risk-adjusted return within their vocation, so that I have a defensible starting point to research.

**US2**: As an investor, I want to know why a fund is absent from the list (quarantined, too small, no vocation), so that I can trust the selection.

**US3**: As an investor, I want to compare a fund against peers with the same investor vocation, so that I can judge relative rather than absolute performance.

**US4**: As an analyst, I want to see a fund's portfolio concentration and composition, so that I can assess hidden risk.

**US5**: As an analyst, I want every metric traceable to the original CNMV source, so that I can audit any number.

**US6**: As an analyst, I want to separate AUM growth caused by returns from growth caused by net flows, so that I can judge whether a fund is commercially growing or just appreciating.

**US7**: As an analyst, I want to decompose expenses into recurring management/custody and other costs, and see fee-revenue concentration, so that I can assess revenue quality.

**US8**: As an analyst, I want a data-quality scorecard and a ranked anomaly list, so that I can prioritise which funds need manual review.

## 7. Success Metrics

- Pipeline runs end-to-end without manual intervention
- Panorama covers every active class with an explicit status; no row silently dropped (quarantine with reason)
- Watchlist has ≤ 20 compartments, each satisfying eligibility rules (legal floors, EUR, vocation with ≥ 5 peers, quality screening)
- Portfolio metrics satisfy weight-sum and HHI invariants per compartment
- AUM bridge identity holds; fee identities (`GR`, `ING`, `RN`) hold
- Data-quality scorecard and anomaly list are populated for every `as_of_period`
- Every run records `as_of_period`, parameters and file hashes (reproducibility)
- Code passes linting (ruff) and CI/CD checks

## 8. Technical Approach

PySpark parses nested XML into Silver parquet tables; DuckDB is the local analytical database; dbt (dbt-duckdb) computes metrics and marts incrementally by `as_of_period`; Jupyter supports exploration and threshold calibration. Release 2 moves Bronze/Silver to ADLS Gen2, loads Silver into Azure SQL, runs dbt-sqlserver, and orchestrates with Airflow on an Azure VM. Weekly non-overlapping returns with √52 annualization follow the ESMA SRRI methodology on a 3-year window; the risk-free rate is the compounded €STR index. See `docs/technical/architecture.md` and `docs/analytics/financial_metrics.md`.

## 9. Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| 0 | Profiling & threshold calibration (FONDTRIM/FONDCART coverage, zero-week distribution, holdings coverage) | Done (notebooks 01/02) |
| 1 | New data: FONDTRIM, FONDCART, €STR ingestion + parsers + gates | Built |
| 2 | dbt: staging, window, flags, weekly series, quarantine | Planned |
| 3 | dbt: risk-free window, 36m class metrics, toy-seed tests | Planned |
| 4 | dbt: panorama + watchlist marts, run_log, tests | Planned |
| 5 | dbt: portfolio marts (concentration, allocation, top holdings) | Planned |
| 5b | dbt: flows, fees, quality, anomalies, executive summary | Planned |
| 6 | Reproducibility: versionable data sample + CI running `dbt build` | Planned |
| 7 | Power BI dashboard (2 tabs) + case study | Planned |
| 8 | Release 2: Airflow, Docker, ADLS, Azure SQL, Bicep, CI/CD | Future |

## 10. Risks & Assumptions

**Risks**:
- CNMV may change XML schema without notice
- Data quality issues (stale NAVs, extreme returns, gaps) — handled by quarantine, but false positives possible for very-low-volatility classes
- Survivorship bias: FONDREGISTRO only contains live funds; worst performers exit via merger/liquidation
- Top-of-ranking today does not predict top tomorrow (persistence is weak); the watchlist is explicitly framed as a past-performance filter, and is complemented by a fee filter and a persistence check (future improvements)
- CNMV vocations are coarse peer groups (e.g. *Renta Fija Euro* mixes durations); percentile within vocation × risk class is a possible future refinement
- Weekly Sortino ranking is noisy (~156 observations); sensitivity must be recorded
- FONDPATRIMDISVAR has no success fee and no gross flows; those analyses are documented as unavailable
- FONDCART has no issuer/sector; concentration is by instrument and asset type
- Azure adds cost and operational risk; mitigated with serverless, auto-shutdown and a budget alert

**Assumptions**:
- CNMV and ECB data remain freely available
- DuckDB is sufficient for the data volume (1,400+ entities)
- Weekly returns, √52 annualization (ESMA SRRI methodology, 3-year window)
- Portfolio weights computed over reported positions (treasury/derivatives inclusion to be confirmed against the XSD)
- FONDPATRIMDISVAR percentages are cumulative since the previous year-end; they are not annual rates

## 11. Open Questions

- Which benchmark to use for Beta/Alpha calculations? (IBEX 35, MSCI World, or CNMV fund proxy) — risk-free rate already resolved: compounded €STR index
- Should fee-based filtering be added to the watchlist once FONDPATRIMDISVAR fee yields are validated?
- Should the platform support a web interface instead of / in addition to Power BI?
- Should the platform support multiple languages?
