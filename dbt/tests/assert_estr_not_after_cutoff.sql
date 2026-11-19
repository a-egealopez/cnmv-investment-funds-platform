-- A run cut at as_of_date must not use data published after it. The €STR is the
-- only source read by date rather than by reporting period, and the last week of
-- the window can end after the cut-off, so it is checked here.
select
    e.date_key,
    e.estr_date
from {{ ref('fact_estr_weekly') }} as e
where e.estr_date > (select as_of_date from {{ ref('meta_run') }})
