-- Monthly identity: net_flows + market_effect = delta_aum.
-- Tolerance: 1 EUR or 1e-9 relative, whichever is larger (float sums).
select *
from {{ ref('fact_compartment_monthly') }}
where abs(net_flows + market_effect - delta_aum) > greatest(1, 1e-9 * abs(delta_aum))
