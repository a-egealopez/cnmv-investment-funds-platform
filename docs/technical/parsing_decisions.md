# Parsing Decisions

Decisions behind `spark/parsing/fondmens.py` and `spark/parsing/fondregistro.py`.
Each entry: the problem found in the CNMV source, what was decided, and why.

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
