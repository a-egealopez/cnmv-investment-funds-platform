-- Rebasing is only meaningful for comparable classes with complete metrics.
with eligible as (
    select
        cl.class_id,
        w.week_end_date,
        w.nav
    from
        {{ ref('int_weekly_nav_returns') }} as w
    inner join {{ ref('int_class_metrics_36m') }} as m
        on m.class_key = w.class_key
    inner join {{ ref('dim_class') }} as cl
        on cl.class_key = w.class_key
    where
        m.class_status = 'eligible'
        and w.nav is not null
),

-- Base 100: first observed NAV of the series.
based as (
    select
        e.class_id,
        e.week_end_date,
        e.nav,
        first_value(e.nav) over (
            partition by e.class_id
            order by e.week_end_date
        ) as base_nav
    from
        eligible as e
)

select
    '{{ var("as_of_period") }}' as as_of_period,
    b.class_id,
    b.week_end_date,
    b.nav,
    b.base_nav,
    100.0 * b.nav / nullif(b.base_nav, 0) as nav_rebased_100
from
    based as b
