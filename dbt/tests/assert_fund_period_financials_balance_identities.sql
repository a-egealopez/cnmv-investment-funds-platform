{{ config(severity='warn') }}

-- Balance identities. Unit: EUR.
-- IF = FinancialInvestments; CI = DomesticPortfolio; CE = ForeignPortfolio;
-- IC = PortfolioInterest; ID = DoubtfulInvestments; TP = TotalPatrimony;
-- L = Cash; R = OtherAssets.
-- Tolerance: fixed 2,000€ materiality threshold, not precision.

with residuals as (
    -- IF: FinancialInvestments = Domestic + Foreign + Interest + Doubtful
    select
        'IF = CI + CE + IC + ID' as identity,
        compartment_id,
        period,
        abs(financial_investments - (
            domestic_portfolio
            + foreign_portfolio
            + portfolio_interest
            + doubtful_investments)
        ) as residual
    from {{ ref('fact_fund_period_financials') }}

    union all

    -- TP: TotalPatrimony = FinancialInvestments + Cash + OtherAssets.
    -- Not checked against PatrimonioFinPeriodoActual: not a stable source identity.
    select
        'TP = IF + L + R' as identity,
        compartment_id,
        period,
        abs(total_patrimony - (
            financial_investments
            + cash
            + other_assets)
        ) as residual
    from {{ ref('fact_fund_period_financials') }}
)


select
    *
from
    residuals
where
    residual > 2000