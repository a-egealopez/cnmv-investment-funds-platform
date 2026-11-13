with flows_raw as (
    -- Monthly flow per compartment: the bridge is at class level and is
    -- aggregated here.
    select
        c.compartment_key,
        {{ month_key_of('f.value_date') }} as month_key,
        -- Days with a capital change or a price jump are corporate actions
        -- (merger, class change, decapitalization), not cash flows or market
        -- moves. They are excluded from the three measures so that
        -- net_flows + market_effect = delta_aum still holds, and their AUM
        -- effect is reported separately.
        sum(case when f.is_capital_change or f.is_jump then 0 else f.net_flows end)     as net_flows,
        sum(case when f.is_capital_change or f.is_jump then 0 else f.market_effect end) as market_effect,
        cast(sum(case when f.is_capital_change or f.is_jump then 0 else f.delta_aum end) as double) as delta_aum,
        cast(sum(case when f.is_capital_change or f.is_jump then f.delta_aum else 0 end) as double) as corporate_action_delta_aum,
        cast(sum(case when f.is_capital_change then 1 else 0 end) as bigint) as n_capital_changes,
        cast(sum(case when f.is_jump then 1 else 0 end) as bigint)           as n_jumps
    from
        {{ ref('int_fund_aum_bridge') }} as f
    inner join {{ ref('dim_class') }} as c
        on c.class_key = f.class_key
    group by
        1, 2
),

daily_aum as (
    select
        c.compartment_key,
        f.value_date,
        sum(f.aum) as aum
    from {{ ref('int_fund_aum_bridge') }} as f
    inner join {{ ref('dim_class') }} as c
        on c.class_key = f.class_key
    group by 1, 2
),

monthly_aum as (
    select
        compartment_key,
        {{ month_key_of('value_date') }} as month_key,
        arg_max(aum, value_date) as aum,
        avg(aum) as average_aum
    from daily_aum
    group by 1, 2
),

monthly_flows as (
    select
        r.*,
        a.aum,
        a.average_aum
    from flows_raw as r
    inner join monthly_aum as a
        on a.compartment_key = r.compartment_key
        and a.month_key = r.month_key
),

-- Holders at the last reported day of the month in each class.
class_holders_month_end as (
    select
        c.compartment_key,
        c.class_key,
        {{ month_key_of('d.date_day') }} as month_key,
        arg_max(f.holders, d.date_day) filter (where f.holders is not null) as holders
    from
        {{ ref('fact_nav_daily') }} as f
    inner join {{ ref('dim_class') }} as c
        on c.class_id = f.class_id
    inner join {{ ref('dim_date') }} as d
        on d.date_key = f.date_key
    group by
        1, 2, 3
),

-- Compartment holders = sum over classes. A participant holding two classes
-- counts twice, so this is an upper bound.
monthly_holders as (
    select
        compartment_key,
        month_key,
        sum(holders) as holders
    from
        class_holders_month_end
    group by
        1, 2
),

holders_with_previous as (
    select
        h.compartment_key,
        h.month_key,
        h.holders,
        {{ month_index('h.month_key') }} as month_index,
        lag({{ month_index('h.month_key') }}) over (
            partition by h.compartment_key
            order by h.month_key
        ) as previous_month_index,
        lag({{ month_index('h.month_key') }}, 2) over (
            partition by h.compartment_key
            order by h.month_key
        ) as month_index_two_back,
        lag(h.holders) over (
            partition by h.compartment_key
            order by h.month_key
        ) as previous_holders,
        lag(h.holders, 2) over (
            partition by h.compartment_key
            order by h.month_key
        ) as holders_two_months_ago
    from
        monthly_holders as h
),

monthly_metrics as (
    select
        f.compartment_key,
        f.month_key,
        f.aum,
        f.average_aum,
        f.net_flows,
        f.market_effect,
        f.delta_aum,
        f.corporate_action_delta_aum,

        f.net_flows / nullif(f.average_aum, 0) as net_flow_yield,
        f.market_effect / nullif(f.average_aum, 0) as market_growth,        
        f.delta_aum / nullif(f.average_aum, 0) as total_growth,
        least(f.net_flows, 0) / nullif(f.average_aum, 0) as outflow_share,

        -- Retention ratios only compare consecutive months: a missing month
        -- would otherwise stretch the ratio over a longer period.
        case
            when hp.previous_holders > 0 and hp.month_index - hp.previous_month_index = 1
                then hp.holders / hp.previous_holders
        end as participant_retention,
        case
            when hp.holders_two_months_ago > 0 and hp.month_index - hp.month_index_two_back = 2
                then hp.holders / hp.holders_two_months_ago
        end as participant_retention_2m,
        case
            when {{ month_index('f.month_key') }} - lag({{ month_index('f.month_key') }}) over (
                    partition by f.compartment_key order by f.month_key
                 ) = 1
                then f.aum / nullif(lag(f.aum) over (
                    partition by f.compartment_key order by f.month_key
                ), 0)
        end as aum_retention,

        f.n_capital_changes,
        f.n_jumps

    from
        monthly_flows as f
    inner join holders_with_previous as hp
        on hp.compartment_key = f.compartment_key
        and hp.month_key = f.month_key
)

select
    p.compartment_id,
    {{ month_key_to_date_key('m.month_key') }} as date_key,
    m.aum,
    m.average_aum,
    m.net_flows,
    m.market_effect,
    m.delta_aum,
    m.corporate_action_delta_aum,
    m.net_flow_yield,
    m.market_growth,
    m.total_growth,
    m.outflow_share,
    m.participant_retention,
    m.participant_retention_2m,
    m.aum_retention,
    -- Flags to filter outliers before charting. They do not remove rows.
    coalesce(
        abs(m.net_flow_yield) > {{ var('max_abs_flow_yield') }}, false
    ) as is_flow_outlier,
    m.n_capital_changes,
    m.n_jumps
from
    monthly_metrics as m
inner join {{ ref('dim_compartment') }} as p
    on p.compartment_key = m.compartment_key

