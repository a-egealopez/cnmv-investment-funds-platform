-- quarter_end_date must be last day of natural quarter: 31/03, 30/06, 30/09, 31/12.
select
    class_id,
    quarter_end_date
from {{ ref('fact_fund_quarterly_metrics') }}
where extract(day from quarter_end_date) not in (31, 30)
   or extract(month from quarter_end_date) not in (3, 6, 9, 12)
