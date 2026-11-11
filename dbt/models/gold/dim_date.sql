with bounds as (
    select
        min(value_date) as min_date,
        max(value_date) as max_date
    from
        {{ ref('stg_fund_nav_daily') }}
),

calendar as (
    select
        cast(unnest(generate_series(min_date, max_date, interval 1 day)) as date)
            as date_day
    from
        bounds
)

select
    date_day,
    cast(strftime(date_day, '%Y%m%d') as integer)
        as date_key,
    cast(year(date_day) as smallint) as year,
    cast(quarter(date_day) as tinyint) as quarter,
    cast(month(date_day) as tinyint) as month,
    cast(weekofyear(date_day) as tinyint) as iso_week,
    cast(date_trunc('week', date_day) as date) as week_start_date,
    cast(date_trunc('week', date_day) + interval 6 day as date) as week_end_date,
    cast(isodow(date_day) as tinyint) as iso_dow,
    isodow(date_day) in (6, 7) as is_weekend
from
    calendar
