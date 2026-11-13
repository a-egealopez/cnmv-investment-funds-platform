-- Weights must sum to 1 and be in (0, 1].
-- Non-positive values are excluded from weighting.
with weights as (

    select
        compartment_id,
        date_key,
        sum(weight) as sum_weights,
        count(*) filter (where weight is not null and (weight <= 0 or weight > 1)) as n_weights_out_of_range
    from {{ ref('fact_holdings') }}
    group by compartment_id, date_key

)

select
    compartment_id,
    date_key,
    sum_weights,
    n_weights_out_of_range
from weights
where abs(sum_weights - 1) > 0.000001
   or n_weights_out_of_range > 0
