-- Active class definition is shared with int_representative_class and the panorama.
with classes as (
    select
        d.class_id,
        d.class_key,
        d.compartment_id,
        d.class_number,
        d.class_name,
        d.isin,
        d.class_currency_code as currency,
        a.class_key is not null as is_active
    from
        {{ ref('dim_class') }} as d
    left join {{ ref('int_active_class_as_of') }} as a
        on a.class_key = d.class_key
    where
        d.class_id <> -1
),

metrics as (
    select
        class_key,
        class_status,
        class_status_reason
    from
        {{ ref('int_class_metrics') }}
),

representatives as (
    select
        class_key,
        is_representative
    from
        {{ ref('int_representative_class') }}
),

-- Same entry criteria as mart_fund_panorama (marts are not read by other
-- models): representative class, with metrics, in a compartment that is active
-- at the as-of date.
panorama as (
    select
        d.class_id
    from
        {{ ref('dim_class') }} as d
    inner join {{ ref('int_representative_class') }} as r
        on r.class_key = d.class_key
        and r.is_representative
    inner join {{ ref('int_class_metrics') }} as m
        on m.class_key = d.class_key
    inner join {{ ref('int_active_compartment_as_of') }} as a
        on a.compartment_id = d.compartment_id
),

classified as (
    select
        c.*,
        m.class_status as metrics_status,
        m.class_status_reason as metrics_status_reason,
        coalesce(r.is_representative, false) as is_representative,
        p.class_id is not null as is_in_panorama,
        case
            when not c.is_active then 'no_recent_nav'
            when c.currency is distinct from '{{ var('watchlist_currency') }}'
                then 'other_currency'
            when coalesce(m.class_status, 'no_metrics') = 'short_history'
                then 'short_history'
            when m.class_status = 'quarantined' then 'quarantined'
            when not coalesce(r.is_representative, false) then 'not_representative'
            when p.class_id is not null then 'in_panorama'
            else 'representative_not_in_panorama'
        end as status
    from
        classes as c
    left join metrics as m
        on m.class_key = c.class_key
    left join representatives as r
        on r.class_key = c.class_key
    left join panorama as p
        on p.class_id = c.class_id
)

select
    class_id,
    compartment_id,
    is_active,
    is_representative,
    is_in_panorama,
    metrics_status,
    metrics_status_reason,
    status,
    case
        when status = 'no_recent_nav' then 'No NAV row with AUM > 0 and holders > 0 at the as-of date'
        when status = 'other_currency' then 'Class currency is not ' || '{{ var('watchlist_currency') }}'
        when status = 'short_history' then 'History is shorter than the analysis window'
        when status = 'quarantined' then metrics_status_reason
        when status = 'not_representative' then 'Another class of the compartment is representative'
        when status = 'representative_not_in_panorama' then 'Representative but missing from the panorama; inspect joins'
    end as status_reason
from
    classified
