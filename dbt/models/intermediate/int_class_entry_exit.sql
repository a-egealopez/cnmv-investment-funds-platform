-- Assets that enter or leave the market because a class starts or stops reporting.
--
-- The daily bridge only measures flows between two observations of the same class,
-- so a class that closes, or is merged into another fund, just stops appearing: its
-- assets never show as an outflow, while the fund that absorbs them records them as
-- subscriptions. Summing flows across funds then overstates new money. This model
-- books those movements explicitly:
--   entry: first observation of a class that starts inside the window, +aum that day.
--   exit:  last observation of a class that stops before the cut-off month,
--          -aum that day, booked the day after (the day it is no longer there).
-- A class already reporting at the window start is not an entry, and one still
-- reporting in the cut-off month is not an exit. A class that misses a month and comes
-- back is neither: the bridge already spans the gap.

with bounds as (
    {{ analysis_window() }}
),

class_span as (
    select
        class_key,
        arg_min(prev_value_date, value_date) as first_date,
        arg_min(aum - delta_aum, value_date) as first_aum,
        max(value_date) as last_date,
        arg_max(aum, value_date) as last_aum
    from
        {{ ref('int_fund_aum_bridge') }}
    group by
        class_key
),

entries as (
    select
        s.class_key,
        s.first_date as value_date,
        'entry' as event,
        cast(s.first_aum as double) as entry_exit_flows
    from
        class_span as s
    cross join bounds as b
    where
        {{ month_key_of('s.first_date') }} > {{ month_key_of('b.window_start') }}
),

exits as (
    select
        s.class_key,
        cast(s.last_date + interval 1 day as date) as value_date,
        'exit' as event,
        -cast(s.last_aum as double) as entry_exit_flows
    from
        class_span as s
    cross join bounds as b
    where
        {{ month_key_of('s.last_date') }} < {{ month_key_of('b.as_of_date') }}
)

select * from entries
union all
select * from exits
