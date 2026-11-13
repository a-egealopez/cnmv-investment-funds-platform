-- The panorama is the decision view: one row per compartment through its
-- representative class. Holdings, flows and fees are compartment-level; the
-- representative class inherits them.
with representatives as (
    select
        r.compartment_key,
        r.class_key,
        r.participants,
        r.aum as class_aum
    from
        {{ ref('int_representative_class') }} as r
    where
        r.is_representative
),

-- Compartments with at least one active class at the as-of date.
active_compartments as (
    select
        compartment_id,
        aum,
        participants
    from
        {{ ref('int_active_compartment_as_of') }}
),

-- Portfolio concentration from the latest reported period of each compartment.
-- fact_holdings keeps every period, so the latest one is selected per compartment.
holdings_concentration as (
    select
        h.compartment_id,
        h.date_key as holdings_date_key,
        count(*) filter (where h.weight is not null) as n_positions,
        sum(power(h.weight, 2)) as hhi,
        1.0 / nullif(sum(power(h.weight, 2)), 0) as effective_n,
        sum(h.weight) filter (
            where h.position_rank <= 10
        ) as top10_weight,
        max(h.coverage_ratio) as holdings_coverage_ratio
    from
        (
            select
                h.*,
                dense_rank() over (
                    partition by h.compartment_id
                    order by h.date_key desc
                ) as period_rank
            from
                {{ ref('fact_holdings') }} as h
        ) as h
    where
        h.period_rank = 1
    group by
        1, 2
),

latest_months as (
    select
        compartment_id,
        max(date_key) as last_flow_date_key
    from
        {{ ref('fact_compartment_monthly') }}
    group by
        compartment_id
),

-- Flows from the latest month with data. They are monthly, so the latest
-- month is enough.
latest_flows as (
    select
        m.compartment_id,
        m.date_key,
        m.net_flow_yield,
        m.market_growth,
        m.is_flow_outlier
    from
        {{ ref('fact_compartment_monthly') }} as m
    inner join latest_months as lm
        on lm.compartment_id = m.compartment_id
        and lm.last_flow_date_key = m.date_key
),

-- Fees are semiannual (June and December closings), so they come from the
-- latest closing with data in fact_fund_period_financials, not from the
-- monthly flows.
latest_fees as (
    select
        compartment_id,
        date_key as fees_date_key,
        charged_expense_yield_rate as charged_expense_yield_ytd_rate,
        core_fee_share,
        fee_revenue_proxy as fee_revenue_proxy_ytd,
        is_fee_outlier
    from
        (
            select
                f.*,
                row_number() over (
                    partition by f.compartment_id
                    order by f.date_key desc
                ) as rn
            from
                {{ ref('fact_fund_period_financials') }} as f
            where
                f.charged_expense_yield_rate is not null
        )
    where
        rn = 1
),

-- Anomalies per compartment, with counts by severity.
anomaly_counts as (
    select
        compartment_id,
        count(*) as n_anomalies,
        cast(sum(case when severity = 'high' then 1 else 0 end) as bigint) as n_anomalies_high
    from
        {{ ref('fact_fund_anomalies') }}
    group by
        1
),

-- Rating for every ranked compartment, not only the selected ones.
rating as (
    select
        c.compartment_id,
        p.percentile_in_vocation as peer_percentile,
        p.quartile_in_vocation   as peer_quartile,
        p.star_rating,
        p.n_peers,
        p.watchlist_rank
    from {{ ref('int_fund_peer_ranking') }} as p
    inner join {{ ref('dim_compartment') }} as c
        on c.compartment_key = p.compartment_key
)

select
    d.compartment_id,
    cl.class_id,
    m.ret_1y,
    m.cagr_3y,
    m.vol,
    m.srri_like_class,
    m.sortino,
    m.sortino_status,
    m.max_drawdown,
    m.coverage_ratio,
    m.stale_share,
    m.gap_share,

    cast(a.aum as double) as aum,
    cast(a.participants as bigint) as participants,
    coalesce(
        a.aum >= {{ var('min_aum_compartment') }}
        and a.participants >= {{ var('min_participants_compartment') }},
        false
    ) as meets_size_floor,

    case
        when rt.watchlist_rank is not null then 'selected'
        else 'not_selected'
    end as watchlist_status,
    rt.watchlist_rank as rnk,
    rt.peer_percentile,
    rt.peer_quartile,
    rt.star_rating,
    rt.n_peers,

    h.holdings_date_key,
    h.n_positions,
    h.hhi,
    h.effective_n,
    h.top10_weight,
    h.holdings_coverage_ratio,
    case
        when h.holdings_coverage_ratio is null then null
        when h.holdings_coverage_ratio < {{ var('min_holdings_coverage') }}
          or h.holdings_coverage_ratio > {{ var('max_holdings_coverage') }} then true
        else false
    end as holdings_incomplete,

    fl.net_flow_yield,
    fl.market_growth,
    coalesce(fl.is_flow_outlier, false) as is_flow_outlier,
    fee.fees_date_key,
    fee.core_fee_share,
    fee.charged_expense_yield_ytd_rate,
    fee.fee_revenue_proxy_ytd,
    coalesce(fee.is_fee_outlier, false) as is_fee_outlier,

    coalesce(ac.n_anomalies, 0) as n_anomalies,
    coalesce(ac.n_anomalies_high, 0) as n_anomalies_high

from
    representatives as r
inner join {{ ref('dim_compartment') }} as d
    on d.compartment_key = r.compartment_key
inner join {{ ref('dim_class') }} as cl
    on cl.class_key = r.class_key
inner join {{ ref('int_class_metrics') }} as m
    on m.class_key = r.class_key
inner join active_compartments as a
    on a.compartment_id = d.compartment_id
left join holdings_concentration as h
    on h.compartment_id = d.compartment_id
left join latest_flows as fl
    on fl.compartment_id = d.compartment_id
left join latest_fees as fee
    on fee.compartment_id = d.compartment_id
left join anomaly_counts as ac
    on ac.compartment_id = d.compartment_id
left join rating as rt
    on rt.compartment_id = d.compartment_id
