with unpivoted as (

-- FONDTRIM publishes 4 quarters per file: the current and the previous three.
-- Each quarter appears in two files (as current/t2 or as t1/t3).
    select
        class_key,
        period,
        'current' as source_slot,
        return_quarter_rate        as return_rate,
        volatility_quarter_rate    as volatility_rate,
        total_expense_ratio_quarter_rate as total_expense_ratio_rate
    from {{ ref('stg_fund_quarterly') }}
    where period <= {{ current_as_of_period() }}

    union all

    select
        class_key,
        period,
        't1' as source_slot,
        return_t1_rate,
        volatility_t1_rate,
        total_expense_ratio_t1_rate
    from {{ ref('stg_fund_quarterly') }}
    where period <= {{ current_as_of_period() }}

    union all

    select
        class_key,
        period,
        't2' as source_slot,
        return_t2_rate,
        volatility_t2_rate,
        total_expense_ratio_t2_rate
    from {{ ref('stg_fund_quarterly') }}
    where period <= {{ current_as_of_period() }}

    union all

    select
        class_key,
        period,
        't3' as source_slot,
        return_t3_rate,
        volatility_t3_rate,
        total_expense_ratio_t3_rate
    from {{ ref('stg_fund_quarterly') }}
    where period <= {{ current_as_of_period() }}

),

in_scope as (

-- M6: 2022 quarters are outside the dimension calendar.
-- quarter_end_date is the quarter end (31/03, 30/06, 30/09, 31/12), not the start.
    select
        q.*,
        cast(
            cast(substr(q.period, 1, 4) || '-' || substr(q.period, 5, 2) || '-01' as date)
            - case q.source_slot
                when 'current' then interval '0 months'
                when 't1' then interval '3 months'
                when 't2' then interval '6 months'
                else interval '9 months'
              end
            as date
        ) as quarter_start
    from unpivoted as q

),

quarters as (

    -- quarter_start is the first day of the quarter; the end is its last day.
    select
        s.*,
        cast(last_day(s.quarter_start) as date) as quarter_end_date
    from in_scope as s
    where s.quarter_start >= (select min(date_day) from {{ ref('dim_date') }})

),

deduplicated as (

    -- Priority: most recent source file (period desc), then slot closeness current>t1>t2>t3.
    -- Values may differ across slots for ~1.5k keys; recency prefers latest reported figure.
    select
        s.*,
        row_number() over (
            partition by s.class_key, s.quarter_end_date
            order by
                s.period desc,
                case s.source_slot
                    when 'current' then 1
                    when 't1' then 2
                    when 't2' then 3
                    else 4
                end
        ) as rn
    from quarters as s
    where s.return_rate is not null
       or s.volatility_rate is not null
       or s.total_expense_ratio_rate is not null
)

select
    cl.class_id,
    dd.date_key,
    d.return_rate,
    d.volatility_rate,
    d.total_expense_ratio_rate
from deduplicated as d
inner join {{ ref('dim_class') }} as cl
    on cl.class_key = d.class_key
inner join {{ ref('dim_date') }} as dd
    on dd.date_day = d.quarter_end_date
where d.rn = 1
