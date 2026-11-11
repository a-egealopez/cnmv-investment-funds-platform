# Parsing Decisions

Decisions behind `spark/parsing/fondmens.py`, `fondregistro.py`, `fondtrim.py`,
`fondcart.py` and `fondpatrimdisvar.py`. Each entry: the problem found in the CNMV source, what was
decided, and why.

## INPUT_SCHEMA declares ArrayType explicitly

**Problem.** The CNMV XML nests `Entidad → Compartimento → Clase`. Spark's XML
reader collapses a single-element array to a plain struct, so a fund with one
compartment or one class silently breaks `explode`.

**Decision.** Both parsers declare `ArrayType(StructType(...))` in `INPUT_SCHEMA`
even when the real data usually has many elements.

**Why.** Structural guarantee over data-dependent luck; explode works for 1 or N.

## Unpivot the 31 daily columns with `stack`

**Problem.** FONDMENS publishes `VL_Dia1..31`, `Participes_Dia1..31`,
`Patrimonio_Dia1..31` — 93 columns per class instead of one row per day.

**Decision.** One `stack(31, ...)` expression unpivots to
`(day, VL, Participes, Patrimonio)` rows. Day 29-31 of short months are dropped.

**Why.** `fund_nav_daily` is a time series keyed by `value_date`; wide-to-long
belongs here because the shape is imposed by the source, not by analysis.

## `try_to_date` instead of `to_date` for daily rows

**Problem.** CNMV zero-fills impossible days (`VL_Dia31` in April). A strict
`to_date` raises on "20260431"; the padding must not kill the period.

**Decision.** `try_to_date(...)` maps impossible dates to NULL; rows where
`value_date IS NULL` are filtered right after.

**Why.** Padding is a source convention, not a data error; the parser absorbs it.

## Casts live in the parser, not in dbt

**Problem.** Everything arrives as strings from the XML reader.

**Decision.** Casts to `LongType`, `DecimalType(18,4)` (VL), `DecimalType(18,2)`
(Patrimonio) and `DateType` (`value_date`) happen inside the parser, before
`write_silver`. `EXPECTED_SCHEMA` is asserted after the cast.

**Why.** Silver is the typed contract every consumer (validate_silver, dbt, notebooks)
reads. dbt should never cast — if a column has the wrong type, Silver is broken.

## `ETF == "YES"` → boolean

**Problem.** FONDREGISTRO encodes the ETF flag as the string `"YES"` (or absent).

**Decision.** `(col("ETF") == "YES").alias("ETF")` in the final select.

**Why.** A string flag is a source artifact; Silver carries a real boolean.

## Parsers named by source file, jobs by layer

**Problem.** `parse_fondmens` produced `fund_nav_daily`; the name said nothing
about the output and duplicated the folder's job.

**Decision.** `spark/parsing/fondmens.py` (source-named); `spark/jobs/build_silver.py`
and `validate_silver.py` (layer-named entrypoints).

**Why.** One module per CNMV source file; the Silver entity is the data-layer
contract, the source file is the parser's identity. See AGENTS.md §8.

## No `spark/normalization/`

**Problem.** AGENTS.md originally proposed a normalization folder between
parsing and jobs.

**Decision.** Not created. Structural normalization (unpivot, casts, dates)
stays inside the parsers; semantic normalization (flags, quarantine, derived
metrics) is deferred to dbt on top of typed Silver tables.

**Why.** An empty folder is premature abstraction. The split that matters is
XML-structural (Spark) vs analytical-semantic (dbt), not parse vs normalize
inside Spark. Create `spark/normalization/` only if a real cross-source need
appears (e.g. entity resolution between nav and metadata keys).

## fund_quarterly: entity/compartment fields repeated per class

**Problem.** FONDTRIM's hierarchy packs fields at three levels: `CodigoDivisaIIC`
(entity), `VocacionInversora` and `ClaseFondo` (compartment, the latter empty ≈ 54%
of rows) and the financial metrics per class. Exploding only `Clase` leaves the
upper levels reachable, but the natural Silver grain is one row per class-month.

**Decision.** `VocacionInversora`, `ClaseFondo` and `CodigoDivisaIIC` are repeated
on every class row; grain is `Tipo + NumeroRegistro + NumeroCompartimento +
NumeroClase + FechaDatos`.

**Why.** A class-month row carries everything a dbt model needs without joins
(that join would be needed anyway — dbt models group by compartment). Storage
costs nothing at 18k rows per closure.

## fund_quarterly: quarterly metric structs flattened, XSD names kept

**Problem.** The XSD nests `Rentabilidad`, `Volatilidad_VL` and
`RatioTotalGastos`, each with `TrimestreActual/T_1/T_2/T_3`.

**Decision.** Flattened to top-level columns (`Rentabilidad_TrimestreActual`,
`Volatilidad_TrimestreActual`, `RatioTotalGastos_T_1`, …), Decimal(18,2); the
`Volatilidad_VL` prefix is shortened to `Volatilidad` (flat names rewrite
`Volatilidad_VL_Volatilidad_T_1` as `Volatilidad_T_1`); optional fields cast to
NULL when absent.

**Why.** dbt and notebooks read flat columns; renaming loses no information
because the columns are already univocal without the `_VL` suffix.

## fund_holdings: raw line grain, no aggregation in Silver

