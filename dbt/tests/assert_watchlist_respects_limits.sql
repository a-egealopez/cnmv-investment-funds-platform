-- Watchlist cannot exceed global limit.
-- Max 2 funds per vocation, 5 per family.
with selected as (

    select *
    from {{ ref('int_fund_peer_ranking') }}
    where watchlist_rank is not null

),

over_global as (

    select count(*) as n
    from selected
    group by all

)

select
    (select count(*) from selected) as n_selected,
    {{ var('watchlist_max') }} as watchlist_max
from over_global
where (select count(*) from selected) > {{ var('watchlist_max') }}
