-- Risk and performance metrics per class over the 5-year window
-- (window_months_long), with the same formulas and quality screen as the
-- 3-year ones. A class without five years of clean history is short_history
-- or quarantined here even if it is eligible over 3 years.
select * rename (cagr_window as cagr_5y)
from ({{ class_metrics('int_weekly_nav_returns_5y', 'long') }})
