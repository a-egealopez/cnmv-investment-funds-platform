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
    p.compartment_id,
    f.period,

    f.portfolio_turnover_current,
    f.portfolio_turnover_previous,

    f.financial_investments,
    f.domestic_portfolio,
    f.foreign_portfolio,
    f.portfolio_interest,
    f.doubtful_investments,
    f.cash,
    f.other_assets,
    f.total_patrimony,
    f.patrimony_previous_period,
    f.patrimony_current_period,

    f.net_subscriptions_redemptions_pct,
    f.gross_distributed_profit_pct,
    f.net_income_pct as net_return_pct,
    f.management_income_pct as management_return_pct,
    f.interest_income_pct,
    f.dividend_income_pct,
    f.fixed_income_results_pct,
    f.equity_results_pct,
    f.deposit_results_pct,
    f.derivatives_results_pct,
    f.iic_results_pct,
    f.other_results_pct,
    f.other_returns_pct,

    f.charged_expenses_pct,
    f.management_fee_pct,
    f.depositary_fee_pct,
    f.external_services_expenses_pct,
    f.other_management_expenses_pct,
    f.other_charged_expenses_pct,
    f.income_pct,
    f.discount_commissions_pct,
    f.retroceded_commissions_pct,
    f.other_revenues_pct,

    f.core_fee_yield_pct,
    f.other_expense_yield_pct,
    f.expense_ratio_pct,
    f.income_yield_pct,
    f.core_fee_yield_pct / nullif(f.expense_ratio_pct, 0) as core_fee_share,
    f.total_patrimony * f.core_fee_yield_pct / 100 as fee_revenue_proxy
from metrics as f
inner join {{ ref('dim_compartment') }} as p
    on p.compartment_key = f.compartment_key
