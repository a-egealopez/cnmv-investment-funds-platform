-- Bridge identity: delta_aum = market_effect + net_flows.
-- Tolerance covers rounding, not calculation error.
select
    class_key,
    value_date,
    delta_aum,
    market_effect + net_flows as effect_plus_flows
from {{ ref('int_fund_aum_bridge') }}
where abs(delta_aum - (market_effect + net_flows)) > 0.01
