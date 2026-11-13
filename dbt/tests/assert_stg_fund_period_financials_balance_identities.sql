{{ config(severity='warn', warn_if='>5') }}
-- Known baseline: 1 row in real data. It only warns if the issue grows.

-- Balance identities of the source (stg_fund_period_financials). Unit: EUR.
-- IF = FinancialInvestments; CI = DomesticPortfolio; CE = ForeignPortfolio;
-- IC = PortfolioInterest; ID = DoubtfulInvestments; TP = TotalPatrimony;
-- L = Cash; R = OtherAssets.
-- Tolerance: fixed 2,000€ materiality threshold, not precision.

with residuals as (
    -- IF: FinancialInvestments = Domestic + Foreign + Interest + Doubtful
    select
        'IF = CI + CE + IC + ID' as identity,
        compartment_key,
        period,
        abs(financial_investments - (
            domestic_portfolio
            + foreign_portfolio
            + portfolio_interest
            + doubtful_investments)
        ) as residual
    from {{ ref('stg_fund_period_financials') }}

    union all

    -- TP: TotalPatrimony = FinancialInvestments + Cash + OtherAssets.
    -- Not checked against PatrimonioFinPeriodoActual: not a stable source identity.
    select
        'TP = IF + L + R' as identity,
        compartment_key,
        period,
        abs(total_patrimony - (
            financial_investments
            + cash
            + other_assets)
        ) as residual
    from {{ ref('stg_fund_period_financials') }}
)


select
    *
from
    residuals
where
    residual > 2000