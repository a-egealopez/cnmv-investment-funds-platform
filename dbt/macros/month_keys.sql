{% macro month_key_of(date_column) %}
{# Integer YYYYMM key of a date. #}
cast(strftime({{ date_column }}, '%Y%m') as integer)
{% endmacro %}

{% macro month_key_to_date(month_key_column) %}
{# First day of the month of an integer YYYYMM key. #}
cast(strptime(cast({{ month_key_column }} as varchar) || '01', '%Y%m%d') as date)
{% endmacro %}

{% macro month_index(month_key_column) %}
{# Consecutive month number (year * 12 + month); consecutive months differ by 1. #}
(({{ month_key_column }}) // 100 * 12 + ({{ month_key_column }}) % 100)
{% endmacro %}

{% macro month_key_to_date_key(month_key_column) %}
{# date_key (YYYYMMDD) of the last day of the month of an integer YYYYMM key. #}
cast(strftime(last_day({{ month_key_to_date(month_key_column) }}), '%Y%m%d') as integer)
{% endmacro %}

{% macro date_key_to_date(date_key_column) %}
{# DATE of an integer date_key (YYYYMMDD). #}
cast(strptime(cast({{ date_key_column }} as varchar), '%Y%m%d') as date)
{% endmacro %}
