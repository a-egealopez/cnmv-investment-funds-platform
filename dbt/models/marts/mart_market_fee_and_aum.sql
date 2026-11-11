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

fee_shares as (
    select
        month,
        manager_group_name,
        fee_revenue,
        fee_revenue / nullif(sum(fee_revenue) over (partition by month), 0) as fee_share
    from
        fee_by_manager_group
),

fee_concentration as (
    select
        month,
        sum(fee_revenue) as total_fee_revenue,
        sum(power(fee_share, 2)) as hhi_fee,
        1.0 / nullif(sum(power(fee_share, 2)), 0) as effective_n_groups,
        count(*) as n_manager_groups
    from
        fee_shares
    group by
        1
),

top_five as (
    select
        month,
        sum(fee_revenue) as top5_fee_revenue
    from
        (
            select
                month,
                fee_revenue,
                row_number() over (
                    partition by month
                    order by fee_revenue desc
                ) as rn
            from
                fee_by_manager_group
        )
    where
        rn <= 5
    group by
        1
),

market_monthly as (
    select
        month,
        sum(aum_managed) as total_aum_managed,
        count(*) as n_manager_groups_active
    from
        manager_group_monthly
    group by
        1
)

select
    '{{ var("as_of_period") }}' as as_of_period,
    m.month,
    m.total_aum_managed,
    m.n_manager_groups_active,
    fc.total_fee_revenue,
    fc.hhi_fee,
    fc.effective_n_groups,
    fc.n_manager_groups,
    case
        when fc.total_fee_revenue > 0 then t5.top5_fee_revenue / fc.total_fee_revenue
    end as top5_fee_share
from
    market_monthly as m
left join fee_concentration as fc
    on fc.month = m.month
left join top_five as t5
    on t5.month = m.month
