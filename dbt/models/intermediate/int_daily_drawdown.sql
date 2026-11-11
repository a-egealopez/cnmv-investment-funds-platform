with bounds as (
    {{ analysis_window() }}
),

daily as (
    select
        cast(f.class_id as varchar) as class_key,
        d.date_day as value_date,
        f.nav
    from
        {{ ref('fact_nav_daily') }} as f
    inner join {{ ref('dim_date') }} as d
        on f.date_key = d.date_key
    cross join bounds as b
    where
        not d.is_weekend
        and d.date_day between b.window_start and b.as_of_date
        and f.nav > 0
),

peaked as (
    select
        class_key,
        value_date,
        nav,
        max(nav) over (
            partition by class_key
            order by value_date
            rows between unbounded preceding and current row
        ) as running_peak
    from
        daily
)

select
    class_key,
    value_date,
    nav,
    running_peak,
    1 - nav / running_peak as drawdown
from
    peaked
