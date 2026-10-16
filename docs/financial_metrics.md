# Financial Metrics

Last updated: 2026-09-26

## Confirmed Metrics

### Return

| Metric | Formula | Description |
|--------|---------|-------------|
| **CAGR** | `(NAV_end / NAV_start)^(252/n_days) - 1` | Compound annual growth rate |
| **Daily return** | `(VL_t - VL_{t-1}) / VL_{t-1}` | Base return calculation |

### Risk

| Metric | Formula | Description |
|--------|---------|-------------|
| **Volatility** | `stddev(daily_returns) * sqrt(252)` | Annualized standard deviation |
| **Max Drawdown** | `max(1 - NAV / cummax(NAV))` | Worst peak-to-trough decline |
| **Sortino Ratio** | `(CAGR - risk_free) / downside_deviation` | Return per unit of bad risk |

### Return / Risk

| Metric | Formula | Description |
|--------|---------|-------------|
| **Calmar Ratio** | `CAGR / max_drawdown` | Return relative to worst scenario |

### Concentration

| Metric | Formula | Description |
|--------|---------|-------------|
| **HHI** | `sum(weight_i^2)` | Herfindahl-Hirschman Index (0–1) |
| **Sector Exposure** | `sum(weights where sector = X)` | Aggregate sector weight |

### Portfolio Activity

| Metric | Formula | Description |
|--------|---------|-------------|
| **Turnover Ratio** | `sum(abs(weight_t - weight_{t-1})) / 2` | Portfolio rotation between periods |
| **Active Share** | `sum(abs(weight_fund - weight_benchmark)) / 2` | Deviation from benchmark (0–1) |

## Blocked Metrics (require benchmark — Version 0.2)

| Metric | Formula | Description |
|--------|---------|-------------|
| **Jensen's Alpha** | `fund_return - (risk_free + beta * (market_return - risk_free))` | Excess return after adjusting for market risk |
| **Beta** | `cov(fund_returns, market_returns) / var(market_returns)` | Sensitivity to market movements |
| **Tracking Error** | `stddev(fund_returns - benchmark_returns)` | Volatility of excess return vs benchmark |

**Status**: Blocked pending benchmark selection (IBEX 35, MSCI World, or CNMV fund proxy).

## Methodological Notes

- **Risk-free rate (Rf)**: 2.5% static for Phase 1 (approximation of Spanish 10-year bond yield). To be revisited when benchmark is selected.
- **Trading days**: 252 per year
- All metrics are internal analysis, not official CNMV calculations
- Every metric must document its assumptions and data source
