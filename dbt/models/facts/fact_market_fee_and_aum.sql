with fee_shares as (
    select
        date_key,
        management_fee_revenue_ytd,
        management_fee_revenue_annualized,
        management_fee_revenue_ytd / nullif(
            sum(management_fee_revenue_ytd) over (partition by date_key), 0
        ) as fee_share
    from
        {{ ref('fact_manager_group_monthly') }}
    where
        management_fee_revenue_ytd is not null
),

fee_concentration as (
    select
        date_key,
        sum(management_fee_revenue_ytd) as total_management_fee_revenue_ytd,
        sum(management_fee_revenue_annualized) as total_management_fee_revenue_annualized,
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
        date_key,
        sum(management_fee_revenue_ytd) as top5_management_fee_revenue_ytd
    from
        (
            select
                date_key,
                management_fee_revenue_ytd,
                row_number() over (
                    partition by date_key
                    order by management_fee_revenue_ytd desc
                ) as rn
            from
                {{ ref('fact_manager_group_monthly') }}
            where
                management_fee_revenue_ytd is not null
        )
    where
        rn <= 5
    group by
        1
),

market_monthly as (
    select
        date_key,
        max(total_aum_managed) as total_aum_managed,
        count(*) as n_manager_groups_active
    from
        {{ ref('fact_manager_group_monthly') }}
    group by
        1
)

select
    m.date_key,
    m.total_aum_managed,
    m.n_manager_groups_active,
    fc.total_management_fee_revenue_ytd,
    fc.total_management_fee_revenue_annualized,
    fc.hhi_fee,
    fc.effective_n_groups,
    fc.n_manager_groups,
    case
        when fc.total_management_fee_revenue_ytd > 0
            then t5.top5_management_fee_revenue_ytd / fc.total_management_fee_revenue_ytd
    end as top5_fee_share
from
    market_monthly as m
left join fee_concentration as fc
    on fc.date_key = m.date_key
left join top_five as t5
    on t5.date_key = m.date_key
