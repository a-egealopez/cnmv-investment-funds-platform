select
    *
from
    {{ ref('fact_fund_period_financials') }}
where
    core_fee_yield_pct < 0
    or other_expense_yield_pct < 0
    or expense_ratio_pct < 0
    or income_yield_pct < 0
    or core_fee_share < 0
    or core_fee_share > 1
    or fee_revenue_proxy < 0