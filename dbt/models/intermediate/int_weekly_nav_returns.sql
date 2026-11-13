with bounds as (
    {{ analysis_window() }}
),

daily as (
    select
        cl.class_key,
        d.date_day      as value_date,
        d.week_end_date,
        f.nav
    from
        {{ ref('fact_nav_daily') }} as f
    inner join {{ ref('dim_date') }} as d
        on f.date_key = d.date_key
    inner join {{ ref('dim_class') }} as cl
        on cl.class_id = f.class_id
    cross join bounds as b
    where
        not d.is_weekend
        and d.date_day between b.window_start and b.as_of_date
),

weekly as (
    select
        class_key,
        week_end_date,
        max(value_date) filter (where nav > 0)          as nav_date,
        arg_max(nav, value_date) filter (where nav > 0) as nav,
        count(*) filter (where nav <= 0)                as n_dormant_days,
        count(*)                                        as n_days
    from
        daily
    group by
        class_key, week_end_date
),

weekly_lagged as (
    select
        w.*,
        lag(w.week_end_date) over by_class as prev_week_end_date,
        lag(w.nav)           over by_class as prev_nav
    from
        weekly as w
    window by_class as (partition by class_key order by week_end_date)
),

weekly_returns as (
    select
        w.*,
        case
            when w.nav is null                then null
            when w.prev_nav is null           then null
            when w.prev_week_end_date
                 <> w.week_end_date - interval '7 days' then null
            else w.nav / w.prev_nav - 1
        end as ret_w
    from
        weekly_lagged as w
),

-- Risk-free reference: weekly change of the compounded €STR index.
benchmark_weekly as (
    select
        d.date_day as week_end_date,
        e.estr_index / lag(e.estr_index) over (order by d.date_day) - 1 as mar_w
    from
        {{ ref('fact_estr_weekly') }} as e
    inner join {{ ref('dim_date') }} as d
        on d.date_key = e.date_key
)

select
    r.class_key,
    r.week_end_date,
    r.nav_date,
    r.nav,
    r.n_days,
    r.n_dormant_days,
    r.n_dormant_days > 0 as is_dormant_week,
    r.ret_w,
    b.mar_w,
    r.ret_w is null and r.prev_week_end_date is not null as is_gap,
    coalesce(r.ret_w = 0, false) as is_stale,
    coalesce(abs(r.ret_w) > {{ var('extreme_return_abs') }}, false) as is_extreme
from
    weekly_returns as r
left join benchmark_weekly as b
    on r.week_end_date = b.week_end_date
