-- Key findings quoted in the README, one query per figure.
--
-- Run against the Gold database after `docker compose up`:
--   duckdb -readonly data/gold/cnmv.duckdb -f docs/analytics/key_findings.sql
--
-- Gold is already cut at meta_run.as_of_period, so the figures follow the cut-off of
-- the last dbt run. These are internal analytical figures built from official CNMV
-- data, not official CNMV statistics. Update the README figures at each release.


-- 1. Market size: assets under management in the first month of history and at the cut-off.
select
    date_key,
    round(total_aum_managed / 1e9, 1) as aum_eur_bn
from fact_market_fee_and_aum
where date_key in (
    (select min(date_key) from fact_market_fee_and_aum),
    (select max(date_key) from fact_market_fee_and_aum)
)
order by date_key;


-- 2. Where the growth of the last three years came from: new money (net flows)
--    against market gains. The monthly flow fact covers the 3-year window only.
select
    min(date_key) as first_month,
    max(date_key) as last_month,
    round(sum(delta_aum) / 1e9, 1) as aum_change_eur_bn,
    round(sum(net_flows) / 1e9, 1) as net_flows_eur_bn,
    round(sum(market_effect) / 1e9, 1) as market_effect_eur_bn,
    round(100 * sum(net_flows) / (sum(net_flows) + sum(market_effect)), 0) as flows_share_pct
from fact_compartment_monthly;


-- 3. Concentration: the five largest manager groups at the cut-off, their share of
--    assets and how much their assets grew since the first month of history.
with
bounds as (
    select min(date_key) as first_key, max(date_key) as last_key
    from fact_manager_group_monthly
),

top5 as (
    select f.manager_group_id, f.rank_by_aum, f.aum_managed, f.market_share
    from fact_manager_group_monthly as f, bounds as b
    where f.date_key = b.last_key and f.rank_by_aum <= 5
)

select
    t.rank_by_aum,
    g.manager_group_name,
    round(100 * t.market_share, 1) as aum_share_pct,
    round(100 * sum(t.market_share) over (), 1) as top5_share_pct,
    round(s.aum_managed / 1e9, 1) as first_aum_eur_bn,
    round(t.aum_managed / 1e9, 1) as last_aum_eur_bn,
    round(100 * (t.aum_managed / s.aum_managed - 1), 0) as growth_pct
from top5 as t
cross join bounds as b
inner join dim_manager_group as g
    on g.manager_group_id = t.manager_group_id
left join fact_manager_group_monthly as s
    on s.manager_group_id = t.manager_group_id
    and s.date_key = b.first_key
order by t.rank_by_aum;


-- 4. Combined share of the five largest groups in the first month of history.
select
    date_key,
    round(100 * sum(market_share), 1) as top5_share_pct
from fact_manager_group_monthly
where
    rank_by_aum <= 5
    and date_key = (select min(date_key) from fact_manager_group_monthly)
group by date_key;


-- 5. New money over the last three years for the largest groups, in euros and as a
--    share of the assets each group managed just before the window started.
with
flows as (
    select
        manager_group_id,
        min(date_key) as first_flow_key,
        sum(net_flows) as net_flows,
        sum(market_effect) as market_effect
    from fact_manager_group_monthly
    where net_flows is not null
    group by manager_group_id
),

start_aum as (
    select f.manager_group_id, f.aum_managed
    from fact_manager_group_monthly as f
    where f.date_key = (
        select max(date_key)
        from fact_manager_group_monthly
        where date_key < (select min(first_flow_key) from flows)
    )
)

select
    g.manager_group_name,
    round(fl.net_flows / 1e9, 1) as net_flows_eur_bn,
    round(fl.market_effect / 1e9, 1) as market_effect_eur_bn,
    round(100 * fl.net_flows / s.aum_managed, 0) as net_flows_pct_of_start_aum
from flows as fl
inner join start_aum as s
    on s.manager_group_id = fl.manager_group_id
inner join dim_manager_group as g
    on g.manager_group_id = fl.manager_group_id
order by fl.net_flows desc
limit 5;


-- 6. The largest funds at the cut-off.
select
    c.fund_name,
    c.manager_group_name,
    c.vocation,
    round(f.aum / 1e9, 1) as aum_eur_bn
from fact_compartment_monthly as f
inner join dim_compartment as c
    on c.compartment_id = f.compartment_id
where f.date_key = (select max(date_key) from fact_compartment_monthly)
order by f.aum desc
limit 5;


-- 7. Management fees at the latest semiannual closing: the median fund against the
--    asset-weighted average (what the average euro pays).
select
    date_key,
    count(*) as n_compartments,
    round(100 * median(management_fee_yield_annualized_rate), 2) as median_fee_pct,
    round(
        100 * sum(management_fee_yield_annualized_rate * average_patrimony) / sum(average_patrimony),
        2
    ) as asset_weighted_fee_pct
from fact_fund_period_financials
where
    date_key = (select max(date_key) from fact_fund_period_financials)
    and management_fee_yield_annualized_rate is not null
group by date_key;


-- 8. Management fees by fund size at the latest closing: median fee per band and the
--    share of all assets each band holds.
with funds as (
    select
        management_fee_yield_annualized_rate as fee_rate,
        average_patrimony
    from fact_fund_period_financials
    where
        date_key = (select max(date_key) from fact_fund_period_financials)
        and management_fee_yield_annualized_rate is not null
)

select
    case
        when average_patrimony < 50e6 then '1. under 50m'
        when average_patrimony < 500e6 then '2. 50m to 500m'
        when average_patrimony < 1e9 then '3. 500m to 1bn'
        else '4. over 1bn'
    end as size_band,
    count(*) as n_compartments,
    round(100 * median(fee_rate), 2) as median_fee_pct,
    round(100 * sum(average_patrimony) / sum(sum(average_patrimony)) over (), 0) as assets_share_pct
from funds
group by size_band
order by size_band;


-- 9. Concentration of management fee revenue: share of the five largest groups,
--    at the first closing with fee data and at the latest one.
select
    date_key,
    round(100 * top5_fee_share, 1) as top5_fee_share_pct
from fact_market_fee_and_aum
where date_key in (
    (select min(date_key) from fact_market_fee_and_aum where top5_fee_share is not null),
    (select max(date_key) from fact_market_fee_and_aum where top5_fee_share is not null)
)
order by date_key;
