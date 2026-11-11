{% macro latest_by_period(relation, key, as_of_period, period_column='period') %}
{#
    Returns one row per `key`: the row with the greatest `period_column` <= as_of_period.
    Implements the Type 1 pattern (last known attribute).
#}
select *
from
    (
        select
            *,
            row_number() over (
                partition by {{ key }}
                order by {{ period_column }} desc
            ) as _row_number
        from
            {{ relation }}
        where
            {{ period_column }} <= cast('{{ as_of_period }}' as varchar)
    )
where
    _row_number = 1
{% endmacro %}
