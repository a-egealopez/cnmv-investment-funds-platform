select f.*
from {{ ref('fact_nav_daily') }} as f
inner join {{ ref('dim_date') }} as d
    on f.date_key = d.date_key
inner join {{ ref('known_data_issues') }} as k
    on f.class_key = k.class_key
   and d.date_day between k.start_date and k.end_date
