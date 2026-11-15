-- Risk and performance metrics per class over the 3-year (36-month) window.
-- The logic lives in the class_metrics macro, shared with the 5-year horizon.
select * rename (cagr_window as cagr_3y)
from ({{ class_metrics('int_weekly_nav_returns', 'base') }})
