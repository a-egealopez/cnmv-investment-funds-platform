# Business Questions

Last updated: 2026-10-30

## Context

Analysis of Spanish IIC to produce a fund panorama and a defensible candidate watchlist for buy/sell study. The watchlist is a list of candidates to research, not a recommendation.

Data sources: CNMV (FONDMENS, FONDREGISTRO, FONDTRIM, FONDCART, FONDPATRIMDISVAR) and ECB (€STR).

Universe: 1,438 entities / 3,116 classes / 1,668 compartments (FONTRIM 202512); FONDCART covers 1,644 compartments with a portfolio. FI only. Metrics unit: share class; selection unit: compartment; peer group: CNMV investor vocation.

## Questions

### MVP — panorama and watchlist (current objective)

#### 1. Fund Panorama

**Question**: What is the state of every active share class — eligible, quarantined (and why), or too short to measure?

**Data needed**: FONDMENS, FONDREGISTRO, FONDTRIM

**Metrics**: 36-month window coverage, quality flags (`bad_nav`, `extreme_return`, `gap`, `stale_nav`, stale end), quarantine reason per class

**Output**: `mart_fund_panorama` — one row per active class, every absence explained

#### 2. Watchlist Selection

**Question**: Which ≤ 20 compartments show the best **past** risk-adjusted performance (Sortino-ranked) within their CNMV investor vocation, after strict quality screening?

**Data needed**: FONDMENS (NAV series), FONDREGISTRO (identification), FONDTRIM (vocation, currency, legal floors), FONDCART (portfolio, informational)

**Metrics**: weekly returns, 36-month volatility (SRRI-like class), Sortino (weekly €STR MAR), percentile/quartile within vocation (1 = best, ≥ 5 peers), 36m CAGR, 1y return, max drawdown

**Output**: `mart_fund_panorama` filtered by `watchlist_status = 'selected'` — ranked candidates with vocation, family, position and full provenance

### Portfolio (already supported by Silver; dbt marts pending)

#### 3. Concentration

**Question**: Which compartments are most concentrated in a single asset?

**Data needed**: FONDCART + FONDMENS (AUM coverage)

**Metrics**: HHI, effective N, top-10 weight, coverage ratio (weights over reported positions)

**Output**: `mart_fund_panorama` (concentration columns) + the top ten from `fact_holdings` (`position_rank <= 10`)

#### 4. Portfolio Composition

**Question**: What does compartment X hold, by reported asset category?

**Data needed**: FONDCART

**Metrics**: weights by `ClaseIF` as reported, top-10 positions

**Output**: asset-class breakdown chart (sum of `fact_holdings.weight` by `clase_if` / `descripcion_if`)

#### 5. Peer Comparison

**Question**: How does fund A compare to peers with the same investor vocation — performance and portfolio?

**Data needed**: FONDMENS, FONDTRIM (vocation), FONDCART

**Metrics**: percentile in vocation, portfolio metrics vs peer group

**Output**: side-by-side comparison against the vocation peer group

### Flows, revenue and quality (Release 1)

#### 6. AUM Growth and Flows

**Question**: Is a fund growing because of returns or because investors are putting money in?

**Data needed**: FONDMENS (daily AUM and NAV), FONDPATRIMDISVAR (YTD net flow cross-check)

**Metrics**: derived units, market effect, net flows, `delta_aum`, market growth, organic growth, net flow yield, outflow share, AUM/participant retention (proxy)

**Output**: `mart_fund_flow_revenue` and a flow/retention block in the executive summary

**Limitations**: only net flows exist; no gross subscriptions/redemptions, so churn is a proxy.

#### 7. Fee and Revenue Quality

**Question**: How much of a fund's expense burden is recurring management/custody, and how concentrated is fee revenue?

**Data needed**: FONDPATRIMDISVAR (management, depositary, other expenses, income), FONDTRIM (fee rate cross-check)

