{{ config(severity='warn') }}
-- Warns when the panorama is empty. It happens when the cut-off is earlier than
-- the first complete analysis window (window_months of history): every class
-- is then short_history. With the current data the first useful cut-off is 202512.
select
    as_of_period,
    as_of_date,
    window_start
from {{ ref('meta_run') }}
where (select count(*) from {{ ref('mart_fund_panorama') }}) = 0
