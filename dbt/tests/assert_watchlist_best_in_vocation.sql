-- Best fund per vocation should be in watchlist if any selected from that vocation.
-- Selection orders by pct_exact (continuous); rounding ties may arbitrarily drop funds.
-- Global truncation (watchlist_max) may legitimately exclude best of a vocation.
with peers as (

    select
        r.compartment_key,
        c.vocation,
        m.sortino,
        row_number() over (
            partition by c.vocation
            order by m.sortino desc
        ) as rank_in_vocation,
        count(*) over (
            partition by c.vocation
        ) as n_peers
    from {{ ref('int_representative_class') }} as r
    inner join {{ ref('dim_compartment') }} as c
        on c.compartment_key = r.compartment_key
    inner join {{ ref('int_class_metrics_36m') }} as m
        on m.class_key = r.class_key
    where r.is_representative
      and m.class_status = 'eligible'
      and m.sortino is not null
      and c.include_in_watchlist

),

selected as (

    select compartment_id as compartment_key
    from {{ ref('mart_fund_watchlist') }}
    where watchlist_status = 'selected'

),

-- Vocaciones con al menos un fondo seleccionado.
selected_vocations as (

    select distinct c.vocation
    from {{ ref('mart_fund_watchlist') }} as w
    inner join {{ ref('dim_compartment') }} as c
        on c.compartment_id = w.compartment_id
    where w.watchlist_status = 'selected'

)

select
    p.compartment_key,
    p.vocation,
    p.rank_in_vocation,
    p.n_peers
from peers as p
inner join selected_vocations as sv
    on sv.vocation = p.vocation
where p.rank_in_vocation = 1
  and not exists (
      select 1
      from selected as s
      where s.compartment_key = p.compartment_key
  )
  -- Si la watchlist esta truncada por el tope global, el mejor puede quedar fuera legitimo.
  and (select count(*) from selected) < {{ var('watchlist_max', 20) }}
