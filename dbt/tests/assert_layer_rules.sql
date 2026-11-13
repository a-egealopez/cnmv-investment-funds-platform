-- Architecture rules, checked on the dbt graph (no data is read):
--   1. mart_* models are leaves: no other model depends on them.
--   2. stg_* models only read sources (cast and rename, nothing else).
{% set violations = [] %}
{% for node in graph.nodes.values() if node.resource_type == 'model' %}
    {% for dep in node.depends_on.nodes %}
        {% set dep_name = dep.split('.')[-1] %}
        {% if dep_name.startswith('mart_') %}
            {% do violations.append(node.name ~ ' reads ' ~ dep_name ~ ' (marts are leaves)') %}
        {% endif %}
        {% if node.name.startswith('stg_') and dep.startswith('model.') %}
            {% do violations.append(node.name ~ ' reads model ' ~ dep_name ~ ' (staging reads only sources)') %}
        {% endif %}
    {% endfor %}
{% endfor %}

select cast(null as varchar) as violation
where false
{% for v in violations %}
union all select '{{ v }}'
{% endfor %}
