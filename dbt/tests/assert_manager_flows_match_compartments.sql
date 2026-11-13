-- Net flows by manager group must add up to the compartment flows of the month
-- (no compartment has an unknown manager group, so nothing is left out).
with by_group as (
    select date_key, sum(net_flows) as group_flows
    from {{ ref('fact_manager_group_monthly') }}
    group by date_key
),

by_compartment as (
    select m.date_key, sum(m.net_flows) as compartment_flows
    from {{ ref('fact_compartment_monthly') }} as m
    inner join {{ ref('dim_compartment') }} as c
        on c.compartment_id = m.compartment_id
    where c.manager_group_id <> -1
    group by m.date_key
)

select
    g.date_key,
    g.group_flows,
    c.compartment_flows
from by_group as g
inner join by_compartment as c
    on c.date_key = g.date_key
where abs(g.group_flows - c.compartment_flows) > greatest(1, 1e-9 * abs(c.compartment_flows))
