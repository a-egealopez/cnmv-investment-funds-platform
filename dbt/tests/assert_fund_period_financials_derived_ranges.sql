select
    *
from
    {{ ref('fact_fund_period_financials') }}
where
    core_fee_yield_rate < 0
    or other_expense_yield_rate < 0
    or charged_expense_yield_rate < 0
    or income_yield_rate < 0
    -- No upper bound on core_fee_share: when the other charged items net to a credit
    -- (positive sign), core fees legitimately exceed total charged expenses.
    or core_fee_share < -1e-9
    or fee_revenue_proxy < 0