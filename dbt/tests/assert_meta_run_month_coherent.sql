{{ config(severity='warn') }}
-- Warns when the last NAV date does not fall in the cut-off month: the last
-- file may be empty or truncated, and the metrics would then use an older date.
select *
from {{ ref('meta_run') }}
where strftime(as_of_date, '%Y%m') <> as_of_period
