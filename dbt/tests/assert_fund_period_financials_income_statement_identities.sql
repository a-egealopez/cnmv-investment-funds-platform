{{ config(severity='warn', warn_if='>10') }}
-- Known baseline: 4 rows in real data. It only warns if the issue grows.

-- Income statement identities. Unit: fraction (0.01 = 1%). Expenses negative in XML.
-- GR = ChargedExpenses; ING = Income; RN = NetReturn; RG = ManagementReturn.
-- Tolerance: 0.0005 (0.05pp) absorbs 2-decimal rounding.

with residuals as (
    -- GR: ChargedExpenses = Management + Depositary + ExternalServices + OtherMgmt + OtherCharged
    select
        'GR' as identity,
        compartment_id,
        date_key,
        abs(charged_expenses_rate - (
            management_fee_rate
            + depositary_fee_rate
            + external_services_expenses_rate
            + other_management_expenses_rate
            + other_charged_expenses_rate)
        ) as residual
    from {{ ref('fact_fund_period_financials') }}

    union all

    -- ING: Income = DiscountCommissions + RetrocededCommissions + OtherRevenues
    select
        'ING' as identity,
        compartment_id,
        date_key,
        abs(income_rate - (
            discount_commissions_rate
            + retroceded_commissions_rate
            + other_revenues_rate)
        ) as residual
    from {{ ref('fact_fund_period_financials') }}

    union all

    -- RN: NetReturn = ManagementReturn + ChargedExpenses + Income
    -- (XML sign: ChargedExpenses already negative)
    select
        'RN' as identity,
        compartment_id,
        date_key,
        abs(net_return_rate - (
            management_return_rate
            + charged_expenses_rate
            + income_rate)
        ) as residual
    from {{ ref('fact_fund_period_financials') }}

    union all

    -- RG: ManagementReturn = Interest + Dividend + FixedIncomeResults + EquityResults
    --     + DepositResults + DerivativesResults + IICResults + OtherResults + OtherReturns
    select
        'RG' as identity,
        compartment_id,
        date_key,
        abs(
            management_return_rate
            - (
                interest_income_rate
                + dividend_income_rate
                + fixed_income_results_rate
                + equity_results_rate
                + deposit_results_rate
                + derivatives_results_rate
                + iic_results_rate
                + other_results_rate
                + other_returns_rate
            )
        ) as residual
    from {{ ref('fact_fund_period_financials') }}
)


select
    *
from
    residuals
where
    residual > 0.0005