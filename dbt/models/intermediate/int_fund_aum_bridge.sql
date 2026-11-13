with bounds as (
    {{ analysis_window() }}
),

-- Valid daily series: positive NAV and AUM. units = aum / nav requires both
-- magnitudes to make sense; a non-positive value would produce fictitious flows.
valid_daily as (
    select
        cl.class_key,
        d.date_day as value_date,
        f.nav,
        f.aum
    from
        {{ ref('fact_nav_daily') }} as f
    inner join {{ ref('dim_date') }} as d
        on d.date_key = f.date_key
    inner join {{ ref('dim_class') }} as cl
        on cl.class_id = f.class_id
    cross join bounds as b
    where
        f.nav > 0
        and f.aum > 0
        and d.date_day between b.window_start and b.as_of_date
),

daily_lagged as (
    select
        v.*,
        lag(v.nav)     over by_class as prev_nav,
        lag(v.aum)     over by_class as prev_aum
    from
        valid_daily as v
    window by_class as (partition by class_key order by value_date)
),

-- valid_daily guarantees positive NAV and AUM; a non-null prev_nav implies
-- the previous row is valid.
with_units as (
    select
        l.*,
        l.aum / l.nav           as units,
        l.prev_aum / l.prev_nav as prev_units
    from
        daily_lagged as l
    where
        l.prev_nav is not null
),

bridged as (
    select
        u.class_key,
        u.value_date,
        u.units,
        u.aum,
        u.nav,

        -- Net flows: unit change valued at current NAV.
        (u.units - u.prev_units) * u.nav                 as net_flows,
        u.prev_units * (u.nav - u.prev_nav)              as market_effect,
        u.aum - u.prev_aum                               as delta_aum,

        (u.aum - u.prev_aum) / u.prev_aum                as total_growth,
        (u.prev_units * (u.nav - u.prev_nav)) / u.prev_aum as market_growth,

        -- Price jump: NAV move above the extreme-return threshold. It is not a
        -- cash flow but a change of identity or a decapitalization.
        abs(u.nav / u.prev_nav - 1) > {{ var('extreme_return_abs') }}
            as is_jump,

        -- Capital and price jump together: AUM and NAV change at once (merger,
        -- class change or new share class). AUM appears or disappears without
        -- money entering or leaving. An AUM jump with stable NAV is a real flow.
        (
            (u.aum / u.prev_aum > {{ var('capital_change_aum_ratio') }}
             or u.aum / u.prev_aum < 1.0 / {{ var('capital_change_aum_ratio') }})
            and abs(u.nav / u.prev_nav - 1) > {{ var('capital_change_nav_move') }}
        ) as is_capital_change

    from
        with_units as u
)

select
    class_key,
    value_date,
    units,
    aum,
    nav,
    market_effect,
    net_flows,
    delta_aum,
    market_growth,
    total_growth,
    is_jump,
    is_capital_change
from
    bridged
