-- Single definition of an active class at the as-of date: positive AUM and
-- holders on the last available NAV date. Used by representative selection,
-- the panorama and the class-status audit, so all of them stay consistent.
with bounds as (
    {{ analysis_window() }}
)

select
    cl.class_id,
    cl.class_key,
    cl.compartment_id,
    cl.compartment_key,
    f.aum,
    f.holders as participants
from
    {{ ref('fact_nav_daily') }} as f
inner join {{ ref('dim_class') }} as cl
    on cl.class_id = f.class_id
inner join bounds as b
    on f.date_key = cast(strftime(b.as_of_date, '%Y%m%d') as integer)
where
    f.aum > 0
    and f.holders > 0
