{% macro analysis_window(horizon='base') %}
{#
    as_of_date and window_start of the run for a metric horizon. The definition
    lives in meta_run; this macro only exposes it with the shape the metric
    models already use. horizon: 'base' (window_months, 36 months; every model
    except the 5-year metrics) or 'long' (window_months_long, 60 months).
#}
{% if horizon not in ('base', 'long') %}
    {{ exceptions.raise_compiler_error("analysis_window horizon must be 'base' or 'long', got: " ~ horizon) }}
{% endif %}
select
    as_of_date,
    {{ 'window_start' if horizon == 'base' else 'window_start_long' }} as window_start
from
    {{ ref('meta_run') }}
{% endmacro %}
