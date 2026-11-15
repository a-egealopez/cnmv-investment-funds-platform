# Product

Last updated: 2026-11-15

## Summary

The CNMV publishes detailed data on every Spanish investment fund, but in large, deeply nested XML files that are hard to use. This platform turns them into three things an analyst can work with:

1. A **panorama** of every active fund compartment, with its 3- and 5-year performance and risk.
2. A **watchlist** of up to 20 compartments with the best past risk-adjusted returns in their category, after strict data-quality screening.
3. A layer of **flows, fees and data-quality signals** that explains how each fund grows, what it costs and whether its figures can be trusted.

Everything it produces is an analytical signal. The watchlist is a starting point for research and makes no prediction about future returns.

## Users

- **Individual investors** who want data-driven fund research without paying for commercial data services.
- **Financial analysts** who need to compare funds with their peers, inspect portfolios and spot unusual behaviour before a deeper review.

## Scope and data

The universe is every Spanish investment fund (FI) registered with the CNMV since 2020: about 2,500 compartments and 4,700 share classes, of which 1,263 active compartments are in the panorama at the 202608 cut-off. Metrics are computed per share class; funds are selected per compartment; peers are the funds with the same CNMV investor vocation.

Sources: CNMV (FONDMENS, FONDREGISTRO, FONDTRIM, FONDCART, FONDPATRIMDISVAR) and the ECB €STR rate. See [sources.md](../analytics/sources.md).

## Questions the platform answers

| # | Question | Main metrics | Where to find it |
|---|----------|--------------|------------------|
| 1 | What is the state of every active fund: measurable, quarantined (and why) or too new? | Window coverage, quarantine reason per class | `mart_fund_panorama`, `mart_fund_class_status` |
| 2 | Which 20 compartments have the best past risk-adjusted returns within their category? | Sortino vs €STR, percentile and quartile in vocation, CAGR, volatility, drawdown | `mart_fund_panorama` (`watchlist_status = 'selected'`) |
| 3 | How concentrated is a fund's portfolio? | HHI, effective number of positions, top-10 weight | `mart_fund_panorama`, `fact_holdings` |
| 4 | What does a fund hold, by asset type? | Weights by reported asset category, top-10 positions | `fact_holdings` |
| 5 | How does a fund compare with its peers? | Percentile, quartile and star rating in its vocation | `mart_fund_panorama` |
| 6 | Is a fund growing from returns or from new money? | Market effect, net flows, flow yield, retention proxies | `fact_compartment_monthly` |
| 7 | How much of a fund's cost is management and custody fees, and how concentrated is fee revenue? | Fee yields, fee revenue estimate, fee HHI and top-5 share by manager group | `fact_fund_period_financials`, `fact_manager_group_monthly`, `fact_market_fee_and_aum` |
| 8 | Which funds have figures that don't reconcile or behave unusually? | Reconciliation error, gaps, stale prices, extreme moves, fee and flow outliers | `fact_fund_anomalies` |

Two questions are left for the future: asset rotation between closings (which positions a fund bought or sold) and the use of derivatives, which would need the FONDDERI file.

## What success looks like

- The pipeline runs end to end every week with no manual steps.
- Every active class has an explicit status, and no record is dropped without a reason.
- The watchlist respects its rules: at most 20 compartments, EUR, legal size floors, a category with at least 5 peers, and clean data.
- Portfolio weights sum to one, the AUM bridge balances and the income statement identities hold.
- Metrics recomputed independently match the dbt output, and returns match the official CNMV figures.

All of these are checked by dbt tests or by the scripts in `tests/integration/`.

## Risks and assumptions

- The CNMV may change its XML schema without notice. Explicit schemas and the quality gate catch it before it reaches dbt.
- Quarantine rules can produce false positives for very low-volatility classes.
- Survivorship bias: the worst funds tend to disappear through mergers or liquidation.
- Past rankings persist weakly, which is why the watchlist is framed as a filter on past performance.
- CNMV categories are broad (*Renta Fija Euro* mixes very different durations). Ranking within category and risk class is a possible refinement.
- A weekly Sortino over three years rests on about 156 observations, so small differences between peers are noise.
- FONDPATRIMDISVAR has no success fee and no gross flows, so those analyses are out of reach.
- FONDCART has no issuer or sector, so concentration is measured by instrument and asset type.
- Portfolio weights use the reported positions; they cover a median 96% of the fund's assets.

## Open questions

- Which benchmark to use for beta and alpha: IBEX 35, MSCI World or a CNMV fund proxy?
- Should a fee filter be added to the watchlist?
- Should there be a web interface in addition to Power BI?
