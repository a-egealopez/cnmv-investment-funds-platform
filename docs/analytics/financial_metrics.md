# Financial Metrics

Last updated: 2026-10-30

All metrics are computed on a **weekly return series** (last weekday NAV of each ISO week, non-overlapping returns, annualization factor 52), over a **36-month analysis window**, following the ESMA SRRI methodology adapted to a 3-year lookback. This replaces the earlier daily-return basis (√252).

**Implementation status**: the Silver layer (`fund_nav_daily`, `fund_metadata`, `fund_quarterly`, `fund_holdings`, `fund_period_financials`, `estr_daily`) is built. No metric below is computed yet — they are specified for the upcoming dbt layer (staging → intermediate → marts). Sections marked **planned** will be produced by dbt models; **Silver** means the input data already exists.

Data coverage caveat: Bronze/Silver start at 2023-01, so with `as_of_period = 202605` the 36-month window covers ≈ 35.3 months (coverage_ratio ≈ 0.98). Metrics are labeled "36-month" with `coverage_ratio` stored per class.

## Return

Status: **planned (dbt)** · input: `fund_nav_daily` (Silver)

| Metric | Formula | Description |
|--------|---------|-------------|
| **Weekly return** | `ret_w = VL_w / VL_{w-1} - 1` | Only if the previous week exists; otherwise the week is flagged `gap` (non-overlapping returns) |
| **ret_1y** | return over the last 52 weeks | When window coverage allows |
| **CAGR (3y)** | `(VL_end / VL_start)^(365 / days_elapsed) - 1` | Window-end vs window-start NAV |

## Risk

Status: **planned (dbt)** · input: weekly series

