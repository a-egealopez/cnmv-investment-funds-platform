{{ config(materialized='view') }}
with source as (
    -- Data after the cut-off of the run is not part of this run.
    select *
    from
        {{ ref('stg_fund_nav_daily') }}
    where
        period <= {{ current_as_of_period() }}
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

    nullif(
        concat_ws(
            '; ',
            case when {{ is_material_negative('s.nav') }} then 'negative_nav_material' end,
            case when {{ is_material_negative('s.aum') }} then 'negative_aum_material' end,
            case when {{ is_material_negative('s.holders') }} then 'negative_holders_material' end
        ),
        ''
    ) as quarantine_reason
from
    source as s
