# Financial Metrics

Last updated: 2026-11-15

This document defines every metric the platform computes, how each one is calculated and what it assumes. It follows the order in which an analyst would read a fund: return, risk, risk-adjusted return and peer ranking, then portfolio, flows and fees, and finally data quality and anomalies. The last sections cover how the metrics were validated, conventions for anyone querying the data, and references.

All metrics are this project's own calculations, not official CNMV figures.

## Basis of calculation

Performance and risk metrics use a weekly return series: the last weekday NAV of each ISO week, non-overlapping weekly returns and an annualization factor of 52. This follows the ESMA methodology for the SRRI risk indicator.

There are two horizons, both ending at the cut-off date of the run:

- **3 years (36 months)**, used for the peer ranking and the watchlist.
- **5 years (60 months)**, reported as context. It includes the 2022 rate shock and does not change the selection.

Both horizons use the same formulas and the same quality screen; only the start of the window changes. A class without enough clean history for a horizon gets the status `short_history` for that horizon, and the panorama leaves its values empty instead of showing a shorter period as if it were complete.

The metrics are computed per share class, since each class has its own NAV, and funds are selected per compartment.

## Return

| Metric | Formula | Notes |
|--------|---------|-------|
| Weekly return | `ret_w = NAV_w / NAV_{w-1} - 1` | Only when the previous week has a price; otherwise the week counts as a gap |
| 1-year return | NAV now vs NAV 52 weeks earlier | `ret_1y` |
| CAGR | `(NAV_end / NAV_start)^(365 / days) - 1` | `cagr_3y` and `cagr_5y` |

## Risk

| Metric | Formula | Notes |
|--------|---------|-------|
| Volatility | `stddev_samp(ret_w) * sqrt(52)` | Annualized; `vol_3y`, `vol_5y` |
| Maximum drawdown | `max(1 - NAV / running_max(NAV))` | On the daily weekday series, because a weekly series would miss intra-week lows; `max_drawdown_3y`, `max_drawdown_5y` |
| SRRI-like class | Volatility bands below | Labelled "SRRI-like (3-year, weekly)". The official SRRI uses 5 years and further rules |

Since the 5-year window contains the 3-year one, the 5-year drawdown can never be lower; a dbt test checks it for every class.

| SRRI-like class | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|-------|---|---|---|---|---|---|---|
| Annualized volatility | < 0.5% | 0.5–2% | 2–5% | 5–10% | 10–15% | 15–25% | ≥ 25% |

## Risk-free rate

The minimum acceptable return for the Sortino ratio is the weekly change of the ECB's compounded €STR index: `mar_w = I_w / I_{w-1} - 1`, where `I_w` is the last index value on or before each week end. It moves week by week with the actual short-term rate, and using the index ratio avoids choosing a day-count convention.

A constant rate would not work here: since 2020 €STR has gone from below zero to about 4% and back toward 2%.

## Sortino ratio

| Metric | Formula |
|--------|---------|
| Mean excess return | `avg(ret_w - mar_w) * 52` |
| Downside deviation | `sqrt(avg(min(ret_w - mar_w, 0)^2)) * sqrt(52)` |
| Sortino ratio | `mean_excess / downside_dev` |

Two cases are excluded from the ranking, with the reason recorded in `sortino_status`:

- `no_downside`: the fund never had a week below the risk-free rate (or almost never, below `min_downside_dev`) and has a positive excess return. A flat price cannot cause this, because a flat week is already below a positive rate. It points to smoothed valuations or interest accrual, and giving it the top rank would not be defensible.
- `stagnant`: zero volatility and no excess return.

The Sortino ranking screens past performance. Persistence at the top of fund rankings is weak (see the S&P scorecard in References), so it does not predict future results.

## Peer ranking

Peers are the compartments with the same CNMV investor vocation (`VocacionInversora`). The ranking follows Morningstar's method and needs at least 5 peers:

1. Sort the peers by Sortino, best first; ties share their rank `c`.
2. `pct_exact = 100 * (c - 1) / (n - 1)` and `percentile_in_vocation = ceil(pct_exact)`, with 0 shown as 1.
3. Quartile 1 up to 25, 2 up to 50, 3 up to 75, otherwise 4.

Percentiles are computed among the investable compartments only, so they are not comparable with Morningstar's published ones.

CNMV vocations are broad: *Renta Fija Euro*, for example, mixes durations from about 2 to more than 10 years. Ranking within vocation and risk class would make peers more alike at the cost of smaller groups; it is left as a possible improvement.

