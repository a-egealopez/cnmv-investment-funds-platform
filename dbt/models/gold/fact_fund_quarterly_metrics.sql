with unpivoted as (

-- FONDTRIM publishes 4 quarters per file: the current and the previous three.
-- Each quarter appears in two files (as current/t2 or as t1/t3).
    select
        class_key,
        period,
        'current' as source_slot,
        return_quarter_pct        as return_pct,
        volatility_quarter_pct    as volatility_pct,
        total_expense_ratio_quarter_pct as total_expense_ratio_pct
    from {{ ref('stg_fund_quarterly') }}

    union all

    select
        class_key,
        period,
        't1' as source_slot,
        return_t1_pct,
        volatility_t1_pct,
        total_expense_ratio_t1_pct
    from {{ ref('stg_fund_quarterly') }}

    union all

    select
        class_key,
        period,
        't2' as source_slot,
        return_t2_pct,
        volatility_t2_pct,
        total_expense_ratio_t2_pct
    from {{ ref('stg_fund_quarterly') }}

    union all

    select
        class_key,
        period,
        't3' as source_slot,
        return_t3_pct,
        volatility_t3_pct,
        total_expense_ratio_t3_pct
    from {{ ref('stg_fund_quarterly') }}

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

    -- M5: priority current > t1 > t2 > t3; equal slot broken by most recent file.
    select
        s.*,
        row_number() over (
            partition by s.class_key, s.quarter_end_date
            order by
                case s.source_slot
                    when 'current' then 1
                    when 't1' then 2
                    when 't2' then 3
                    else 4
                end,
                s.period desc
        ) as source_priority
    from quarters as s

)

select
    cl.class_id,
    d.quarter_end_date,
    dd.date_key,
    d.return_pct,
    d.volatility_pct,
    d.total_expense_ratio_pct,
    d.period as source_period,
    d.source_slot,
    d.source_priority
from deduplicated as d
inner join {{ ref('dim_class') }} as cl
    on cl.class_key = d.class_key
inner join {{ ref('dim_date') }} as dd
    on dd.date_day = d.quarter_end_date
where d.source_priority = 1
