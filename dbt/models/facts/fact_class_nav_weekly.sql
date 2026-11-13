-- Weekly NAV series for eligible classes (comparable, complete metrics).
-- Grain: class_id x week_end_date. Rebasing to 100 is done in BI/DAX to
-- respect the selected period; this model provides the weekly NAV only.
with eligible as (
    select
        cl.class_id,
        w.week_end_date,
        w.nav
    from
        {{ ref('int_weekly_nav_returns') }} as w
    inner join {{ ref('int_class_metrics') }} as m
        on m.class_key = w.class_key
    inner join {{ ref('dim_class') }} as cl
        on cl.class_key = w.class_key
    where
        m.class_status = 'eligible'
        and w.nav is not null
)

select
    e.class_id,
    d.date_key,
    e.nav
from
    eligible as e
inner join {{ ref('dim_date') }} as d
    on d.date_day = e.week_end_date
