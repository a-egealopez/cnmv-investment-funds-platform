{{ config(severity='warn') }}

-- Income statement identities. Unit: pp. Expenses negative in XML.
-- GR = ChargedExpenses; ING = Income; RN = NetReturn; RG = ManagementReturn.
-- Tolerance: 0.05pp absorbs 2-decimal rounding.

with residuals as (
    -- GR: ChargedExpenses = Management + Depositary + ExternalServices + OtherMgmt + OtherCharged
    select
        'GR' as identity,
        compartment_id,
        period,
        abs(charged_expenses_pct - (
            management_fee_pct
            + depositary_fee_pct
            + external_services_expenses_pct
            + other_management_expenses_pct
            + other_charged_expenses_pct)
        ) as residual
    from {{ ref('fact_fund_period_financials') }}

    union all

    -- ING: Income = DiscountCommissions + RetrocededCommissions + OtherRevenues
    select
        'ING' as identity,
        compartment_id,
        period,
        abs(income_pct - (
            discount_commissions_pct
            + retroceded_commissions_pct
            + other_revenues_pct)
        ) as residual
    from {{ ref('fact_fund_period_financials') }}

    union all

    -- RN: NetReturn = ManagementReturn + ChargedExpenses + Income
    -- (XML sign: ChargedExpenses already negative)
    select
        'RN' as identity,
        compartment_id,
        period,
        abs(net_return_pct - (
            management_return_pct
            + charged_expenses_pct
            + income_pct)
        ) as residual
    from {{ ref('fact_fund_period_financials') }}

    union all

    -- RG: ManagementReturn = Interest + Dividend + FixedIncomeResults + EquityResults
    --     + DepositResults + DerivativesResults + IICResults + OtherResults + OtherReturns
    select
        'RG' as identity,
        compartment_id,
        period,
        abs(
            management_return_pct
            - (
                interest_income_pct
                + dividend_income_pct
                + fixed_income_results_pct
                + equity_results_pct
                + deposit_results_pct
                + derivatives_results_pct
                + iic_results_pct
                + other_results_pct
                + other_returns_pct
            )
        ) as residual
    from {{ ref('fact_fund_period_financials') }}
)


select
    *
from
    residuals
where
    residual > 0.05