**Problem.** FONDCART repeats the same instrument inside one compartment
(2.879 same-instrument line groups in the six 2023-2025 closures) and some
compartimentos have no `InversionesFinancieras` at all.

**Decision.** One row per raw position line. Compartimentos with no holdings
produce no rows (their absence is a documented join finding). No position key is
asserted unique; a repeated line is not treated as a data error.

**Why.** The aggregation (per instrument, weight share) follows a portfolio
definition the source does not constrain (the per-instrument aggregation is
defined in the dbt plan); doing it in Silver
would freeze that choice into the storage layer.

## Gate cadence contract: FONDTRIM/FONDCART semiannual, FONDPATRIMDISVAR nominal quarterly

**Problem.** The project plan (v0.3) assumed quarterly closures for
FONDTRIM/FONDCART; the Bronze zips disprove that (202403 and 202303 zips don't
contain either dataset). The FONDPATRIMDISVAR explanatory document says it is
quarterly (03/06/09/12), but every downloaded CNMV archive from 2023 to 2025
(six closures) contains FONDPATRIMDISVAR only in June and December. The XSD
header for FONDTRIM says "Datos mensuales" but the published cadence is
half-yearly.

**Decision.** `validate_silver` gates `trim_period_months` to 06/12 for
FONDTRIM/FONDCART and accepts 03/06/09/12 for FONDPATRIMDISVAR; `build_silver`
parses each only when the file exists. Observed FONDPATRIMDISVAR coverage is
therefore 06/12, and the analysis layer treats it as semiannual until a real
03/09 file appears. The download expansion (PLAN §5.2) follows those cadences.

**Why.** The permissive FONDPATRIMDISVAR gate matches the explanatory PDF and
will not reject a future quarterly file; the observed data still prevents the
dbt layer from assuming quarters that do not exist. The existence checks make
`build_silver` idempotent across all 41 monthly periods.

## estr_daily: ECB CSV read by header, try_cast and full overwrite

**Problem.** The ECB risk-free series (dataset EST) is a daily CSV, not XML,
close to 1.8k rows per series, and the Spark readers so far used an explicit
INPUT_SCHEMA per CNMV XSD.

**Decision.** Read the two raw CSVs (`data/raw/ecb/estr_ci.csv`,
`estr_cr.csv`) with `header=True` and no explicit input schema (the CSV is
self-describing; the contract is the output `EXPECTED_SCHEMA`). `TIME_PERIOD`
and `OBS_VALUE` go through `try_cast` (malformed input becomes NULL, as with
FONDCART positions). Output is a long table,
`estr_daily(series, value_date, obs_value, obs_status)`, unique
`(value_date, series)`, no partitions: the table is small, so a full overwrite
is the idempotent reload. `build_silver` runs it once per run (files may be
absent until the first download).

**Why.** Full-history reload keeps the source, the file hash
(`data/raw/ecb/manifest.csv`, same manifest pattern as the CNMV zips) and the
Silver table in a simple 1:1; incremental by date would buy nothing at this
size. Keeping both series in one table exposes the key `series`
(`*.CI` index, `*.CR` rate) instead of two parallel tables.

## fund_period_financials: compartment grain, source percentages preserved

**Problem.** FONDPATRIMDISVAR reports expenses, income, net flow, net return,
turnover and patrimony at compartment level, with variation fields expressed as
percentages of average daily patrimony accumulated since the previous year-end.
The XML uses negative signs for expenses; the distribution fields and the two
patrimony fields are monetary amounts, not percentages.

**Decision.** `spark/parsing/fondpatrimdisvar.py` produces one row per
`Tipo + NumeroRegistro + NumeroCompartimento + FechaDatos`. Percentage fields
are stored as published (not divided by 100, not annualized, not sign-flipped);
the two patrimony fields keep their currency amounts. The parser records only
the period in the partition (`FechaDatos`); source hash and schema version
remain in Bronze and are not yet propagated into Silver. It does not create a
separate success-fee column because the source has none.

**Why.** Silver is a typed source contract. Converting percentages to fractions
or annualizing them would silently change the meaning before dbt can document
it. Keeping XML signs lets the dbt identity `GR = CGES + CDEP + GSE + OGGC + OGR`
be tested directly.

## fund_period_financials: nominal quarterly, observed semiannual, FI only

**Problem.** The FONDPATRIMDISVAR PDF describes quarterly publication and only
for FI. The downloaded 2023-2025 archives contain the file only at 06/12. It
contains net subscriptions/redemptions, not gross entries and exits; the
turnover index refers to a quarter in 03/09 and to a half-year in 06/12.

**Decision.** The parser and gates accept 03/06/09/12 and the FI universe; missing
files produce no rows. The current Silver coverage is 06/12. The parser keeps
`IndiceRotacionCarteraActual` and its source period semantics unchanged. The dbt
layer labels churn and retention as proxies and never presents them as gross
churn.

**Why.** The permissive gate follows the official PDF without inventing 03/09
rows; the semiannual analysis cadence follows the actual published archives.
Using the wrong cadence would create empty periods or skip available data;
inventing gross flows would violate the "never fabricate missing regulatory
data" rule.

**Profiling evidence.**
`notebooks/exploration/03_fondpatrimdisvar__financial_contract_profiling.ipynb` verifies the
real 06/12 slice (10,237 rows, 1,970 compartments), nullability, signs, units and
the accounting identities used by the gates.
