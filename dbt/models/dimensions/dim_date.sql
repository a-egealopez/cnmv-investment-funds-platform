-- Calendar covering whole quarters at the start and whole months (and the last
-- ISO week) at the end: the first day of every quarter with data (quarterly
-- anomalies), the last day of every month (monthly facts) and the Sunday of every
-- week (weekly series) always exist.
with bounds as (
    select
        cast(date_trunc('quarter', min(value_date)) as date) as min_date,
        -- End of the last month, or of its last ISO week if that ends later: the
        -- weekly series are keyed by the Sunday that closes each week.
        cast(greatest(
            last_day(max(value_date)),
            cast(date_trunc('week', max(value_date)) + interval 6 day as date)
        ) as date) as max_date
    from
        {{ ref('stg_fund_nav_daily') }}
    where
        period <= {{ current_as_of_period() }}
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
    cast(strftime(date_day, '%Y%m') as integer) as month_key,
    cast(last_day(date_day) as date) as month_end_date,
    cast(year(date_day) as smallint) as year,
    cast(quarter(date_day) as tinyint) as quarter,
    cast(month(date_day) as tinyint) as month,
    strftime(date_day, '%B') as month_name,
    strftime(date_day, '%b %Y') as month_label,
    cast(weekofyear(date_day) as tinyint) as iso_week,
    cast(date_trunc('week', date_day) as date) as week_start_date,
    cast(date_trunc('week', date_day) + interval 6 day as date) as week_end_date,
    cast(isodow(date_day) as tinyint) as iso_dow,
    isodow(date_day) in (6, 7) as is_weekend,
    date_day = cast(last_day(date_day) as date) as is_month_end,
    -- FONDPATRIMDISVAR closings: June and December (semiannual).
    month(date_day) in (6, 12) as is_closing_month
from
    calendar