| Metric | Formula | Description |
|--------|---------|-------------|
| **Volatility** | `stddev_samp(ret_w) * sqrt(52)` | Sample weekly standard deviation, annualized |
| **Max Drawdown** | `max(1 - VL / cummax(VL))` | Worst peak-to-trough decline, computed on the **daily weekday VL series** already in Silver. No regulatory convention fixes the drawdown horizon (unlike the SRRI's weekly basis), so the daily series is used; a weekly series would understate intra-week troughs |
| **SRRI-like class** | 7 risk classes from annualized weekly volatility (cuts below) | Labeled "SRRI-like (3-year, weekly)" — never official SRRI, which uses 5 years |

SRRI-like cuts (annualized weekly volatility):

| Class | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|-------|---|---|---|---|---|---|---|
| Volatility | < 0.5% | 0.5–2% | 2–5% | 5–10% | 10–15% | 15–25% | ≥ 25% |

## Risk-adjusted (Sortino)

Status: **planned (dbt)** · input: weekly series + €STR index

Weekly minimum acceptable return (varies week by week, from the compounded €STR index — see Risk-free rate): `mar_w = I_w / I_{w-1} - 1`.

| Metric | Formula | Description |
|--------|---------|-------------|
| **mean_excess** | `avg(ret_w - mar_w) * 52` | Arithmetic mean excess return, annualized |
| **downside_dev** | `sqrt(avg(least(ret_w - mar_w, 0)^2)) * sqrt(52)` | Downside deviation against the same weekly MAR |
| **Sortino Ratio** | `mean_excess / downside_dev` | Past risk-adjusted performance filter for the watchlist |

**Reading**: the Sortino ranking is a screen on **past** risk-adjusted performance, not a predictor — persistence at the top is weak (see References). It complements, and is complemented by, the fee filter and the persistence check (future improvements).

Special cases (`sortino_status`):
- `no_downside`: `downside_dev = 0` and `mean_excess > 0` → **Sortino undefined; no percentile; excluded from the watchlist** (reason surfaced). A flat price does not produce this case — with MAR > 0 a flat week is a negative excess and adds downside — so `downside_dev = 0` with positive mean excess implies a NAV accruing above MAR every week: smoothed valuations or interest accrual. Rewarding it with the top rank is not defensible; near-zero downside is treated the same way via a minimum downside floor, calibrated with data in Phase 0.
- `stagnant`: `vol = 0` and `mean_excess <= 0` → excluded from the watchlist.

## Peer ranking

Status: **planned (dbt)** · peer group: CNMV investor vocation (`VocacionInversora`, FONDTRIM)

Morningstar-style percentile within vocation (1 = best), only with ≥ 5 peers:

1. Sort investable peers by Sortino (descending); tied ranks share their rank `c`.
2. `pct_exact = 100 * (c - 1) / (n - 1)`; `percentile_in_vocation = ceil(pct_exact)` (0 → 1).
3. `quartile_in_vocation`: 1 if ≤ 25, 2 if ≤ 50, 3 if ≤ 75, else 4.

Percentiles are computed among **investable compartments only** — not comparable to Morningstar published percentiles.

**Known limitation — coarse peer group**: CNMV vocations are broad (e.g. *Renta Fija Euro* mixes durations from ~2 to 10+ years), so peers are heterogeneous. Possible mitigation — percentile within `vocation × SRRI-like class` cells — trades homogeneity for smaller peer groups; kept as a future improvement.

## Concentration

Status: **planned (dbt)** · input: `fund_holdings` (Silver, per compartment) + compartment AUM

Weights are computed over **reported positions** (not over NAV): lines of the same instrument are aggregated (ISIN if present, else `clase_if + descripcion_if`); `w_i = position_value_i / sum(position_value)` over positions with `value > 0`; non-positive values are counted (`n_nonpositive`), never silently dropped.

| Metric | Formula | Description |
|--------|---------|-------------|
| **HHI** | `sum(w_i^2)` | Herfindahl-Hirschman Index, range [1/n, 1] |
| **Effective N** | `1 / HHI` | Number of equally-sized positions with the same concentration |
| **Top 10 Weight** | sum of the 10 largest position weights | Simple concentration measure |
| **Coverage Ratio** | `sum(position_value) / compartment_aum` | Completeness of reported holdings vs NAV; flagged outside [0.80, 1.20] |

**Weight base — to decide with Phase 0 data**: weights are computed over reported positions, which may exclude treasury or derivatives, so HHI can overstate true portfolio concentration. A common alternative (used in fund factsheets, source not verified in this session) is weighting over NAV. If `coverage_ratio` ≈ 1 in nearly all compartments, the two bases coincide and the choice is moot; measured median is 0.96 (FONDCART 202512).

## Risk-free rate

Status: **input in Silver (`estr_daily`)** · derivation **planned (dbt)**

Two levels:

- **Weekly MAR (core, feeds Sortino)**: `mar_w = I_w / I_{w-1} - 1`, where `I_w` is the last compounded €STR index observation on or before each week end (single as-of join against `estr_daily`). The MAR therefore varies week by week with the actual short rate, and no annualization convention (ACT/360 vs 365) is introduced — the index ratio is convention-free.
- **Window rate (reporting only)**: `rf_window = (I_end / I_start)^(365 / dc) - 1`, where `I_start` / `I_end` bracket the analysis window and `dc` is calendar days between them. Used to report the window risk-free level; not to build `mar_w`.

Context: over the current window €STR moved from ≈ 3% up to ≈ 4% (Sep 2023) and back down toward 2% — the earlier static 2.5% approximation is **superseded**.

## Flows and AUM bridge

Status: **planned (dbt)** · input: `fund_nav_daily` (Silver, daily) + `fund_period_financials` (Silver, cross-check)

The bridge is computed per class and day, then aggregated to month/quarter. `units_t` is a derived analytical unit, not an official CNMV figure.

| Metric | Formula | Description |
|--------|---------|-------------|
| **Derived units** | `units_t = aum_t / nav_t` | Analytical units implied by AUM and NAV |
| **Market effect** | `units_{t-1} * (nav_t - nav_{t-1})` | AUM change attributable to NAV |
| **Net flows** | `(units_t - units_{t-1}) * nav_t` | AUM change attributable to units |
| **Delta AUM** | `aum_t - aum_{t-1}` | Must equal `market_effect + net_flows` within tolerance |
| **Market growth** | `market_effect / aum_{t-1}` | Return-driven growth |
| **Organic growth** | `net_flows / aum_{t-1}` | Flow-driven growth |
| **Net flow yield** | `net_flows / aum_{t-1}` | Same as organic growth; monthly/period version |
| **Outflow share** | `min(net_flows, 0) / aum_{t-1}` | Intensity of net outflows |
| **Participant retention** | `holders_t / holders_{t-1}` | Proxy only; not gross retention |
| **AUM retention** | `aum_t / aum_{t-1}` | Includes market effect |

**Limitations:** only **net** subscriptions/redemptions exist; there is no gross churn. Distributions, mergers and class changes can break the bridge and are flagged (`aum_flow_mismatch`). `Suscripciones_Reembolsos_Netos` is cumulative from the previous year-end: accumulate daily `net_flows` from that close and compare with the YTD percentage at each quarter. Do not compare a single quarter with a YTD figure.

## Fees and income quality (FONDPATRIMDISVAR)

Status: **planned (dbt)** · input: `fund_period_financials` (Silver) + `fund_quarterly` (FONDTRIM, cross-check)

FONDPATRIMDISVAR is documented as quarterly but the downloaded archives only contain 06/12; it gives **percentages of average daily patrimony, cumulative since the previous year-end**. XML expenses are negative. Do not mix these accumulated percentages with annual rates from FONDTRIM. Field abbreviations: `CGES`=management fee, `CDEP`=depositary fee, `GSE`=external services, `OGGC`=other management expenses, `OGR`=other charged expenses, `CDFAV`=discount commissions, `CRETRO`=retroceded commissions, `OING`=other income.

| Metric | Formula | Description |
|--------|---------|-------------|
| **Gross expenses** | `GR = CGES + CDEP + GSE + OGGC + OGR` | XML sign; keep negative in Silver |
| **Income** | `ING = CDFAV + CRETRO + OING` | Discounts, retrocessions, other income |
| **Net return** | `RN = RG − GR + ING` (PDF); with XML signs, `GR` is negative, so `RN = RG + GR + ING` | Source identity |
| **Core fee yield** | `abs(CGES + CDEP)` | Management + depositary fees |
| **Other expense yield** | `abs(GSE + OGGC + OGR)` | Other recurring/non-recurring expenses |
| **Expense ratio** | `abs(GR)` | Total expenses over average patrimony |
| **Income yield** | `abs(ING)` | Income over average patrimony |
| **Core fee share** | `core_fee_yield / expense_ratio` | Share of expenses that is management/custody |
| **Fee revenue proxy** | `TotalPatrimonio * (ComisionGestion + ComisionDepositario) / 100` | Proxy using period-end patrimony and FONDPATRIMDISVAR percentages; not accounting revenue. FONDTRIM rates are a cross-check. |
| **HHI fee** | `sum((fee_revenue_i / total_fee_revenue)^2)` | Concentration of fee revenue by manager/group |
| **Top-5 fee share** | sum of 5 largest `fee_revenue` shares | Fee concentration |

**Limitations:** no separate success fee exists; `GastosRepercutidos` is the total and does not isolate it. There is no fee-base field: the source defines all variation fields over average daily patrimony. `TotalPatrimonio` is the quarter-end patrimony, not average daily patrimony; the fee-revenue proxy is for ranking, not accounting. `hhi_fee` needs a documented grouping choice (`Gestora` vs `GrupoGestora`).

## Data quality and reconciliation

Status: **planned (dbt)** · input: FONDMENS + FONDTRIM at common semiannual closes

| Metric | Formula | Description |
|--------|---------|-------------|
| **Reconciliation error** | `abs(aum_fondmens - aum_fondtrim) / aum_fondmens` | Same date/period; flag, do not auto-fail |
| **Coverage** | eligible classes / active classes | Share with usable metrics |
| **Gap share** | classes with `gap` / eligible classes | Missing-week incidence |
| **Stale share** | classes with `stale_nav` / eligible classes | Stale price incidence |
| **Fee period status** | `ok` / `missing` | Whether FONDPATRIMDISVAR has a row for that period (observed 06/12) |
| **DQ status** | rule-based `pass` / `warn` / `fail` | Aggregates thresholds and flags |

Thresholds live in dbt `vars` and are calibrated (`max_recon_error`, `max_outflow_yield`, `max_fee_yield`, `max_hhi_asset_type`).

## Anomalies

Status: **planned (dbt)** · input: NAV, fees, flows, concentration, coverage, reconciliation

`mart_fund_anomalies` is a typed union, one row per `fund_key × period × anomaly_type`:

| Field | Meaning |
|-------|---------|
| `anomaly_type` | e.g. `nav_extreme_return`, `nav_stale`, `nav_gap`, `fee_outlier`, `fee_period_missing`, `flow_extreme_outflow`, `aum_flow_mismatch`, `concentration_outlier`, `holdings_coverage_outlier`, `recon_error`, `missing_period` |
| `severity` | `info`, `warn`, `high` |
| `metric_value` | Observed value |
| `threshold` | Rule threshold |
| `source` | Silver table / source dataset |
| `description` | Human-readable explanation |

**Limitations:** anomaly signals are analytical, not regulatory findings. `high` requires manual review and never silently removes a fund.

## Blocked Metrics (require benchmark)

| Metric | Formula | Blocker |
|--------|---------|---------|
| **Jensen's Alpha** | `fund_return - (risk_free + beta * (market_return - risk_free))` | Benchmark selection (IBEX 35, MSCI World, or CNMV fund proxy) |
| **Beta** | `cov(fund_returns, market_returns) / var(market_returns)` | Benchmark selection |
| **Tracking Error** | `stddev(fund_returns - benchmark_returns)` | Benchmark selection |
| **Active Share** | `sum(abs(weight_fund - weight_benchmark)) / 2` | Benchmark portfolio |

## Future metrics (out of current scope)

| Metric | Requirement |
|--------|-------------|
| **Turnover Ratio (portfolio-derived)** | `sum(abs(w_t - w_{t-1})) / 2` — needs FONDDERI or multi-period FONDCART; FONDPATRIMDISVAR already provides `IndiceRotacionCarteraActual`, which should be preferred and documented as the source metric |
| **Sharpe Ratio** | Easy extension of the Sortino pipeline (36 months) |
| **Calmar Ratio** | `CAGR / max_drawdown` — planned as a future metric alongside Sharpe |
| **Official SRRI (5-year)** | Requires extending history to 5 years |

## Methodological Notes

- **Unit of measurement**: share class (own NAV); **selection unit**: compartment.
- All metrics are internal analysis, not official CNMV calculations.
- Every metric must document its assumptions and data source; formulas must not change silently.
- Weekly volatility on the 3-year window is noisy; ranking sensitivity (window ±6 months, weekly MAR vs window-constant MAR) must be recorded when the watchlist is built.
- Dividends: for **accumulation classes** (the overwhelming majority), the published VL already embeds reinvested returns, so VL-based returns are total returns. The issue only affects **distribution classes**, whose VL drops at each payout — measured on FONTRIM 202512 `Beneficio_Dividendo_Bruto`: 81 of 3,069 classes (2.6%) report a gross dividend; among them the median dividend/VL is 1.3% (p90 2.4%, max 4.5%), concentrated in international equity and mixed vocations — exactly where the price-return distortion would matter. Phase 0 check: identify classes showing periodic VL drops compatible with a payout; if few, flag and exclude them from the watchlist rather than adjusting returns.

## References

All formulas above back to these sources. Labels: **verified** = located and read; **to verify** = cited from memory, pending check.

### Risk-adjusted performance methodology
- [ESMA/CESR 10-673 — SRRI methodology](https://www.esma.europa.eu/sites/default/files/library/2015/11/10_673.pdf) (verified) — weekly non-overlapping returns, m=52 annualization, volatility formula, risk classes.
- [CESR 09-716 — SRRI consultation draft](https://www.esma.europa.eu/sites/default/files/library/2015/11/09_716.pdf) (verified) — 3-year window with weekly returns.
- [SRRI cut-off table (UCLouvain)](https://dial.uclouvain.be/pr/boreal/en/object/boreal%3A254713/datastream/PDF_01/view) (verified) — the 7 volatility cut-offs.

### Peer comparison & rankings
- [Morningstar Rating for Funds](https://tw.morningstar.com/tw/news/119348/the-morningstar-rating-for-funds.aspx) (verified) — 36-month continuous history requirement; comparison within category.
- [Morningstar — Absolute, Percentile and Fractional Ranks](https://morningstardirect.morningstar.com/clientcomm/DueDiligenceReports/Morningstar_Methodology_Ranking_Calculations.pdf) (verified) — percentile/quartile formula; no rating with < 5 distinct portfolios.
- [Morningstar — Performance Quartile (within Category)](https://awgmain.morningstar.com/webhelp/glossary_definitions/mutual_fund/mfglossary_performance_quartile.htm) (verified).
- [Morningstar — Oldest Share Class Methodology](https://morningstardirect.morningstar.com/clientcomm/Oldest_Share_Class_Methodology.pdf) (verified) — ordered criteria for representative-class selection.
- [S&P — Fleeting Alpha: the challenge of consistent outperformance](https://www.spglobal.com/spdji/en/research/article/fleeting-alpha-the-challenge-of-consistent-outperformance) (verified) — largest-asset class as representative.
- [S&P — Europe Persistence Scorecard Year-End 2025](https://www.spglobal.com/spdji/en/documents/spiva/persistence-scorecard-europe-year-end-2025.pdf) (verified) — survivorship and persistence caveats.

### Concentration
- [State Street — Concentration is up, diversification isn't gone](https://www.ssga.com/us/en/intermediary/insights/concentration-is-up-diversification-isnt-gone) (verified) — HHI, effective number = 1/HHI, top-10 weight.
- [Nasdaq — All about index concentration](https://www.nasdaq.com/articles/all-about-index-concentration) (verified) — HHI as sum of squared weights.

### Risk-free rate (€STR)
- [ECB — €STR overview (compounded index)](https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_short-term_rate/html/eurostr_overview.en.html) (verified).
- [ECB — Series `EST.B.EU000A2QQF08.CI`](https://data.ecb.europa.eu/data/datasets/EST/EST.B.EU000A2QQF08.CI) (verified) — compounded €STR index used as input.
- [ECB — Compounded €STR calculation rules](https://ecb.eu/paym/interest_rate_benchmarks/WG_euro_risk-free_rates/shared/pdf/ecb.Compounded_euro_short-term_rate_calculation_rules.en.pdf) (verified).

### Fees and revenue quality
- [Morningstar (Kinnel, 2016) — How Fund Fees are the Best Predictor of Returns](https://morningstar.co.uk/uk/news/149421/how-fund-fees-are-the-best-predictor-of-returns.aspx) (verified).
- [Morningstar (Kinnel, 2010) — How Expense Ratios & Star Ratings Predict Success](https://morningstar.co.uk/uk/news/66497/how-expense-ratios--star-ratings-predict-success.aspx) (verified).
- [CNMV — Las principales comisiones de los fondos de inversión](https://www.cnmv.es/portal/inversor/fondos-comisiones) (verified).
- [CNMV Circular 4/2008 — expense ratio in periodic reports](https://vlex.es/vid/trimestral-semestral-posicion-43113951) (verified, divulgative).

### From memory, to verify
Sortino, F. and Price, L. (1994), *Performance Measurement in a Downside Risk Framework* · Sharpe, W. (1994), *The Sharpe Ratio* · Lo, A. (2002), *The Statistics of Sharpe Ratios* · Young (1991) on Calmar · Carhart, M. (1997), *On Persistence in Mutual Fund Performance* · Herfindahl (1950) / Hirschman (1945), origin of HHI · Bacon, C., *Practical Portfolio Performance Measurement and Attribution*.
