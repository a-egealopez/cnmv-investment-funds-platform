select
    *
from
    {{ ref('fact_fund_period_financials') }}
where
    core_fee_yield_rate < 0
    or other_expense_yield_rate < 0
    or charged_expense_yield_rate < 0
    or income_yield_rate < 0
    -- core_fee_share is a ratio: 1 is valid; the epsilon absorbs floating-point noise.
    or core_fee_share < -1e-9
    or core_fee_share > 1 + 1e-9
    or fee_revenue_proxy < 0