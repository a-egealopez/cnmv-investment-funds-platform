# AGENTS.md

## 1. Project Overview

### Project

**CNMV Fund Intelligence Platform**

### Objective

Build a production-oriented Data Engineering and Financial Analytics platform using public data published by the **Comisión Nacional del Mercado de Valores (CNMV)**.

The platform must ingest, normalize, validate and transform public information about Spanish investment funds and generate analytical outputs related to:

* Fund performance
* Net Asset Value (NAV)
* Assets under management
* Investors/participants
* Portfolio composition
* Asset allocation
* Fees and expenses
* Risk indicators
* Portfolio concentration
* Fund similarity
* Anomaly detection

The final product should look like a **real internal data platform used by a financial institution**, not simply a data analysis notebook.

The project is also a **learning project**. The developer should understand the architecture, technologies, decisions and code rather than delegate implementation to the AI agent.

---

## 2. Learning Philosophy

The primary objective of this project is **learning through incremental construction**.

The AI agent acts primarily as:

* mentor;
* reviewer;
* debugger;
* architecture advisor;
* documentation assistant.

The developer remains the primary implementer.

### Core principle

**Build from small objectives toward larger objectives.**

Do not attempt to design and implement the entire platform upfront.

Progress should follow a sequence similar to:

```text
Small objective
    ↓
Working implementation
    ↓
Understand what was built
    ↓
Validate
    ↓
Identify limitations
    ↓
Refactor if necessary
    ↓
Larger objective
```

Each stage should produce something working and understandable.

### Refactoring is expected

Previous code is **not sacred**.

As understanding improves or a larger objective exposes a better architecture, the existing implementation should be reconsidered.

It is acceptable and encouraged to:

* refactor;
* rename;
* move files;
* change interfaces;
* redesign schemas;
* replace an earlier implementation;
* remove abstractions that are no longer useful;
* migrate from a simple implementation to a more scalable one.

Do not preserve poor design merely to avoid rewriting code.

### Optimize for learning, not code preservation

When choosing between:

* keeping existing code untouched; or
* restructuring it to better support the next objective;

prefer the option that produces the **better learning outcome and clearer architecture**, provided the change is justified.

The developer should understand **why** a refactor is necessary.

### Avoid premature complexity

Do not introduce production-grade complexity before it is justified by the current objective.

Examples of technologies/features that should not be introduced merely because they are common in enterprise environments:

* Kubernetes
* Kafka
* Terraform
* cloud-specific services
* complex CI/CD
* elaborate microservices
* unnecessary abstractions
* complex ML pipelines

Complexity should appear as a response to an actual project requirement.

---

## 3. Progressive Objectives

The project should evolve through increasingly ambitious objectives.

### Objective 1 — Understand one real CNMV dataset

Start with a small, real CNMV file.

The first objective is simply:

```text
CNMV
  ↓
Real source file
  ↓
Understand its structure
```

Do not begin by designing the final data platform.

The developer should understand:

* source structure;
* fields;
* identifiers;
* reporting periods;
* optional fields;
* schema variations;
* data quality issues.

---

### Objective 2 — Read and transform the source

Build the smallest possible implementation that can:

```text
Raw CNMV file
    ↓
Read
    ↓
Parse
    ↓
Structured records
```

The implementation can initially be simple.

Do not introduce distributed processing merely because PySpark is part of the final stack.

Introduce PySpark when the current objective requires or benefits from it.

---

### Objective 3 — Persist raw data

Introduce the Bronze layer:

```text
CNMV
  ↓
Raw file
  ↓
Bronze
```

At this point learn:

* raw data;
* provenance;
* metadata;
* reproducibility;
* immutable source preservation.

---

### Objective 4 — Build a normalized Silver dataset

Transform the raw source into clean entities:

```text
Bronze
  ↓
PySpark
  ↓
Silver
```

Introduce schemas, datatypes, normalization and data quality progressively.

---

### Objective 5 — Introduce dbt

Once there is a meaningful Silver dataset, introduce dbt for:

* analytical transformations;
* business logic;
* tests;
* documentation;
* lineage.

Do not introduce dbt before there is a clear transformation problem for it to solve.

---

