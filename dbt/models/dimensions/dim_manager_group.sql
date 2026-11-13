select
    cast(row_number() over (order by manager_group_name) as bigint) as manager_group_id,
    manager_group_name
from (
    select distinct
        manager_group_name
    from
        {{ ref('stg_fund_metadata') }}
    where
        manager_group_name is not null
        and period <= {{ current_as_of_period() }}
)

union all

-- Unknown member: fund without manager group.
select
    cast(-1 as bigint) as manager_group_id,
    'Desconocido' as manager_group_name
