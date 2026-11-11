with source as (
    select * from {{source('silver', 'estr_daily') }}
)

select
    series,
    value_date,
    obs_value as series_value,
    obs_status
from source