**Metrics**: `core_fee_yield_rate`, `other_expense_yield_rate`, `charged_expense_yield_rate`, `income_yield_rate`, `net_return_rate` (cumulative for the year) and their `*_annualized_rate` versions, `core_fee_share`, `fee_revenue_proxy` / `fee_revenue_proxy_annualized`, and by manager group `management_fee_revenue_annualized`, `management_fee_yield_annualized_rate`, `net_flow_yield` / `market_growth`, `hhi_fee`, `top5_fee_share`

**Output**: `fact_fund_period_financials` (fee block), `fact_manager_group_monthly` and `fact_market_fee_and_aum` (concentration)

**Limitations**: no success fee; `fee_revenue_proxy` is cumulative for the year (June covers half a year, December a full year; use the annualized columns to compare) and is not accounting revenue. Manager revenue uses the management fee only, gross of retrocessions to distributors and without costs, so it supports market mapping and screening, not valuation.

#### 8. Data Quality and Forensic Signals

**Question**: Which funds have data that does not reconcile, and which show unusual NAV, flow, fee, or concentration behaviour?

**Data needed**: FONDMENS, FONDTRIM, FONDPATRIMDISVAR, FONDCART

**Metrics**: `recon_error`, coverage, gap/stale shares, `fee_period_status`, `dq_status`, anomaly type and severity

**Output**: `mart_data_quality_scorecard`, `fact_fund_anomalies`, Power BI "Anomaly / Forensic Breakdown"

### Phase 2 (future)

#### 9. Asset Rotation

**Question**: What assets did funds buy or sell between semiannual closures?

**Data needed**: FONDCART (multiple periods)

**Metrics**: new holdings, abandoned holdings, weight changes

**Output**: rotation report

#### 10. Derivatives & Patrimony Variation

**Question**: Do funds use derivatives materially? What drives patrimony variation (flows vs returns)?

**Data needed**: FONDDERI (not yet ingested); FONDPATRIMDISVAR already covers flows and net return

**Output**: derivative usage signal; deeper flow/rotation analysis

## Notes

- All return, volatility, and risk calculations are internal analysis, not official CNMV metrics; the risk-class label is "SRRI-like (3-year, weekly)", never official SRRI.
- **Reading**: the watchlist is a filter on past risk-adjusted performance, not a prediction of future results — persistence at the top is weak (S&P persistence scorecard evidence). It is complemented by the fee/flow layer and a persistence contrast.
- Buy/sell conclusions are analytical signals, not financial advice.
- Every metric must be traceable to its original CNMV source.
- Each calculation must document its assumptions and limitations (survivorship bias — FONDREGISTRO only contains live funds; weekly volatility noise on ~156 weeks; portfolio data up to 2 months stale vs `as_of_period`).

## Implementation Priority

| Priority | Question | Phase | Depends on |
|----------|----------|-------|------------|
| High | 1. Panorama | MVP (dbt Fase 2) | FONDMENS, FONDREGISTRO, FONDTRIM |
| High | 2. Watchlist | MVP (dbt Fase 4) | FONDMENS, FONDTRIM, €STR |
| High | 3. Concentration | MVP (dbt Fase 5) | FONDCART, FONDMENS |
| Medium | 4. Composition | MVP (dbt Fase 5) | FONDCART |
| Medium | 5. Peer comparison | MVP (dbt Fase 4–5) | FONDMENS, FONDTRIM, FONDCART |
| High | 6. AUM growth and flows | Release 1 (Fase 5b) | FONDMENS, FONDPATRIMDISVAR |
| High | 7. Fee and revenue quality | Release 1 (Fase 5b) | FONDPATRIMDISVAR, FONDTRIM |
| High | 8. Data quality and anomalies | Release 1 (Fase 5b) | FONDMENS, FONDTRIM, FONDPATRIMDISVAR, FONDCART |
| Low | 9. Rotation | Future | FONDCART (multi-period) |
| Low | 10. Derivatives | Future | FONDDERI |
