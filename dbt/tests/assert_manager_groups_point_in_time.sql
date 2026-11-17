-- Manager group history must be point in time: each month, a group must hold at least
-- the month-end assets of the classes that FONDREGISTRO lists under it that same month.
-- If groups were taken from dim_compartment (the current owner), a group that was later
-- taken over would lose its past: Bankia had EUR 20bn in January 2020, but its funds
-- counted as CaixaBank's. That version fell short in 123 group-months; the
-- point-in-time attribution matches exactly. Tolerance 1 % for float sums.
with month_end_classes as (
    -- Assets of the classes that report on the last day of the month with data, the
    -- day the fact measures month-end assets on (a class that does not report that day
    -- is missing from both sides)
    select
        c.class_key,
        d.month_key,
        f.aum
    from {{ ref('fact_nav_daily') }} as f
    inner join {{ ref('dim_date') }} as d
        on d.date_key = f.date_key
    inner join {{ ref('dim_class') }} as c
        on c.class_id = f.class_id
    qualify d.date_day = max(d.date_day) over (partition by d.month_key)
),

listed as (
    -- Those assets added up by the group in that same month's FONDREGISTRO
    select
        e.month_key,
        g.manager_group_id,
        sum(e.aum) as listed_aum
    from month_end_classes as e
    inner join {{ ref('stg_fund_metadata') }} as m
        on m.class_key = e.class_key
        and cast(m.period as integer) = e.month_key
    inner join {{ ref('dim_manager_group') }} as g
        on g.manager_group_name = m.manager_group_name
    where
        e.aum > 0
        and m.period <= {{ current_as_of_period() }}
    group by 1, 2
)

select
    l.month_key,
    l.manager_group_id,
    l.listed_aum,
    f.aum_managed
from listed as l
left join {{ ref('fact_manager_group_monthly') }} as f
    on f.date_key // 100 = l.month_key
    and f.manager_group_id = l.manager_group_id
where coalesce(f.aum_managed, 0) < 0.99 * l.listed_aum
