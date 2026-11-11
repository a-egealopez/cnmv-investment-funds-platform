with bounds as (
    select
        b.*,
        ceil(date_diff('day', b.window_start, b.as_of_date) / 7.0)
            as n_weeks_expected
    from
        ({{ analysis_window() }}) as b
),

weekly_lagged as (
    select
        w.*,
        lag(w.week_end_date) over by_class as prev_week_end_date,
        date_diff(
            'day',
            lag(w.week_end_date) over by_class,
            w.week_end_date
        ) as gap_days
    from
        {{ ref('int_weekly_nav_returns') }} as w
    window by_class as (partition by class_key order by week_end_date)
),

class_span as (
    select
        class_key,
        min(week_end_date) filter (where nav is not null) as first_week,
        max(week_end_date) filter (where nav is not null) as last_week
    from
        weekly_lagged
    group by
        class_key
),

weekly_stats as (
    select
        w.class_key,
        s.first_week,
        s.last_week,

        count(*) filter (where w.nav is not null)          as n_weeks,
        count(w.ret_w)                                      as n_returns,
        sum(case when w.is_stale then 1 else 0 end)          as n_stale,
        sum(case when w.is_gap then 1 else 0 end)            as n_gap,
        sum(case when w.is_dormant_week then 1 else 0 end)   as n_dormant_weeks,
        sum(case when w.is_extreme then 1 else 0 end)        as n_extreme,
        max(w.gap_days)                                      as max_gap_days,

        stddev_samp(w.ret_w) * sqrt(52)                     as vol,
        avg(w.ret_w - w.mar_w) * 52                         as mean_excess,
        sqrt(avg(power(least(w.ret_w - w.mar_w, 0), 2))) * sqrt(52) as downside_dev,

        -- 52-week return: current NAV vs. NAV 52 weeks ago.
        max(case when w.week_end_date = s.last_week
                 then w.nav end)
            / nullif(max(case when w.week_end_date = s.last_week - interval '52 weeks'
                            then w.nav end), 0) - 1        as ret_1y,

        -- CAGR: end-of-window NAV vs. start-of-window NAV, annualized by days.
        power(
            max(case when w.week_end_date = s.last_week then w.nav end)
            / nullif(max(case when w.week_end_date = s.first_week then w.nav end), 0),
            365.0 / nullif(date_diff('day', s.first_week, s.last_week), 0)
        ) - 1                                             as cagr_3y

    from
        weekly_lagged as w
    inner join class_span as s
        on s.class_key = w.class_key
    group by
        w.class_key, s.first_week, s.last_week
),

with_drawdown as (
    select
        class_key,
        max(drawdown) as max_drawdown
    from
        {{ ref('int_daily_drawdown') }}
    group by
        class_key
),

derived_metrics as (
    select
        s.*,
        d.max_drawdown,
        b.n_weeks_expected,
        b.window_start,
        b.as_of_date,
        s.n_weeks::double / b.n_weeks_expected as coverage_ratio,
        s.n_stale::double / nullif(s.n_returns, 0) as stale_share,
        s.n_gap::double / nullif(s.n_weeks, 0) as gap_share,

        case
            when s.mean_excess is null or s.downside_dev is null then null
            when s.downside_dev < {{ var('min_downside_dev', 0.001) }} and s.mean_excess > 0
                then 'no_downside'
            when s.vol = 0 and s.mean_excess <= 0 then 'stagnant'
            else 'ok'
        end as sortino_status,

        case
            when s.vol is null then null
            when s.vol < 0.005 then 1
            when s.vol < 0.02  then 2
            when s.vol < 0.05  then 3
            when s.vol < 0.10  then 4
            when s.vol < 0.15  then 5
            when s.vol < 0.25  then 6
            else 7
        end as srri_like_class

    from
        weekly_stats as s
    cross join bounds as b
    left join with_drawdown as d
        on d.class_key = s.class_key
),

-- Quarantine reason by priority: the most severe wins.
-- short_history is not quarantine: the class appears in the panorama without 36-month metrics.
class_quality as (
    select
        m.*,
        case
            when m.first_week > m.window_start + {{ var('max_edge_gap_weeks', 1) }} * interval '7 days'
                then 'short_history'
            when m.n_dormant_weeks > 0 then 'dormant'
            when m.n_extreme > 0 then 'extreme_return'
            when m.max_gap_days > ({{ var('max_gap_weeks', 1) }} + 1) * 7 then 'gap_gt_max'
            when m.coverage_ratio < {{ var('min_coverage', 0.90) }} then 'coverage_lt_min'
            when m.last_week < m.as_of_date - {{ var('max_edge_gap_weeks', 1) }} * interval '7 days'
                then 'stale_end'
            else null
        end as class_status_reason
    from
        derived_metrics as m
)

select
    q.class_key,
    q.first_week,
    q.last_week,
    q.n_weeks,
    q.n_weeks_expected,
    q.n_returns,
    q.n_stale,
    q.n_gap,
    q.n_dormant_weeks,
    q.n_extreme,
    q.coverage_ratio,
    q.stale_share,
    q.gap_share,
    q.ret_1y,
    q.cagr_3y,
    q.vol,
    q.mean_excess,
    q.downside_dev,
    q.mean_excess / nullif(q.downside_dev, 0) as sortino,
    q.sortino_status,
    q.max_drawdown,
    q.srri_like_class,
    case
        when q.class_status_reason = 'short_history' then 'short_history'
        when q.class_status_reason is not null then 'quarantined'
        else 'eligible'
    end as class_status,
    q.class_status_reason
from
    class_quality as q
