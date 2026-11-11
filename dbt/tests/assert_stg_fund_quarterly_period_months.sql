select *
from {{ ref('stg_fund_quarterly') }}
where substr(period, 5, 2) not in ('06', '12')