## Portfolio concentration

Weights are computed over the reported positions. Lines of the same instrument are added together (by ISIN, or by asset type and description when there is no ISIN), and `w_i = position_value_i / sum(position_value)` over positions with a positive value. Non-positive positions are counted in `n_nonpositive`.

| Metric | Formula | Notes |
|--------|---------|-------|
| HHI | `sum(w_i^2)` | Herfindahl-Hirschman index, between 1/n and 1 |
| Effective number of positions | `1 / HHI` | |
| Top-10 weight | Sum of the 10 largest weights | |
| Coverage ratio | `sum(position_value) / compartment AUM` | Flagged outside 0.80–1.20 |

Reported positions may leave out cash or derivatives, which would overstate concentration. In practice the difference is small: the median coverage ratio is 0.96 (FONDCART 202512).

## Flows and the AUM bridge

The bridge splits each daily change in assets into what comes from prices and what comes from investors, per class, and then adds it up by month.

| Metric | Formula | Notes |
|--------|---------|-------|
| Derived units | `units_t = aum_t / nav_t` | Implied by AUM and NAV; not a CNMV figure |
| Market effect | `units_{t-1} * (nav_t - nav_{t-1})` | Change explained by the price |
| Net flows | `(units_t - units_{t-1}) * nav_t` | Change explained by subscriptions and redemptions |
| Change in AUM | `aum_t - aum_{t-1}` | Equals market effect plus net flows; tested |
| Market growth | `market_effect / average_aum` | |
| Net flow yield | `net_flows / average_aum` | |
| Outflow share | `min(net_flows, 0) / average_aum` | |
| Participant retention | `holders_t / holders_{t-1}` | A proxy: an investor in two classes counts twice |
| AUM retention | `aum_t / aum_{t-1}` | Includes the market effect |

Days with mergers, capital changes or jumps (`is_capital_change`, `is_jump`) are reported apart in `corporate_action_delta_aum` and kept out of the monthly flows, so the bridge still balances.

Limitations:

- The CNMV only publishes net subscriptions and redemptions, so gross churn cannot be measured.
- Month-end compartment AUM adds the last reported AUM of each class. A class that does not report on that day is missing from the sum, which affects about 0.2% of compartment-months.
- FONDPATRIMDISVAR reports flows as a cumulative year-to-date percentage, so the comparison with the daily bridge is done on the year-to-date total at each closing.

## Fees and income

FONDPATRIMDISVAR reports expenses and income as percentages of average daily assets, cumulative since the previous year-end. A June figure therefore covers six months and a December figure twelve. The Gold tables keep that year-to-date meaning and add annualized versions (`*_annualized_rate`) for comparing closings. Expenses come with a negative sign in the source.

| Metric | Formula | Notes |
|--------|---------|-------|
| Gross expenses | `GR = CGES + CDEP + GSE + OGGC + OGR` | Management, depositary, external services, other management and other charged expenses |
| Income | `ING = CDFAV + CRETRO + OING` | Discount commissions, retroceded commissions, other income |
| Net return | `RN = RG + GR + ING` | Source identity, with expenses negative; tested |
| Core fee yield | `abs(CGES + CDEP)` | Management and depositary fees |
| Other expense yield | `abs(GSE + OGGC + OGR)` | |
| Expense ratio | `abs(GR)` | |
| Income yield | `abs(ING)` | |
| Core fee share | Core fee yield / expense ratio | Share of costs that is management and custody |
| Fee revenue estimate | `average_assets * (management fee + depositary fee)` | `fee_revenue_proxy`: the fund's total fee pool |
| Manager revenue estimate | `average_assets * management fee` | `management_fee_revenue`: before payments to distributors and without costs |
| Management fee yield by group | Annualized management revenue / average assets | Weighted by assets |
| Fee concentration | `sum(share_i^2)` of management revenue by manager group | `hhi_fee`, plus `top5_fee_share` |

Using the management fee alone for concentration lowers the fee pool by about 7–8% and leaves the HHI almost unchanged (0.0942 vs 0.0941 in December 2025).

These revenue figures are estimates for mapping the market and ranking managers, and are not accounting revenue. There is no separate success fee in the source, and FONDTRIM's management fee rate cannot be used as a cross-check (see Validation).

## Data quality

