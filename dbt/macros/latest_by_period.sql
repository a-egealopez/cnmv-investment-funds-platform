{% macro latest_by_period(relation, key, as_of_period, period_column='period') %}
{#
    Devuelve una fila por `key`: la del mayor `period_column` <= as_of_period.
    Implementa el patrón Type 1 (último atributo conocido).
#}
select *
from (
    select
        *,
        row_number() over (
            partition by {{ key }}
            order by {{ period_column }} desc
        ) as _row_number
    from {{ relation }}
    where {{ period_column }} <= cast('{{ as_of_period }}' as varchar)
)
where _row_number = 1
{% endmacro %}
