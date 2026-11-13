with daily_by_group as (
    select
        d.date_day,
        co.manager_group_id,
        co.manager_group_name,
        sum(f.aum) as aum
    from
        {{ ref('fact_nav_daily') }} as f
    inner join {{ ref('dim_date') }} as d
        on d.date_key = f.date_key
    inner join {{ ref('dim_class') }} as c
        on c.class_id = f.class_id
    inner join {{ ref('dim_compartment') }} as co
        on co.compartment_id = c.compartment_id
    where
        f.aum > 0
        and co.manager_group_id <> -1
    group by
        1, 2, 3
),

manager_group_monthly as (
    -- Month-end AUM: last available day of each month.
    select
        {{ month_key_of('date_day') }} as month_key,
        manager_group_id,
        manager_group_name,
        cast(arg_max(aum, date_day) as double) as aum_managed
    from
        daily_by_group
    group by
        1, 2, 3
),

market_totals as (
    select
        month_key,
        sum(aum_managed) as total_aum_managed
    from
        manager_group_monthly
    group by
        1
),

fee_by_manager_group as (
    -- FONDPATRIMDISVAR reports semiannually (June and December), so fees
    -- exist only in those months and are cumulative from the previous year-end.
    select
        cast(f.date_key // 100 as integer) as month_key,
        c.manager_group_id,
        -- Revenue of the manager = management fee only (the depositary fee is
        -- not the manager's). It is a proxy: gross of retrocessions to
        -- distributors and without costs.
        sum(f.management_fee_revenue) as management_fee_revenue_ytd,
        sum(f.management_fee_revenue_annualized) as management_fee_revenue_annualized,
        -- Average management fee charged, weighted by patrimony.
        sum(f.management_fee_revenue_annualized) / nullif(sum(f.average_patrimony), 0)
            as management_fee_yield_annualized_rate
    from
        {{ ref('fact_fund_period_financials') }} as f
    inner join {{ ref('dim_compartment') }} as c
        on c.compartment_id = f.compartment_id
    where
        c.manager_group_id <> -1
    group by
        1, 2
),

-- Flows by manager group: sum of the compartment flows of the month.
flows_by_manager_group as (
    select
        cast(m.date_key // 100 as integer) as month_key,
        c.manager_group_id,
        sum(m.net_flows) as net_flows,
        sum(m.market_effect) as market_effect,
        sum(m.average_aum) as average_aum
    from
        {{ ref('fact_compartment_monthly') }} as m
    inner join {{ ref('dim_compartment') }} as c
        on c.compartment_id = m.compartment_id
    where
        c.manager_group_id <> -1
    group by
        1, 2
),

monthly as (
    select
        m.month_key,
        m.manager_group_id,
        m.manager_group_name,
        m.aum_managed,
        t.total_aum_managed,
        m.aum_managed / nullif(t.total_aum_managed, 0) as market_share,
        row_number() over (
            partition by m.month_key
            order by m.aum_managed desc
        ) as rank_by_aum,
        count(*) over (partition by m.month_key) as n_manager_groups,
        f.management_fee_revenue_ytd,
        f.management_fee_revenue_annualized,
        f.management_fee_yield_annualized_rate,
        fl.net_flows,
        fl.market_effect,
        fl.average_aum
    from
        manager_group_monthly as m
    inner join market_totals as t
        on t.month_key = m.month_key
    left join fee_by_manager_group as f
        on f.month_key = m.month_key
        and f.manager_group_id = m.manager_group_id
    left join flows_by_manager_group as fl
        on fl.month_key = m.month_key
        and fl.manager_group_id = m.manager_group_id
)

select
    {{ month_key_to_date_key('month_key') }} as date_key,
    manager_group_id,
    rank_by_aum,
    n_manager_groups,
    aum_managed,
    total_aum_managed,
    market_share,
    management_fee_revenue_ytd,
    management_fee_revenue_annualized,
    management_fee_yield_annualized_rate,
    -- Growth split: money added by clients (net flows) vs market moves,
    -- both over the average AUM of the month. Corporate actions are excluded.
    net_flows,
    market_effect,
    net_flows / nullif(average_aum, 0) as net_flow_yield,
    market_effect / nullif(average_aum, 0) as market_growth
from
    monthly
