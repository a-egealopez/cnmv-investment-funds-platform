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
    inner join {{ ref('int_class_metrics') }} as m
        on m.class_key = r.class_key
    where
        r.is_representative
        and m.class_status = 'eligible'
        and m.sortino is not null
        and c.include_in_watchlist
),

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
            when p.n_peers < {{ var('min_peer_group_size') }} then null
            else greatest(1, ceil(p.pct_exact))
        end as percentile_in_vocation
    from
        percentiled as p
),

rated as (
    select
        s.*,
        -- Quartiles and star bands follow the Morningstar convention (fixed 10 / 22.5 / 35 / 22.5 / 10 %).
        -- They are constants of that convention, not tunable parameters.
        case
            when s.percentile_in_vocation is null then null
            when s.percentile_in_vocation <= 25 then 1
            when s.percentile_in_vocation <= 50 then 2
            when s.percentile_in_vocation <= 75 then 3
            else 4
        end as quartile_in_vocation,
        case
            when s.percentile_in_vocation is null then null
            when s.pct_exact <= 10   then 5
            when s.pct_exact <= 32.5 then 4
            when s.pct_exact <= 67.5 then 3
            when s.pct_exact <= 90   then 2
            else 1
        end as star_rating
    from scored as s
),

-- Watchlist selection: best funds by pct_exact (continuous; the rounded
-- percentile would tie 16 funds at percentile 1), capped per vocation, then per
-- family, then globally. AUM here is the representative class AUM, used only as
-- a tie-breaker.
by_vocation as (
    select
        r.*,
        row_number() over (
            partition by r.vocation
            order by r.pct_exact asc, r.cagr_3y desc, r.aum desc
        ) as rn_vocation
    from rated as r
),

by_family as (
    select
        v.*,
        row_number() over (
            partition by v.vocation_family
            order by v.pct_exact asc, v.cagr_3y desc, v.aum desc
        ) as rn_family
    from by_vocation as v
    where v.rn_vocation <= {{ var('max_per_vocacion') }}
),

ordered as (
    select
        f.compartment_key,
        row_number() over (
            order by f.pct_exact asc, f.cagr_3y desc, f.aum desc
        ) as rn_global
    from by_family as f
    where f.rn_family <= {{ var('watchlist_per_family') }}
)

select
    r.* exclude (rn_vocation),
    o.rn_global as watchlist_rank
from by_vocation as r
left join ordered as o
    on o.compartment_key = r.compartment_key
    and o.rn_global <= {{ var('watchlist_max') }}
