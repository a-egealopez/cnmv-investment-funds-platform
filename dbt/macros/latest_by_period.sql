{% macro latest_by_period(relation, partition_column, period_column='period') %}
{#
    Returns one row per `partition_column`: the row with the greatest `period_column` <= the
    run's cut-off period. Implements the Type 1 pattern (last known attribute).
#}
select *
from
    (
        select
            *,
            row_number() over (
                partition by {{ partition_column }}
                order by {{ period_column }} desc
            ) as _row_number
        from
            {{ relation }}
        where
            {{ period_column }} <= {{ current_as_of_period() }}
    )
where
    _row_number = 1
{% endmacro %}
