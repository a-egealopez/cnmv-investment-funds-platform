with source as (
    select
        *
    from
        {{ ref('stg_fund_period_financials') }}
),

metrics as (
    select
        *,
        abs(management_fee_pct + depositary_fee_pct) as core_fee_yield_pct,
        abs(external_services_expenses_pct + other_management_expenses_pct + other_charged_expenses_pct) as other_expense_yield_pct,
        abs(charged_expenses_pct) as expense_ratio_pct,
        abs(income_pct) as income_yield_pct
    from
        source
)

select
    compartment_key,
    period,

    portfolio_turnover_current,
    portfolio_turnover_previous,

    financial_investments,
    domestic_portfolio,
    foreign_portfolio,
    portfolio_interest,
    doubtful_investments,
    cash,
    other_assets,
    total_patrimony,
    patrimony_previous_period,
    patrimony_current_period,

    net_subscriptions_redemptions_pct,
    gross_distributed_profit_pct,
    net_income_pct as net_return_pct,
    management_income_pct as management_return_pct,
    interest_income_pct,
    dividend_income_pct,
    fixed_income_results_pct,
    equity_results_pct,
    deposit_results_pct,
    derivatives_results_pct,
    iic_results_pct,
    other_results_pct,
    other_returns_pct,

    charged_expenses_pct,
    management_fee_pct,
    depositary_fee_pct,
    external_services_expenses_pct,
    other_management_expenses_pct,
    other_charged_expenses_pct,
    income_pct,
    discount_commissions_pct,
    retroceded_commissions_pct,
    other_revenues_pct,

    core_fee_yield_pct,
    other_expense_yield_pct,
    expense_ratio_pct,
    income_yield_pct,
    core_fee_yield_pct / nullif(expense_ratio_pct, 0) as core_fee_share,
    total_patrimony * core_fee_yield_pct / 100 as fee_revenue_proxy
from metrics
