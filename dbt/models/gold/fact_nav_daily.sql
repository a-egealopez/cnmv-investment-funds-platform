with classified as (
    select * from {{ ref('int_nav_daily_classified') }}
)

select
    cl.class_id,
    d.date_key,
    c.nav,
    c.aum,
    c.holders,
    c.is_dormant,
    c.is_dust,
    c.is_dust_nav,
    c.is_dust_aum,
    c.is_dust_holders
from classified as c
inner join {{ ref('dim_class') }} as cl
    on cl.class_key = c.class_key
inner join {{ ref('dim_date') }} as d
    on c.value_date = d.date_day
where not c.is_material