| Measure | Definition | Where |
|--------|---------|-------|
| Reconciliation error | `abs(aum_fondmens - aum_fondtrim) / aum_fondmens`, same class and date | Above `max_recon_error` it becomes a `recon_error` anomaly |
| Coverage ratio | Weeks with a valid NAV / expected weeks | Per class and horizon |
| Gap share | Weeks with a gap / weeks with a NAV | Per class |
| Stale share | Zero-return weeks / weeks with a return | Per class |
| Class status | `eligible`, `quarantined` with a reason, or `short_history` | Per class and horizon, in `mart_fund_class_status` |

Every threshold is a dbt variable in `dbt_project.yml` with a comment on where its value comes from. Flags such as `is_flow_outlier`, `is_fee_outlier` and `meets_size_floor` mark rows without removing them.

## Anomalies

`fact_fund_anomalies` has one row per flag: compartment, class (empty for compartment-level flags), date and type.

| Field | Content |
|-------|---------|
| `anomaly_type` | `nav_extreme_return`, `nav_gap`, `nav_stale`, `dormant`, `coverage_lt_min`, `stale_end`, `short_history`, `recon_error`, `fee_outlier`, `fee_period_missing`, `flow_extreme_outflow` |
| `severity` | `info`, `warn` or `high` |
| `metric_value`, `threshold` | Observed value and the rule it broke |
| `source`, `description` | Where the data came from, and a readable explanation |

An anomaly is an analytical signal for manual review and does not imply any regulatory finding. A `high` flag never removes a fund on its own.

## Validation

Two scripts in `tests/integration/` recompute the metrics from Silver with pandas, sharing no code with the dbt SQL, and compare them with the dbt output and with official CNMV figures. They need the full data, so they are run by hand after `dbt build`:

```bash
python tests/integration/validate_class_metrics.py . data/gold/cnmv.duckdb
python tests/integration/validate_against_official.py . data/gold/cnmv.duckdb
```

| Check | Result (cut-off 202608) |
|---|---|
| All 3-year class metrics recomputed for 3,751 classes | Identical, maximum relative error 3·10⁻¹⁵ |
| Peer percentile recomputed from the Sortino ranking | Identical for 1,112 compartments |
| Official quarterly return (FONDTRIM) vs return from the daily NAV: 21,767 quarters of 1,463 classes, 2020–2026 | Median difference 0.003 pp; 97.3% within 0.05 pp; 0.9% above 2 pp, from distribution classes and corporate actions |
| Official quarterly volatility vs daily-return deviation | Official = daily deviation × √260 (median ratio 1.002). Not directly comparable with the project's weekly volatility |
| Realised management fee (FONDPATRIMDISVAR, December 2025) vs FONDTRIM `ComisionGestion` | Median ratio 1.98: the FONDTRIM field behaves like a half-year rate, so no metric uses it |
| Net flows vs the official year-to-date flow | 98.5% of compartments within 5 pp (dbt test `assert_flow_ytd_matches_official`) |

This process found and fixed two defects:

- **The downside deviation was understated.** In DuckDB `least(NULL, 0)` returns 0, so weeks without a return counted as weeks without losses. That inflated every eligible Sortino by about 0.32% without changing the ranking. A regression test now recomputes it with an explicit sum and count.
- **A "distribution" flag fired on market crashes.** It marked days when NAV and AUM fell in the same proportion with unchanged participants, which also happens on any sharp market drop: 72% of the events fell on 10 dates. It fed no metric and was removed.

## Known limitations

- **Distribution classes.** Most classes accumulate income, so their NAV already includes it and NAV returns are total returns. Distribution classes are the exception: their NAV drops at each payout. In FONDTRIM 202512, 81 of 3,069 classes (2.6%) reported a dividend, with a median of 1.3% of NAV. Their returns are not adjusted and are slightly understated.
- **Noise.** A 3-year weekly series has about 156 observations, so small differences between close peers should not be over-read.
- **Survivorship.** Funds that were merged or liquidated before the cut-off are not ranked.

## Metrics that need a benchmark

| Metric | Formula |
|--------|---------|
| Jensen's alpha | `fund_return - (risk_free + beta * (market_return - risk_free))` |
| Beta | `cov(fund, market) / var(market)` |
| Tracking error | `stddev(fund - benchmark)` |
| Active share | `sum(abs(weight_fund - weight_benchmark)) / 2` |

They are not computed until a benchmark is chosen (IBEX 35, MSCI World or a CNMV fund proxy). Possible additions that need no benchmark are the Sharpe and Calmar ratios.

## Conventions for querying the data

