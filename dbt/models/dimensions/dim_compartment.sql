with latest_metadata as (
    {{ latest_by_period(
        relation=ref('stg_fund_metadata'),
        partition_column='compartment_key'
    ) }}
),

-- Fund-level attributes (last known), flattened into the compartment dimension.
latest_fund as (
    {{ latest_by_period(
        relation=ref('stg_fund_metadata'),
        partition_column='fund_key'
    ) }}
),

latest_quarterly as (
    {{ latest_by_period(
        relation=ref('stg_fund_quarterly'),
        partition_column='compartment_key'
    ) }}
),

base as (
select
    row_number() over (order by m.compartment_key) as compartment_id,
    m.compartment_key,
    f.fund_key,
    f.fund_type,
    f.registration_number,
    f.fund_name,
    f.is_etf,
    f.manager_name,
    f.manager_registration_number,
    f.manager_type,
    f.manager_group_name,
    coalesce(g.manager_group_id, -1) as manager_group_id,
    f.depositary_name,
    f.depositary_registration_number,
    f.depositary_group_name,
    m.compartment_number,
    m.compartment_name,
    coalesce(va.canonical_vocation, q.vocation, 'Sin vocación') as vocation,
    coalesce(vf.family, 'Sin vocación') as vocation_family,
    coalesce(vf.include_in_watchlist, false) as include_in_watchlist,
    q.fund_class
from latest_metadata as m
left join latest_quarterly as q
    on q.compartment_key = m.compartment_key
left join {{ ref('vocation_aliases') }} as va
    on va.source_vocation = q.vocation
left join {{ ref('vocacion_family') }} as vf
    on vf.vocation = coalesce(va.canonical_vocation, q.vocation)
left join latest_fund as f
    on f.fund_key = m.fund_key
left join {{ ref('dim_manager_group') }} as g
    on g.manager_group_name = f.manager_group_name
),

-- Readable label: most compartments are called 'COMPARTIMENTO 0' (the fund has a
-- single one), so the label is the fund name, plus the compartment name when the
-- fund really has several. If two labels still collide, the fund type and
-- registration number tell them apart. Always relate by compartment_id.
named as (
    select
        b.*,
        trim(
            coalesce(b.fund_name, '')
            || case
                when b.compartment_number is not null and b.compartment_number > 0
                    then ' · ' || coalesce(b.compartment_name, '')
                else ''
            end
        ) as base_name
    from base as b
)

select
    * exclude (base_name),
    case
        when count(*) over (partition by base_name) > 1
            then base_name || ' [' || fund_type || ' ' || cast(registration_number as varchar) || ']'
        else base_name
    end as display_name
from named
