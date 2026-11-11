{% macro analysis_window() %}
{#
    Analysis window: as_of_date and window_start.
    as_of_date = last date with data for as_of_period or earlier.
    window_start = as_of_date minus window_months months, +1 day
    (so the window contains exactly window_months full months).
#}
select
    max(value_date) as as_of_date,
    cast(
        max(value_date)
            - cast({{ var('window_months', 36) }} as integer) * interval '1 month'
            + interval '1 day'
        as date
    ) as window_start
from
    {{ ref('stg_fund_nav_daily') }}
where
    period <= cast('{{ var('as_of_period') }}' as varchar)
{% endmacro %}
