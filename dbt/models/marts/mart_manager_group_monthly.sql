with manager_group_monthly as (
    -- AUM managed by manager group and month. Each compartment's daily AUM
    -- is attributed to its group and aggregated by month.
    select
        strftime(d.date_day, '%Y-%m') as month,
        g.manager_group_name,
        sum(f.aum) as aum_managed
    from
        {{ ref('fact_nav_daily') }} as f
    inner join {{ ref('dim_date') }} as d
        on d.date_key = f.date_key
    inner join {{ ref('dim_class') }} as c
        on c.class_id = f.class_id
    inner join {{ ref('dim_compartment') }} as co
        on co.compartment_key = c.compartment_key
    inner join {{ ref('dim_fund') }} as g
        on g.fund_key = co.fund_key
    where
        f.aum > 0
        and g.manager_group_name is not null
    group by
        1, 2
),

market_totals as (
    select
        month,
        sum(aum_managed) as total_aum_managed
    from
        manager_group_monthly
    group by
        1
),

fee_by_manager_group as (
    -- Fee revenue in closing months. FONDPATRIMDISVAR reports semiannually
    -- (June and December), so fees exist only in those months.
    select
        substr(f.period, 1, 4) || '-' || substr(f.period, 5, 2) as month,
        g.manager_group_name,
        sum(f.fee_revenue_proxy) as fee_revenue
    from
        {{ ref('fact_fund_period_financials') }} as f
    inner join {{ ref('dim_compartment') }} as c
        on c.compartment_id = f.compartment_id
    inner join {{ ref('dim_fund') }} as g
        on g.fund_key = c.fund_key
    where
        g.manager_group_name is not null
    group by
        1, 2
),

-- Market share within the month. It explains HHI: a high weight indicates
-- a large group.
ranked as (
    select
        m.month,
        m.manager_group_name,
        m.aum_managed,
        t.total_aum_managed,
        m.aum_managed / nullif(t.total_aum_managed, 0) as market_share,
        row_number() over (partition by m.month order by m.aum_managed desc) as rank_by_aum,
        count(*) over (partition by m.month) as n_manager_groups
    from
        manager_group_monthly as m
    inner join market_totals as t
        on t.month = m.month
)

select
    '{{ var("as_of_period") }}' as as_of_period,
    r.month,
    r.manager_group_name,
    r.rank_by_aum,
    r.n_manager_groups,
    r.aum_managed,
    r.total_aum_managed,
    r.market_share,
    f.fee_revenue,
    f.fee_revenue / nullif(r.total_aum_managed, 0) as fee_revenue_per_aum
from
    ranked as r
left join fee_by_manager_group as f
    on f.month = r.month
    and f.manager_group_name = r.manager_group_name
