with latest_metadata as (
    {{ latest_by_period(
        relation=ref('stg_fund_metadata'),
        key='compartment_key',
        as_of_period=var('as_of_period')
    ) }}
),

latest_quarterly as (
    {{ latest_by_period(
        relation=ref('stg_fund_quarterly'),
        key='compartment_key',
        as_of_period=var('as_of_period')
    ) }}
)

select
    row_number() over (order by m.compartment_key) as compartment_id,
    m.compartment_key,
    f.fund_id,
    f.fund_key,
    f.fund_type,
    f.registration_number,
    m.compartment_number,
    m.compartment_name,
    coalesce(va.canonical_vocation, q.vocation) as vocation,
    coalesce(vf.family, 'No vocation') as vocation_family,
    coalesce(vf.include_in_watchlist, false) as include_in_watchlist,
    q.fund_class
from latest_metadata as m
left join latest_quarterly as q
    on q.compartment_key = m.compartment_key
left join {{ ref('vocation_aliases') }} as va
    on va.source_vocation = q.vocation
left join {{ ref('vocacion_family') }} as vf
    on vf.vocation = coalesce(va.canonical_vocation, q.vocation)
left join {{ ref('dim_fund') }} as f
    on f.fund_key = m.fund_key
