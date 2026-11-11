select *
from {{ ref('known_data_issues') }}
where start_date > end_date
