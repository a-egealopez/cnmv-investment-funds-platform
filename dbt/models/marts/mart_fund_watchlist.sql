-- Investable peers: representative, eligible class in the watchlist currency
-- with a non-null Sortino and a vocation included in the selection.
with investable as (
    select
        r.compartment_key,
        r.class_key,
        c.vocation,
        c.vocation_family,
        r.aum,
        m.sortino,
        m.cagr_3y
    from
        {{ ref('int_representative_class') }} as r
    inner join {{ ref('dim_compartment') }} as c
        on c.compartment_key = r.compartment_key
    inner join {{ ref('int_class_metrics_36m') }} as m
        on m.class_key = r.class_key
    where
        r.is_representative
        and m.class_status = 'eligible'
        and m.sortino is not null
        and c.include_in_watchlist
),

-- Percentile within vocation (Morningstar formula).
-- rank() shares ranks on ties; pct_exact = 100 * (c - 1) / (n - 1).
-- A group smaller than min_peer_group_size has no percentile.
percentiled as (
    select
        i.*,
        100.0 * (rank() over (partition by i.vocation order by i.sortino desc) - 1)
            / nullif(count(*) over (partition by i.vocation) - 1, 0) as pct_exact,
        count(*) over (partition by i.vocation) as n_peers
    from
        investable as i
),

scored as (
    select
        p.*,
        case
            when p.n_peers < {{ var('min_peer_group_size', 5) }} then null
            else greatest(1, ceil(p.pct_exact))
        end as percentile_in_vocation
    from
        percentiled as p
),

quartiled as (
    select
        p.*,
        case
            when p.percentile_in_vocation is null then null
            when p.percentile_in_vocation <= 25 then 1
            when p.percentile_in_vocation <= 50 then 2
            when p.percentile_in_vocation <= 75 then 3
            else 4
        end as quartile_in_vocation
    from
        scored as p
),

-- Selection order: ascending pct_exact (best first), not the rounded percentile:
-- rounding collapses many funds into percentile 1 and the CAGR tie-break
-- reorders them arbitrarily. Tie-break by CAGR desc, then AUM desc.
ordered as (
    select
        q.*,
        row_number() over (
            partition by q.vocation_family
            order by q.pct_exact asc, q.cagr_3y desc, q.aum desc
        ) as rn_family,
        row_number() over (
            partition by q.vocation
            order by q.pct_exact asc, q.cagr_3y desc, q.aum desc
        ) as rn_vocation,
        row_number() over (
            order by q.pct_exact asc, q.cagr_3y desc, q.aum desc
        ) as rn_global
    from
        quartiled as q
),

-- Cap per family, then per vocation, then the global limit.
selected as (
    select
        o.*,
        case
            when o.rn_global <= {{ var('watchlist_max', 20) }} then 'selected'
            else 'not_selected'
        end as watchlist_status
    from
        ordered as o
    where
        o.rn_family <= {{ var('watchlist_per_family', 5) }}
        and o.rn_vocation <= {{ var('max_per_vocacion', 2) }}
)

select
    '{{ var("as_of_period") }}' as as_of_period,
    c.compartment_id as compartment_id,
    cl.class_id as class_id,
    s.vocation_family as family,
    s.vocation,
    s.rn_global as rnk,
    s.percentile_in_vocation as percentile,
    s.quartile_in_vocation as quartile,
    s.sortino,
    s.cagr_3y,
    s.aum,
    s.watchlist_status
from
    selected as s
inner join {{ ref('dim_compartment') }} as c
    on c.compartment_key = s.compartment_key
inner join {{ ref('dim_class') }} as cl
    on cl.class_key = s.class_key
