-- Manager group of each compartment in each month, as FONDREGISTRO reported it then.
--
-- dim_compartment keeps the last known group (Type 1), which is right for "who
-- manages this fund today" but wrong for history: applied to every month, it moves
-- funds to their current owner before the takeover happened (Bankia's funds would
-- count as CaixaBank's in 2020, a year before the merger). Facts that track groups
-- over time (market share, concentration, flows by group) join this model instead.
-- FONDREGISTRO is monthly and reports one group per compartment and month.

select
    m.compartment_key,
    cast(m.period as integer) as month_key,
    max(m.manager_group_name) as manager_group_name,
    coalesce(max(g.manager_group_id), -1) as manager_group_id
from
    {{ ref('stg_fund_metadata') }} as m
left join {{ ref('dim_manager_group') }} as g
    on g.manager_group_name = m.manager_group_name
where
    m.period <= {{ current_as_of_period() }}
group by
    m.compartment_key,
    m.period
