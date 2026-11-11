with latest_metadata as (
    {{ latest_by_period(
        relation=ref('stg_fund_metadata'),
        key='class_key',
        as_of_period=var('as_of_period')
    ) }}
),

latest_quarterly as (
    {{ latest_by_period(
        relation=ref('stg_fund_quarterly'),
        key='class_key',
        as_of_period=var('as_of_period')
    ) }}
)

select
    row_number() over (order by m.class_key) as class_id,
    m.class_key,
    m.compartment_key,
    p.compartment_id,
    m.class_number,
    m.class_name,
    m.isin,
    q.class_currency_code,
    q.iic_currency_code
from latest_metadata as m
left join latest_quarterly as q
    on q.class_key = m.class_key
left join {{ ref('dim_compartment') }} as p
    on p.compartment_key = m.compartment_key
