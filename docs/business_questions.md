# Business Questions

Last updated: 2026-09-26

## Context

Analysis of Spanish IIC to generate short-term buy/sell signals on fund assets.

Data source: CNMV (Comisión Nacional del Mercado de Valores).

## Questions

### Phase 1 (MVP)

#### 1. Fund Screening

**Question**: Which equity funds have the best risk-adjusted return over the last 6 months?

**Data needed**: FONDMENS (NAV series), FONDREGISTRO (metadata)

**Metrics**: CAGR, Sortino ratio, Calmar ratio, max drawdown

**Output**: Ranked fund table

### Phase 2 (Post-MVP) — requires IPP

#### 2. Portfolio Composition

**Question**: What sectors does fund X hold?

**Data needed**: IPP per-fund (holdings, sector allocation)

**Metrics**: Sector weights, top-10 holdings, HHI

**Output**: Sector breakdown chart

#### 3. Peer Comparison

**Question**: How does fund A's sector exposure compare to fund B?

**Data needed**: IPP per-fund (both funds)

**Metrics**: Sector weight difference, holdings overlap

**Output**: Side-by-side comparison table

#### 4. Asset Rotation

**Question**: What assets did top funds buy or sell between periods?

**Data needed**: IPP per-fund (multiple periods)

**Metrics**: New holdings, abandoned holdings, weight changes

**Output**: Rotation report

#### 5. Concentration

**Question**: Which funds are most concentrated in a single sector or asset?

**Data needed**: IPP per-fund, FONDMENS

**Metrics**: HHI, max sector weight, max single-asset weight

**Output**: Concentration ranking

#### 6. Strategy Evolution

**Question**: How has a fund's strategy changed over time?

**Data needed**: IPP per-fund (multiple periods)

**Metrics**: Sector distribution change, top holdings turnover

**Output**: Trend analysis

## Notes

- All return, volatility, and risk calculations are internal analysis, not official CNMV metrics
- Buy/sell conclusions are analytical signals, not financial advice
- Every metric must be traceable to its original CNMV source
- Each calculation must document its assumptions and limitations

## Implementation Priority

| Priority | Question | Phase | Depends on |
|----------|----------|-------|------------|
| High | 1. Screening | 1 (MVP) | FONDMENS, FONDREGISTRO |
| High | 2. Composition | 2 | IPP per-fund |
| Medium | 3. Comparison | 2 | IPP per-fund (x2) |
| Medium | 4. Rotation | 2 | IPP per-fund (multiple) |
| Low | 5. Concentration | 2 | IPP + FONDMENS |
| Low | 6. Evolution | 2 | IPP per-fund (multiple) |
