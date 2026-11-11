with latest_metadata as (
    {{ latest_by_period(
        relation=ref('stg_fund_metadata'),
        key='fund_key',
        as_of_period=var('as_of_period')
    ) }}
)

select
    fund_key,
    fund_type,
    registration_number,
    fund_name,
    is_etf,
    manager_name,
    manager_registration_number,
    manager_type,
    manager_group_name,
    depositary_name,
    depositary_registration_number,
    depositary_group_name
from latest_metadata
