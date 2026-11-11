-- Portfolio composition by asset category.
-- Grain: compartment_key x holdings_period x descripcion_if x clase_if.
--
-- Both description and class are exposed because the same description can
-- appear in EXTERIOR and INTERIOR with different weights.
with positions as (
    select
        h.compartment_id,
        h.holdings_period,
        h.descripcion_if,
        h.clase_if,
        count(*) as n_positions,
        sum(h.position_value) as position_value,
        sum(h.weight) as weight
    from
        {{ ref('fact_holdings') }} as h
    where
        h.weight is not null
    group by
        1, 2, 3, 4
)

select
    p2.compartment_id as compartment_id,
    p.holdings_period,
    p.descripcion_if,
    p.clase_if,
    p.n_positions,
    p.position_value,
    p.weight,
    p.weight / nullif(sum(p.weight) over (
        partition by p.compartment_id, p.holdings_period
    ), 0) as weight_share
from
    positions as p
inner join {{ ref('dim_compartment') }} as p2
    on p2.compartment_id = p.compartment_id
