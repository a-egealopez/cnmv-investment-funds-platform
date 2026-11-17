-- The monthly change in total market assets must be explained by the funds:
--   change = net flows + market effect + corporate actions + entries and exits.
-- If a fund could disappear without an outflow (a closure or a merger into another
-- fund), its assets would leave the total but not the flows, and new money would be
-- overstated. Before entry_exit_flows existed, the gap reached EUR 4.7bn in a month.
--
-- Tolerance: 0.1 % of the market's assets. Real data reconciles within 0.06 %; the
-- remainder is classes that do not report on the last day of the month.
-- Only consecutive months are compared. The first month of the window is skipped:
-- the daily bridge starts on its first day, so the change from the previous
-- month-end is not in it.
with explained as (
    select
        m.date_key,
        sum(m.net_flows + m.market_effect + m.corporate_action_delta_aum + m.entry_exit_flows)
            as explained_change
    from {{ ref('fact_compartment_monthly') }} as m
    inner join {{ ref('dim_compartment') }} as c
        on c.compartment_id = m.compartment_id
    -- The market total excludes compartments with an unknown manager group
    where c.manager_group_id <> -1
    group by m.date_key
),

market as (
    select
        date_key,
        total_aum_managed,
        total_aum_managed - lag(total_aum_managed) over (order by date_key) as actual_change,
        {{ month_index('date_key // 100') }}
            - lag({{ month_index('date_key // 100') }}) over (order by date_key) as months_since_previous
    from {{ ref('fact_market_fee_and_aum') }}
)

select
    e.date_key,
    k.actual_change,
    e.explained_change,
    e.explained_change - k.actual_change as gap
from explained as e
inner join market as k
    on k.date_key = e.date_key
where
    e.date_key > (select min(date_key) from explained)
    -- Only a month against the one right before it (sparse data, like the CI fixture)
    and k.months_since_previous = 1
    and abs(e.explained_change - k.actual_change) > 0.001 * k.total_aum_managed
