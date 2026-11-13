-- The cut-off must exist in Silver and have data up to it.
select *
from {{ ref('meta_run') }}
where as_of_date is null
   or as_of_period > silver_max_period
