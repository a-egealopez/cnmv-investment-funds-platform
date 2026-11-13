with latest_metadata as (
    {{ latest_by_period(
        relation=ref('stg_fund_metadata'),
        partition_column='class_key'
    ) }}
),

latest_quarterly as (
    {{ latest_by_period(
        relation=ref('stg_fund_quarterly'),
        partition_column='class_key'
    ) }}
),

base as (
    select
        row_number() over (order by m.class_key) as class_id,
        m.class_key,
        m.compartment_key,
        p.compartment_id,
        m.class_number,
        m.class_name,
        m.isin,
        coalesce(q.class_currency_code, 'N/D') as class_currency_code,
        coalesce(q.iic_currency_code, 'N/D') as iic_currency_code
    from latest_metadata as m
    left join latest_quarterly as q
        on q.class_key = m.class_key
    left join {{ ref('dim_compartment') }} as p
        on p.compartment_key = m.compartment_key
),

named as (
select
    b.class_id,
    b.class_key,
    b.compartment_key,
    b.compartment_id,
    b.class_number,
    b.class_name,
    b.isin,
    b.class_currency_code,
    b.iic_currency_code,
    cp.fund_name,
    cp.compartment_number,
    cp.compartment_name,
    cp.vocation,
    cp.vocation_family,
    cp.fund_class,
    cp.include_in_watchlist,
    cp.manager_group_id,
    cp.manager_group_name,
    cp.manager_name,
    cp.depositary_name,
    cp.depositary_group_name,
    cp.is_etf,
    trim(
        coalesce(cp.fund_name, '')
        || case
            when cp.compartment_number is not null and cp.compartment_number > 0
                then ' · ' || coalesce(cp.compartment_name, '')
            else ''
        end
        || case
            when b.class_name is not null and b.class_name <> ''
                then ' · ' || b.class_name
            else ''
        end
    ) as base_name,
    cp.fund_type,
    cp.registration_number
from base as b
left join {{ ref('dim_compartment') }} as cp
    on cp.compartment_id = b.compartment_id
),

-- Same rule as dim_compartment: if two labels collide, the fund type and
-- registration number tell them apart; if they still collide (the source has
-- classes of the same fund with the same name and even the same ISIN), the
-- class number does. Always relate by class_id.
registered as (
    select
        * exclude (base_name, fund_type, registration_number),
        case
            when count(*) over (partition by base_name) > 1
                then base_name || ' [' || fund_type || ' ' || cast(registration_number as varchar) || ']'
            else base_name
        end as registered_name
    from named
),

classes as (
    select
        * exclude (registered_name),
        case
            when count(*) over (partition by registered_name) > 1
                then registered_name || ' #' || cast(class_number as varchar)
            else registered_name
        end as display_name
    from registered
)

select * from classes

union all by name

-- Unknown member: anomalies detected at compartment level have no class.
select
    -1 as class_id,
    'n/a' as class_key,
    'n/a' as compartment_key,
    cast(null as bigint) as compartment_id,
    cast(null as integer) as class_number,
    'Sin clase' as class_name,
    'N/D' as isin,
    'N/D' as class_currency_code,
    'N/D' as iic_currency_code,
    'Sin clase' as fund_name,
    cast(null as integer) as compartment_number,
    'Sin clase' as compartment_name,
    'Sin vocación' as vocation,
    'Sin vocación' as vocation_family,
    cast(null as varchar) as fund_class,
    false as include_in_watchlist,
    -1 as manager_group_id,
    'Desconocido' as manager_group_name,
    'Desconocido' as manager_name,
    'Desconocido' as depositary_name,
    'Desconocido' as depositary_group_name,
    false as is_etf,
    'Sin clase (señal a nivel de compartimento)' as display_name
