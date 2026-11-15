-- Run context: the single place where the cut-off of the run is defined.
-- Every other model reads it through ref('meta_run') (directly, or through the
-- current_as_of_period() and analysis_window() macros), never through var().
--
-- var as_of_period: 'latest' (default) or an explicit YYYYMM (backfills).
{% set requested = var('as_of_period', 'latest') | string %}
{% if requested != 'latest' and not modules.re.match('^[0-9]{6}$', requested) %}
    {{ exceptions.raise_compiler_error("as_of_period must be 'latest' or YYYYMM, got: " ~ requested) }}
{% endif %}

with silver as (
    select max(period) as silver_max_period
    from {{ ref('stg_fund_nav_daily') }}
),

resolved as (
    select
        '{{ requested }}'::varchar as requested_period,
        silver_max_period,
        case
            when '{{ requested }}' = 'latest' then silver_max_period
            else '{{ requested }}'
        end::varchar as as_of_period
    from silver
),

bounds as (
    -- as_of_date: last NAV date available up to the cut-off period.
    select
        r.*,
        (
            select max(n.value_date)
            from {{ ref('stg_fund_nav_daily') }} as n
            where n.period <= r.as_of_period
        ) as as_of_date
    from resolved as r
)

select
    as_of_period,
    cast(
        strptime(as_of_period || '01', '%Y%m%d') as date
    ) as as_of_month_start_date,
    as_of_date,
    -- The window contains exactly window_months full months.
    cast(
        as_of_date
        - cast({{ var('window_months') }} as integer) * interval '1 month'
        + interval '1 day'
        as date
    ) as window_start,
    cast({{ var('window_months') }} as integer) as window_months,
    -- Long window for the 5-year metrics, same rule with window_months_long.
    cast(
        as_of_date
        - cast({{ var('window_months_long') }} as integer) * interval '1 month'
        + interval '1 day'
        as date
    ) as window_start_long,
    cast({{ var('window_months_long') }} as integer) as window_months_long,
    requested_period,
    silver_max_period,
    current_timestamp as built_at
from bounds