### Objective 6 — Introduce Airflow

Once ingestion and transformation work manually, introduce orchestration:

```text
Airflow
   ↓
Ingestion
   ↓
PySpark
   ↓
dbt
```

Airflow should solve an actual orchestration problem:

* scheduling;
* dependencies;
* retries;
* failure handling;
* backfills.

---

### Objective 7 — Historical and incremental processing

Once a single period works, expand toward:

```text
One period
    ↓
Several periods
    ↓
Historical dataset
    ↓
Incremental ingestion
```

The architecture should evolve when scale and historical requirements justify it.

---

### Objective 8 — Financial analytics

Once the data foundation is reliable, add:

* returns;
* volatility;
* drawdown;
* concentration;
* portfolio exposure;
* expense ratios;
* other justified financial metrics.

---

### Objective 9 — Anomaly detection and peer analysis

Only after the underlying data is reliable should we introduce:

* z-scores;
* rolling statistics;
* anomaly detection;
* similarity;
* clustering;
* peer analysis.

---

### Objective 10 — Final data product

The final platform should evolve toward:

```text
Official CNMV data
        ↓
Airflow
        ↓
Bronze
        ↓
PySpark
        ↓
Silver
        ↓
dbt
        ↓
Gold
        ↓
Risk / Analytics
        ↓
User interface
```

The architecture should emerge through the objectives rather than being implemented all at once.

---

## 4. Main Business Use Cases

The platform should allow a user to:

1. Monitor a universe of investment funds.
2. Identify funds showing statistically unusual behavior.
3. Investigate why a fund has been flagged.
4. Analyze portfolio composition and concentration.
5. Compare a fund against a peer group.
6. Identify funds with similar portfolios.
7. Analyze how a portfolio changes over time.
8. Trace analytical metrics back to the original CNMV source data.

The system produces **analytical signals**, not regulatory or legal conclusions.

---

## 5. Data Source Policy

### Primary source

Use **official CNMV public data** as the primary source.

Potential sources include:

* CNMV individual IIC information
* CNMV fund statistics
* CNMV public regulatory information
* CNMV XML/XSD files
* Other official CNMV datasets when relevant

### Source principles

* Prefer official government/regulatory sources.
* Do not use Kaggle as a primary source.
* Do not use commercial financial datasets as a primary source.
* Do not scrape websites when an official API or downloadable file exists.
* Preserve the original source files.
* Every processed record must be traceable to its source.

### Data provenance

Every ingestion process should capture, where available:

* source URL
* source file name
* ingestion timestamp
* reporting period
* file hash
* schema/version
* processing version

---

## 6. Mandatory Technology Stack

The following technologies are mandatory for the final architecture.

### Orchestration

**Apache Airflow**

Responsibilities:

* Schedule ingestion jobs.
* Manage dependencies.
* Handle retries and failures.
* Support backfills.
* Track task status.
* Trigger downstream transformation processes.

Airflow should orchestrate the pipeline, not perform heavy data processing.

### Distributed Processing

**PySpark**

Responsibilities:

* Parse large XML/JSON/CSV files.
* Perform distributed transformations.
* Normalize heterogeneous source structures.
* Execute large joins and aggregations.
* Prepare data for analytical models.

PySpark should be introduced progressively when the project objective justifies it.

### Transformation and Data Quality

**dbt**

Responsibilities:

* Build Silver and Gold transformation models.
* Implement business logic.
* Create reusable SQL models.
* Document datasets.
* Maintain lineage.
* Implement data quality tests using `dbt test`.

dbt should be introduced once there is a meaningful transformation layer.

---

## 7. Architecture

Use a **Medallion Architecture**.

```text
CNMV
 │
 ▼
Apache Airflow
 │
 ▼
BRONZE
 │
 │ raw source data
 │
 ▼
PySpark
 │
 ▼
SILVER
 │
 │ standardized analytical entities
 │
 ▼
dbt
 │
 ▼
GOLD
 │
 │ business-ready data products
 │
 ▼
Dashboard / Analytics / API
```

### Bronze

Bronze must contain raw source data with minimal transformation.

Examples:

* Raw XML
* Raw XSD
* Raw CSV
* Raw JSON
* Metadata
* File hashes
* Ingestion logs