- Every rate, return, ratio and weight is a fraction: `0.0123` means 1.23%. Columns with rates end in `_rate`.
- FONDPATRIMDISVAR figures are year-to-date. Compare closings with the `*_annualized_rate` columns and never add them across periods.
- `fact_nav_daily.is_valid_nav` is false when NAV or AUM is not positive; leave those rows out of charts.
- `fact_holdings` keeps every FONDCART closing. The top ten positions are `position_rank <= 10`, and the asset allocation is the sum of `weight` by `clase_if` and `descripcion_if`.
- `mart_fund_panorama` has one row per active compartment, through its representative class; `mart_fund_class_status` explains why any class is missing from it.

## References

### Risk and performance methodology
- [ESMA/CESR 10-673: SRRI methodology](https://www.esma.europa.eu/sites/default/files/library/2015/11/10_673.pdf). Weekly returns, annualization and risk classes.
- [CESR 09-716: SRRI consultation draft](https://www.esma.europa.eu/sites/default/files/library/2015/11/09_716.pdf). 3-year window with weekly returns.
- [SRRI cut-off table (UCLouvain)](https://dial.uclouvain.be/pr/boreal/en/object/boreal%3A254713/datastream/PDF_01/view). The seven volatility bands.

### Peer comparison and rankings
- [Morningstar Rating for Funds](https://tw.morningstar.com/tw/news/119348/the-morningstar-rating-for-funds.aspx). 36 months of continuous history; comparison within category.
- [Morningstar: Absolute, Percentile and Fractional Ranks](https://morningstardirect.morningstar.com/clientcomm/DueDiligenceReports/Morningstar_Methodology_Ranking_Calculations.pdf). Percentile and quartile formula; no rating below 5 portfolios.
- [Morningstar: Performance Quartile within Category](https://awgmain.morningstar.com/webhelp/glossary_definitions/mutual_fund/mfglossary_performance_quartile.htm).
- [Morningstar: Oldest Share Class Methodology](https://morningstardirect.morningstar.com/clientcomm/Oldest_Share_Class_Methodology.pdf). Criteria for choosing a representative class.
- [S&P: Fleeting Alpha](https://www.spglobal.com/spdji/en/research/article/fleeting-alpha-the-challenge-of-consistent-outperformance). Largest class as representative.
- [S&P: Europe Persistence Scorecard, year-end 2025](https://www.spglobal.com/spdji/en/documents/spiva/persistence-scorecard-europe-year-end-2025.pdf). Survivorship and persistence.

### Concentration
- [State Street: Concentration is up, diversification isn't gone](https://www.ssga.com/us/en/intermediary/insights/concentration-is-up-diversification-isnt-gone). HHI, effective number and top-10 weight.
- [Nasdaq: All about index concentration](https://www.nasdaq.com/articles/all-about-index-concentration). HHI as the sum of squared weights.

### Risk-free rate
- [ECB: €STR overview](https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_short-term_rate/html/eurostr_overview.en.html).
- [ECB: series EST.B.EU000A2QQF08.CI](https://data.ecb.europa.eu/data/datasets/EST/EST.B.EU000A2QQF08.CI). The compounded index used here.
- [ECB: compounded €STR calculation rules](https://ecb.eu/paym/interest_rate_benchmarks/WG_euro_risk-free_rates/shared/pdf/ecb.Compounded_euro_short-term_rate_calculation_rules.en.pdf).

### Fees
- [Morningstar (Kinnel, 2016): How Fund Fees are the Best Predictor of Returns](https://morningstar.co.uk/uk/news/149421/how-fund-fees-are-the-best-predictor-of-returns.aspx).
- [Morningstar (Kinnel, 2010): How Expense Ratios and Star Ratings Predict Success](https://morningstar.co.uk/uk/news/66497/how-expense-ratios--star-ratings-predict-success.aspx).
- [CNMV: Las principales comisiones de los fondos de inversión](https://www.cnmv.es/portal/inversor/fondos-comisiones).
- [CNMV Circular 4/2008: expense ratio in periodic reports](https://vlex.es/vid/trimestral-semestral-posicion-43113951).

### Further reading
Sortino and Price (1994), *Performance Measurement in a Downside Risk Framework*. Sharpe (1994), *The Sharpe Ratio*. Lo (2002), *The Statistics of Sharpe Ratios*. Carhart (1997), *On Persistence in Mutual Fund Performance*. Bacon, *Practical Portfolio Performance Measurement and Attribution*.
