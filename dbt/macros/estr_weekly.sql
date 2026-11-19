{% macro estr_weekly(horizon='base') %}
{#
    Weekly €STR compounded index (series .CI) over the analysis window of a
    metric horizon: the last published value on or before each week end.
    fact_estr_weekly exposes the base horizon; the long horizon is used inline
    by weekly_nav_returns('long'), so the Gold fact keeps its 3-year grain.
#}
with bounds as (
    {{ analysis_window(horizon) }}
),

weeks as (
    select distinct d.week_end_date
    from {{ ref('dim_date') }} as d
    cross join bounds as b
    where d.week_end_date >= b.window_start
      and d.week_start_date <= b.as_of_date
),

weekly_index as (
    -- Last published index value on or before the week end (Sunday), and never
    -- after the cut-off: the last week can end after as_of_date (a Monday cut-off
    -- leaves six days of it in the future), and the ECB data may already cover them.
    select
        w.week_end_date,
        i.value_date as estr_date,
        cast(i.series_value as double) as estr_index
    from weeks as w
    asof join (
        select value_date, series_value
        from {{ ref('stg_estr_daily') }}
        where
            series = '{{ var("estr_series") }}'
            and value_date <= (select as_of_date from bounds)
    ) as i
        on w.week_end_date >= i.value_date
)

select
    d.date_key,
    w.estr_date,
    w.estr_index
from weekly_index as w
inner join {{ ref('dim_date') }} as d
    on d.date_day = w.week_end_date
where w.estr_index is not null
{% endmacro %}
