with source as (
    select
        *
    from
        {{ ref('stg_fund_period_financials') }}
    where
        period <= {{ current_as_of_period() }}
),

metrics as (
    select
        *,
        abs(management_fee_rate + depositary_fee_rate) as core_fee_yield_rate,
        -- Management fee only: what the manager charges. The depositary fee goes
        -- to the depositary, not to the manager.
        abs(management_fee_rate) as management_fee_yield_rate,
        abs(external_services_expenses_rate + other_management_expenses_rate + other_charged_expenses_rate) as other_expense_yield_rate,
        abs(charged_expenses_rate) as charged_expense_yield_rate,
        abs(income_rate) as income_yield_rate,

        -- FONDPATRIMDISVAR rates are cumulative for the year: June covers 6
        -- months and December 12. period_months and the annualized columns make
        -- the two closings comparable.
        cast(substr(period, 5, 2) as integer) as period_months,

        -- The rates are over average patrimony, so the average of the start and
        -- end of the period is a better base than the closing value alone.
        coalesce(
            (patrimony_previous_period + patrimony_current_period) / 2,
            total_patrimony
        ) as average_patrimony
    from
        source
)

select
    p.compartment_id,
    dd.date_key as date_key,

    f.portfolio_turnover_current,
    f.portfolio_turnover_previous,

    f.total_patrimony,
    f.patrimony_previous_period,
    f.patrimony_current_period,

    f.net_subscriptions_redemptions_rate,
    f.gross_distributed_profit_rate,
    f.net_income_rate as net_return_rate,
    f.management_income_rate as management_return_rate,
    f.interest_income_rate,
    f.dividend_income_rate,
    f.fixed_income_results_rate,
    f.equity_results_rate,
    f.deposit_results_rate,
    f.derivatives_results_rate,
    f.iic_results_rate,
    f.other_results_rate,
    f.other_returns_rate,

    f.charged_expenses_rate,
    f.management_fee_rate,
    f.depositary_fee_rate,
    f.external_services_expenses_rate,
    f.other_management_expenses_rate,
    f.other_charged_expenses_rate,
    f.income_rate,
    f.discount_commissions_rate,
    f.retroceded_commissions_rate,
    f.other_revenues_rate,

    f.core_fee_yield_rate,
    f.other_expense_yield_rate,
    f.charged_expense_yield_rate,
    f.income_yield_rate,
    f.core_fee_yield_rate / nullif(f.charged_expense_yield_rate, 0) as core_fee_share,
    f.average_patrimony * f.core_fee_yield_rate as fee_revenue_proxy,

    f.period_months,
    f.average_patrimony,
    f.core_fee_yield_rate * 12 / f.period_months as core_fee_yield_annualized_rate,
    f.other_expense_yield_rate * 12 / f.period_months as other_expense_yield_annualized_rate,
    f.charged_expense_yield_rate * 12 / f.period_months as charged_expense_yield_annualized_rate,
    f.income_yield_rate * 12 / f.period_months as income_yield_annualized_rate,
    f.average_patrimony * f.core_fee_yield_rate * 12 / f.period_months as fee_revenue_proxy_annualized,

    f.management_fee_yield_rate,
    f.management_fee_yield_rate * 12 / f.period_months as management_fee_yield_annualized_rate,
    f.average_patrimony * f.management_fee_yield_rate as management_fee_revenue,
    f.average_patrimony * f.management_fee_yield_rate * 12 / f.period_months as management_fee_revenue_annualized,

    -- Flag to filter outliers before charting. It does not remove rows.
    coalesce(
        f.charged_expense_yield_rate > {{ var('max_fee_yield') }}, false
    ) as is_fee_outlier
from metrics as f
inner join {{ ref('dim_compartment') }} as p
    on p.compartment_key = f.compartment_key
left join {{ ref('dim_date') }} as dd
    on dd.date_day = cast(
        last_day(cast(strptime(f.period || '01', '%Y%m%d') as date)) as date
    )
