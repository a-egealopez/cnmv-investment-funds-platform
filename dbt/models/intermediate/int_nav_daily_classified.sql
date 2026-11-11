with source as (
    select * from {{ ref('stg_fund_nav_daily') }}
),

known_issues as (
    select
        s.class_key,
        s.value_date,
        string_agg(k.reason, '; ' order by k.reason) as issue_reason
    from {{ ref('stg_fund_nav_daily') }} as s
    inner join {{ ref('known_data_issues') }} as k
        on s.class_key = k.class_key
       and s.value_date between k.start_date and k.end_date
    group by s.class_key, s.value_date
)

select
    s.*,

    s.nav = 0 as is_dormant,

    {{ is_material_negative('s.nav') }}         as is_material_nav,
    {{ is_material_negative('s.aum') }}         as is_material_aum,
    {{ is_material_negative('s.holders') }}     as is_material_holders,
    (
        {{ is_material_negative('s.nav') }}
        or {{ is_material_negative('s.aum') }}
        or {{ is_material_negative('s.holders') }}
    ) as is_material,

    {{ is_dust_negative('s.nav') }}             as is_dust_nav,
    {{ is_dust_negative('s.aum') }}             as is_dust_aum,
    {{ is_dust_negative('s.holders') }}         as is_dust_holders,
    (
        {{ is_dust_negative('s.nav') }}
        or {{ is_dust_negative('s.aum') }}
        or {{ is_dust_negative('s.holders') }}
    ) as is_dust,

    k.issue_reason is not null as is_known_issue,

    nullif(
        concat_ws(
            '; ',
            case when {{ is_material_negative('s.nav') }} then 'negative_nav_material' end,
            case when {{ is_material_negative('s.aum') }} then 'negative_aum_material' end,
            case when {{ is_material_negative('s.holders') }} then 'negative_holders_material' end,
            k.issue_reason
        ),
        ''
    ) as quarantine_reason

from source as s
left join known_issues as k
    on s.class_key = k.class_key
   and s.value_date = k.value_date
