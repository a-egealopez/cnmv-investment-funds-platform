with monthly_flows as (
    -- Monthly flow per compartment: the bridge is at class level and is
    -- aggregated here.
    select
        c.compartment_key,
        strftime(f.value_date, '%Y-%m') as month,
        sum(f.net_flows)                       as net_flows,
        sum(f.market_effect)                   as market_effect,
        sum(f.delta_aum)                       as delta_aum,
        max(f.aum)                             as aum,
        avg(f.aum)                             as average_aum,
        sum(case when f.is_capital_change then 1 else 0 end) as n_capital_changes,
        sum(case when f.is_distribution then 1 else 0 end)    as n_distributions,
        sum(case when f.is_jump then 1 else 0 end)            as n_jumps
    from
        {{ ref('int_fund_aum_bridge') }} as f
    inner join {{ ref('dim_class') }} as c
        on c.class_key = f.class_key
    group by
        1, 2
),

monthly_holders as (
    -- Holders at month end, used to measure retention.
    select
        c.compartment_key,
        strftime(d.date_day, '%Y-%m') as month,
        max(f.holders) as holders
    from
        {{ ref('fact_nav_daily') }} as f
    inner join {{ ref('dim_class') }} as c
        on c.class_id = f.class_id
    inner join {{ ref('dim_date') }} as d
        on d.date_key = f.date_key
    group by
        1, 2
),

holders_with_previous as (
    select
        h.compartment_key,
        h.month,
        h.holders,
        lag(h.holders) over (
            partition by h.compartment_key
            order by h.month
        ) as previous_holders,
        lag(h.holders) over (
            partition by h.compartment_key
            order by h.month
            rows between 2 preceding and 1 preceding
        ) as holders_two_months_ago
    from
        monthly_holders as h
),

-- FONDPATRIMDISVAR fees: compartment-level, semiannual. The fee is assigned
-- to the closing month (June and December); other months stay null.
fees as (
    select
        compartment_id,
        substr(period, 1, 4) || '-' || substr(period, 5, 2) as month,
        net_subscriptions_redemptions_pct,
        total_patrimony,
        net_return_pct,
        core_fee_yield_pct,
        other_expense_yield_pct,
        expense_ratio_pct,
        income_yield_pct,
        core_fee_share,
        fee_revenue_proxy
    from
        {{ ref('fact_fund_period_financials') }}
),

monthly_metrics as (
    select
        f.compartment_key,
        f.month,
        f.aum,
        f.average_aum,
        f.net_flows,
        f.market_effect,
        f.delta_aum,

        f.net_flows / nullif(f.average_aum, 0) as net_flow_yield,
        f.market_effect / nullif(f.average_aum, 0) as market_growth,
        f.net_flows / nullif(f.average_aum, 0) as organic_growth,
        f.delta_aum / nullif(f.average_aum, 0) as total_growth,
        least(f.net_flows, 0) / nullif(f.average_aum, 0) as outflow_share,

        case
            when hp.previous_holders > 0 then hp.holders / hp.previous_holders
        end as participant_retention,
        case
            when hp.holders_two_months_ago > 0 then hp.holders / hp.holders_two_months_ago
        end as participant_retention_2m,
        f.aum / nullif(lag(f.aum) over (
            partition by f.compartment_key order by f.month
        ), 0) as aum_retention,

        fm.net_subscriptions_redemptions_pct,
        fm.total_patrimony,
        fm.net_return_pct,
        fm.core_fee_yield_pct,
        fm.other_expense_yield_pct,
        fm.expense_ratio_pct,
        fm.income_yield_pct,
        fm.core_fee_share,
        fm.fee_revenue_proxy,

        f.n_capital_changes,
        f.n_distributions,
        f.n_jumps

    from
        monthly_flows as f
    inner join holders_with_previous as hp
        on hp.compartment_key = f.compartment_key
        and hp.month = f.month
    left join fees as fm
        on fm.compartment_id = f.compartment_key
        and fm.month = f.month
)

select
    '{{ var("as_of_period") }}' as as_of_period,
    p.compartment_id as compartment_id,
    m.month,
    m.aum,
    m.average_aum,
    m.net_flows,
    m.market_effect,
    m.delta_aum,
    m.net_flow_yield,
    m.market_growth,
    m.organic_growth,
    m.total_growth,
    m.outflow_share,
    m.participant_retention,
    m.participant_retention_2m,
    m.aum_retention,
    m.net_subscriptions_redemptions_pct,
    m.total_patrimony,
    m.net_return_pct,
    m.core_fee_yield_pct,
    m.other_expense_yield_pct,
    m.expense_ratio_pct,
    m.income_yield_pct,
    m.core_fee_share,
    m.fee_revenue_proxy,
    m.n_capital_changes,
    m.n_distributions,
    m.n_jumps
from
    monthly_metrics as m
inner join {{ ref('dim_compartment') }} as p
    on p.compartment_key = m.compartment_key
