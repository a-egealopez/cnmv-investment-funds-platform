with latest as (
    select
        h.*,
        dense_rank() over (
            partition by h.compartment_id
            order by h.date_key desc
        ) as period_rank,
        row_number() over (
            partition by h.compartment_id, h.date_key
            order by h.weight desc nulls last
        ) as rank_by_weight
    from
        {{ ref('fact_holdings') }} as h
),

expected as (
    select
        compartment_id,
        date_key,
        count(*) filter (where weight is not null) as n_positions,
        sum(power(weight, 2)) as hhi,
        sum(weight) filter (where rank_by_weight <= 10) as top10_weight
    from
        latest
    where
        period_rank = 1
    group by
        1, 2
)

select
    p.compartment_id,
    p.holdings_date_key,
    p.n_positions as panorama_n_positions,
    e.n_positions as expected_n_positions,
    p.hhi as panorama_hhi,
    e.hhi as expected_hhi,
    p.top10_weight as panorama_top10_weight,
    e.top10_weight as expected_top10_weight
from
    {{ ref('mart_fund_panorama') }} as p
inner join expected as e
    on e.compartment_id = p.compartment_id
    and e.date_key = p.holdings_date_key
where
    p.n_positions <> e.n_positions
    or abs(p.hhi - e.hhi) > 1e-9
    or abs(coalesce(p.top10_weight, 0) - coalesce(e.top10_weight, 0)) > 1e-9
