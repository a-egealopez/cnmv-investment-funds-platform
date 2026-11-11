select *
from {{ ref('stg_fund_period_financials') }}
where substr(period, 5, 2) not in ('03', '06', '09', '12')