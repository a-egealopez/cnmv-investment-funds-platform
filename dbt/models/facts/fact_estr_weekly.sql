-- Weekly €STR compounded index (series .CI), used as risk-free reference (e.g. Sortino).
-- Grain: week_end_date. Rebasing to 100 is done in BI/DAX for the selected window.
with bounds as (
    {{ analysis_window() }}
),

weeks as (
    select distinct d.week_end_date
    from {{ ref('dim_date') }} as d
    cross join bounds as b
    where d.week_end_date >= b.window_start
      and d.week_start_date <= b.as_of_date
),

weekly_index as (
    -- Last published index value on or before the week end (Sunday).
    select
        w.week_end_date,
        i.value_date as estr_date,
        cast(i.series_value as double) as estr_index
    from weeks as w
    asof join (
        select value_date, series_value
        from {{ ref('stg_estr_daily') }}
        where series = '{{ var("estr_series") }}'
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
