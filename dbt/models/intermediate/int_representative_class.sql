with first_seen as (
    select
        class_key,
        min(value_date) as first_date
    from
        {{ ref('stg_fund_nav_daily') }}
    where
        period <= {{ current_as_of_period() }}
    group by
        class_key
),

candidates as (
    select
        d.class_key,
        d.compartment_key,
        a.participants,
        a.aum,
        f.first_date
    from
        {{ ref('int_class_metrics') }} as m
    inner join {{ ref('dim_class') }} as d
        on d.class_key = m.class_key
    inner join {{ ref('int_active_class_as_of') }} as a
        on a.class_key = d.class_key
    inner join first_seen as f
        on f.class_key = d.class_key
    where
        m.class_status = 'eligible'
        and d.class_currency_code = '{{ var('watchlist_currency') }}'
),

ranked as (
    select
        c.*,
        row_number() over (
            partition by c.compartment_key
            order by c.participants desc, c.aum desc, c.first_date asc
        ) as rn
    from
        candidates as c
),

selected as (
    select
        compartment_key,
        class_key,
        participants,
        aum,
        first_date
    from
        ranked
    where
        rn = 1
)

select
    d.compartment_key,
    s.class_key,
    s.participants,
    s.aum,
    s.first_date as class_age,
    s.compartment_key is not null as is_representative,
    case
        when s.compartment_key is null then 'no_eligible_class'
        else 'representative'
    end as eligibility_status,
    case
        when s.compartment_key is null then 'no_eligible_class'
    end as exclusion_reason
from
    {{ ref('dim_compartment') }} as d
left join selected as s
    on s.compartment_key = d.compartment_key