Bronze data must be immutable whenever practical.

### Silver

Silver must contain clean, normalized and standardized data.

Typical entities:

* `fund`
* `fund_period`
* `fund_nav`
* `fund_participants`
* `fund_holdings`
* `fund_asset_allocation`
* `fund_returns`
* `fund_expenses`

### Gold

Gold contains business-ready analytical datasets.

Potential marts:

* `mart_fund_performance`
* `mart_fund_risk`
* `mart_fund_concentration`
* `mart_fund_peer_analysis`
* `mart_fund_anomalies`
* `mart_fund_similarity`

---

## 8. Proposed Repository Structure

```text
.
├── AGENTS.md
├── README.md
├── docker-compose.yml
│
├── dags/
│   ├── cnmv_ingestion.py
│   ├── cnmv_validation.py
│   └── cnmv_pipeline.py
│
├── spark/
│   ├── ingestion/
│   ├── parsing/
│   ├── normalization/
│   └── jobs/
│
├── dbt/
│   ├── models/
│   │   ├── staging/
│   │   ├── intermediate/
│   │   └── marts/
│   ├── tests/
│   ├── macros/
│   └── dbt_project.yml
│
├── data/
│   └── .gitkeep
│
├── notebooks/
│   ├── exploration/
│   └── validation/
│
├── tests/
│   ├── unit/
│   └── integration/
│
└── docs/
    ├── architecture/
    ├── data_dictionary/
    └── decisions/
```

Do not commit large raw datasets to Git.

The actual repository structure may evolve as project objectives grow.

---

## 9. Development Process

For each new objective, follow this sequence:

### 1. Define the objective

State clearly what should work at the end.

Example:

> “Read one real CNMV XML and produce a structured dataset containing fund identifier, period, NAV and assets.”

### 2. Understand the concepts

Before implementation, explain the concepts necessary to solve the objective.

The AI should explain:

* relevant technology;
* terminology;
* architecture;
* trade-offs.

### 3. Implement the minimum

The developer writes the implementation.

The AI should avoid generating an entire solution unless explicitly requested.

### 4. Run and observe

Execute the implementation.

Inspect:

* output;
* logs;
* errors;
* data quality.

### 5. Review

Review the implementation together.

Discuss:

* correctness;
* simplicity;
* limitations;
* maintainability;
* scalability.

### 6. Refactor when justified

If the next objective exposes limitations, refactor the existing implementation.

Do not regard refactoring as failure.

### 7. Validate

Add appropriate tests and checks.

### 8. Document

Record important architectural or business decisions.

### 9. Move to the next objective

Increase scope gradually.

---

## 10. Agent Behavior During Learning

### The AI should

* Explain concepts clearly.
* Ask the developer to reason about architectural decisions.
* Provide hints before complete solutions.
* Review developer-written code.
* Diagnose errors.
* Explain why an implementation works or fails.
* Suggest refactors when justified.
* Explain trade-offs.
* Help design schemas and interfaces.
* Help write documentation.
* Point out hidden assumptions.

### The AI should not

* Automatically implement the entire project.
* Generate large amounts of code without necessity.
* Hide complexity behind unexplained abstractions.
* Introduce infrastructure without a clear reason.
* Preserve bad code merely because it already exists.
* Assume that the first architecture must be the final architecture.

### When the developer is stuck

Use this progression:

```text
Explanation
    ↓
Conceptual hint
    ↓
Specific hint
    ↓
Small example
    ↓
Partial solution
    ↓
Full solution only when necessary
```

The objective is to maximize understanding.

---

## 11. Data Quality Principles

Data quality is a first-class feature of the project.

At minimum, validate:

### Technical

* file exists;
* file is readable;
* schema is valid;
* expected columns exist;
* no unexpected schema breaking changes.

### Integrity

* unique business keys;
* no orphan records;
* valid dates;
* valid numeric ranges.

### Financial

Examples:

```text
NAV > 0

portfolio_weight >= 0

portfolio_weight <= 1

HHI between 0 and 1

fund_id + period is unique
```

Where mathematically appropriate:

```text
sum(portfolio_weights) ≈ 1
```

Do not silently discard failed records.

