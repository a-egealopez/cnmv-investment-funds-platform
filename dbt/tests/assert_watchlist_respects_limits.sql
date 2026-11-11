-- Watchlist cannot exceed global limit.
-- Max 2 funds per vocation, 5 per family.
with selected as (

    select *
    from {{ ref('mart_fund_watchlist') }}
    where watchlist_status = 'selected'

),

over_global as (

    select count(*) as n
    from selected
    where true
    group by all

)

select
    (select count(*) from selected) as n_selected,
    {{ var('watchlist_max', 20) }} as watchlist_max
from over_global
where (select count(*) from selected) > {{ var('watchlist_max', 20) }}
