# CNMV Fund Intelligence Platform — Product Discovery

**Version**: 0.1 | **Date**: 2026-09-26 | **Status**: Draft

---

## 1. Executive Summary

The CNMV Fund Intelligence Platform is a data engineering pipeline that transforms raw CNMV regulatory XML into actionable investment fund intelligence. It automates the full workflow from data ingestion to a ranked fund table based on risk-adjusted performance metrics, providing individual investors and financial analysts with a free, data-driven tool for fund selection.

## 2. Problem Statement

The CNMV publishes monthly data on Spanish investment funds in XML format. While the data is official, free, and comprehensive, it is difficult to consume: files are large (15+ MB), deeply nested, and require significant processing before analysis is possible. There is no free tool that screens funds by risk-adjusted performance using this data. Investors who want a data-driven approach to fund selection have no accessible option.

## 3. Target Users

**Primary**: Individual investors seeking data-driven fund selection. They want to identify funds with strong risk-adjusted returns without paying for expensive financial data services.

**Secondary**: Financial analysts who need fund comparison tooling. They want to quickly screen and compare funds based on standardized metrics.

## 4. Goals & Objectives

The platform produces a ranked fund table with the following metrics: CAGR, Sortino ratio, Calmar ratio, and maximum drawdown. The output answers: "Which funds offer the best risk-adjusted return?" Success means the pipeline runs end-to-end, covers 1,400+ funds, and produces metrics validated against source data.

## 5. Scope

**In scope (MVP)**:
- PySpark parsing of FONDMENS and FONDREGISTRO XML into parquet tables
- dbt models for financial metric calculation
- SQL queries to produce the fund ranking
- Jupyter notebook for validation and visualization

**Deferred**:
- IPP holdings parsing (Smart Money Tracker)
- Airflow orchestration
- Docker containerization
- Cloud deployment (Azure)
- Web dashboard

## 6. User Stories

**US1**: As an investor, I want to see a ranked list of funds by risk-adjusted return, so that I can decide where to invest.

**US2**: As an investor, I want to compare two funds side by side, so that I can choose the better option.

**US3**: As an investor, I want to track a fund's performance over time, so that I can distinguish consistent performance from luck.

## 7. Success Metrics

- Pipeline runs end-to-end without manual intervention
- Ranking contains 1,400+ funds
- Financial metrics are calculated correctly and validated against source CNMV data
- Code passes linting (ruff) and CI/CD checks

## 8. Technical Approach

The platform uses PySpark for XML parsing, DuckDB for analytical storage, dbt for SQL transformations, and Jupyter for exploration. This stack was chosen for its ability to handle nested XML, support advanced SQL (window functions, CTEs), and remain lightweight enough for a solo developer. See `docs/architecture.md` for details.

## 9. Roadmap

| Phase | Focus | Timeline |
|-------|-------|----------|
| 1 | PySpark: FONDMENS parsing | Week 1 |
| 2 | PySpark: FONDREGISTRO parsing | Week 2 |
| 3 | dbt: financial metrics models | Week 3 |
| 4 | SQL + Jupyter: fund ranking | Week 4 |
| 5 | IPP parsing (Smart Money Tracker) | Week 5 |
| 6 | Polish: docs, Docker, portfolio | Week 6 |

## 10. Risks & Assumptions

**Risks**:
- CNMV may change XML schema without notice
- Data quality issues (missing values, duplicates) may require cleaning
- Benchmark selection for advanced metrics (Beta, Alpha) is undecided

**Assumptions**:
- CNMV data remains freely available
- DuckDB is sufficient for the data volume (1,400+ funds)
- 252 trading days per year for annualization

## 11. Open Questions

- Which benchmark to use for Beta/Alpha calculations? (IBEX 35, MSCI World, or CNMV fund proxy)
- Should the platform support a web interface?
- Should the platform support multiple languages?
