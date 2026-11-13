{% macro current_as_of_period() %}
{#
    Cut-off period (YYYYMM) of the run, as a scalar subquery on meta_run.
#}
(select as_of_period from {{ ref('meta_run') }})
{% endmacro %}
