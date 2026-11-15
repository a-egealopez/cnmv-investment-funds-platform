-- Weekly €STR compounded index (series .CI), used as risk-free reference (e.g. Sortino).
-- Grain: week_end_date. Rebasing to 100 is done in BI/DAX for the selected window.
-- Covers the 3-year window; the 5-year metrics build the long series inline
-- from the same macro (estr_weekly), so this fact keeps its grain.
{{ estr_weekly('base') }}
