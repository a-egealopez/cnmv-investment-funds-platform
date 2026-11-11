with classified as (
    select * from {{ ref('int_nav_daily_classified') }}
)

select
    c.period,
    c.value_date,
    c.fund_key,
    c.compartment_key,
    cl.class_id,
    c.isin,
    c.fund_type,
    c.registration_number,
    c.compartment_number,
    c.class_number,
    c.nav,
    c.aum,
    c.holders,
    c.is_material,
    c.is_dust,
    c.quarantine_reason
from classified as c
inner join {{ ref('dim_class') }} as cl
    on cl.class_key = c.class_key
where c.is_material
