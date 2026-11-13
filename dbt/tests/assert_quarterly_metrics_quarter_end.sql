-- date_key must be the last day of a natural quarter: 31/03, 30/06, 30/09, 31/12.
select
    f.class_id,
    d.date_day
from {{ ref('fact_fund_quarterly_metrics') }} as f
inner join {{ ref('dim_date') }} as d
    on d.date_key = f.date_key
where extract(day from d.date_day) not in (31, 30)
   or extract(month from d.date_day) not in (3, 6, 9, 12)
