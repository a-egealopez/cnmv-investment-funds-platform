-- Top ten positions per compartment.
-- Grain: compartment_key x holdings_period x position_rank.
--
-- Resolved as a view over fact_holdings, which already aggregates each
-- instrument's weight and ranks it inside the compartment.
with ranked as (
    select
        h.compartment_id,
        h.holdings_period,
        h.instrument_key,
        h.isin,
        h.clase_if,
        h.descripcion_if,
        h.asset_description,
        h.position_value,
        h.weight,
        row_number() over (
            partition by h.compartment_id, h.holdings_period
            order by h.weight desc nulls last, h.instrument_key
        ) as position_rank
    from
        {{ ref('fact_holdings') }} as h
    where
        h.weight is not null
)

select
    p.compartment_id as compartment_id,
    r.holdings_period,
    r.position_rank,
    r.instrument_key,
    r.isin,
    r.clase_if,
    r.descripcion_if,
    r.asset_description,
    r.position_value,
    r.weight
from
    ranked as r
inner join {{ ref('dim_compartment') }} as p
    on p.compartment_id = r.compartment_id
where
    r.position_rank <= 10