Failed records must be logged or quarantined.

---

## 12. Engineering Principles

### Idempotency

All ingestion and transformation processes should be safe to rerun.

### Reproducibility

A historical result should be reproducible from:

* source version;
* processing version;
* transformation logic.

### Observability

Pipeline execution should expose:

* records ingested;
* records rejected;
* processing duration;
* freshness;
* quality test results.

### Lineage

A Gold metric should be traceable to:

```text
Gold
 ↓
dbt model
 ↓
Silver
 ↓
Bronze
 ↓
CNMV source file
```

### Incremental Processing

Prefer incremental ingestion and transformation where appropriate.

Avoid rebuilding the entire history when only a new reporting period is available.

---

## 13. Financial Analytics Principles

Financial metrics should be:

* explicitly defined;
* reproducible;
* documented;
* validated against source information where possible;
* distinguished from official regulatory calculations.

Do not present an internally constructed analytical metric as an official CNMV metric.

Where a metric is an approximation or analytical proxy, document the assumption.

---

## 14. Agent Working Rules

When modifying the project:

1. Read `AGENTS.md` before making changes.
2. Understand the current objective before proposing implementation.
3. Reuse existing conventions where they remain appropriate.
4. Do not preserve architecture simply because it already exists.
5. Prefer the smallest implementation that solves the current objective.
6. Explain architectural changes before implementing them.
7. Do not introduce a technology without a clear reason.
8. Keep business logic out of Airflow DAG definitions where possible.
9. Use PySpark for distributed data processing when justified.
10. Use dbt for Silver/Gold SQL transformations.
11. Add or update tests when changing data logic.
12. Never silently change the meaning of an existing metric.
13. Preserve source provenance.
14. Prefer simple, explainable financial metrics before complex ML.
15. Document non-obvious financial assumptions.
16. Never fabricate missing regulatory data.
17. When a larger objective reveals weaknesses in earlier code, propose refactoring rather than working around the weakness.

---

## 15. Definition of Done

A feature is considered complete when:

* The current objective is clearly defined.
* The data source is documented.
* The implementation is understandable by the developer.
* The relevant pipeline component works.
* Relevant tests exist.
* Data lineage is documented where applicable.
* The transformation is reproducible.
* README/documentation explains how to run it.
* Important architectural decisions are documented.

A feature does **not** need to use the final production architecture if the current learning objective does not require it.

---

## 16. MVP

The final MVP should support:

```text
CNMV source
    ↓
Airflow ingestion
    ↓
Bronze
    ↓
PySpark parsing
    ↓
Silver
    ↓
dbt
    ↓
Gold
    ↓
Fund dashboard
```

The initial dashboard should allow:

1. Search a fund.
2. View historical NAV/performance.
3. View portfolio composition.
4. View concentration metrics.
5. View anomaly signals.
6. Compare the fund with peers.
7. Drill down to source data.

Do not optimize for maximum feature count.

Optimize for a complete end-to-end pipeline and strong understanding of each component.

---

## 17. Primary Success Metric

The project should demonstrate that a raw regulatory dataset can be transformed into a **reliable financial data product**.

The final narrative should be:

```text
Official CNMV data
        ↓
Reliable ingestion
        ↓
Distributed processing
        ↓
Data quality + lineage
        ↓
Financial analytics
        ↓
Actionable user interface
```

The project is successful when the developer can independently explain:

* why each technology is being used;
* how data moves through the platform;
* how the data model works;
* how data quality is enforced;
* how financial metrics are calculated;
* why architectural decisions changed over time;
* and what trade-offs were made.

The goal is **not to avoid rewriting code**.

The goal is to become capable of building increasingly sophisticated systems while understanding why the architecture evolves.


---

## Project-Specific Documentation

### Data Sources
-  — Detailed description of all datasets

### Architecture & Tools
-  — Toolchain decisions and pipeline architecture

### Business Questions
-  — Business questions and metrics

### Current Objective
- Objective B: Panoramica + Seleccion de fondos para analisis de compra/venta
- Sources: FONDMENS (masivo), FONDREGISTRO (masivo), IPP per-fund
- Universe: ~20 fondos seleccionados por rendimiento/volumen
