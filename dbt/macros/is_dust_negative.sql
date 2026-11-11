{% macro is_dust_negative(column) %}
({{ column }} < 0 and abs({{ column }}) <= {{ var('neg_dust_max', 1) }})
{% endmacro %}
