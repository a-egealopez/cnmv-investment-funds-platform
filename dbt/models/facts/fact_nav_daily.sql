with classified as (
    select * from {{ ref('int_nav_daily_classified') }}
)

select
    cl.class_id,
    d.date_key,
    c.nav,
    c.aum,
    case
        when c.holders = 0 and c.aum > 0 then null
        else c.holders
    end as holders,
    c.nav > 0 and c.aum > 0 as is_valid_nav,
    c.is_dormant,
    c.is_dust,
    (c.nav > 0 and c.aum > 0 and not c.is_dormant and not c.is_dust) as is_usable
from classified as c
inner join {{ ref('dim_class') }} as cl
    on cl.class_key = c.class_key
inner join {{ ref('dim_date') }} as d
    on c.value_date = d.date_day
where not c.is_material
