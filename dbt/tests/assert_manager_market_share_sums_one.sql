-- Market shares of the manager groups must add up to 1 in every month.
select
    date_key,
    sum(market_share) as sum_market_share
from {{ ref('fact_manager_group_monthly') }}
group by date_key
having abs(sum(market_share) - 1) > 1e-9
