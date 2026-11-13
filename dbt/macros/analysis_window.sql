{% macro analysis_window() %}
{#
    as_of_date and window_start of the run. The definition lives in meta_run;
    this macro only exposes it with the shape the metric models already use.
#}
select
    as_of_date,
    window_start
from
    {{ ref('meta_run') }}
{% endmacro %}
