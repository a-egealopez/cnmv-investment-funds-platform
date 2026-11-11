with bounds as (
    {{ analysis_window() }}
),

-- The panorama is the decision view: one row per compartment through its
-- representative class. Holdings, flows and fees are compartment-level; the
-- representative class inherits them.
representatives as (
    select
        r.compartment_key,
        r.class_key,
        r.participants,
        r.aum as class_aum,
        r.is_representative
    from
        {{ ref('int_representative_class') }} as r
    where
        r.is_representative
),

-- Compartments with at least one active class at the as-of date.
active_compartments as (
    select
        cl.compartment_id,
        sum(f.aum) as aum,
        sum(f.holders) as participants
    from
        {{ ref('fact_nav_daily') }} as f
    inner join {{ ref('dim_class') }} as cl
        on cl.class_id = f.class_id
    inner join bounds as b
        on f.date_key = cast(strftime(b.as_of_date, '%Y%m%d') as integer)
    where
        f.aum > 0
        and f.holders > 0
    group by
        cl.compartment_id
),

-- Portfolio concentration from the latest reported period.
holdings_concentration as (
    select
        h.compartment_id,
        max(h.holdings_period) as holdings_period,
        count(*) filter (where h.weight is not null) as n_positions,
        sum(power(h.weight, 2)) as hhi,
        1.0 / nullif(sum(power(h.weight, 2)), 0) as effective_n,
        sum(h.weight) filter (
            where rank_by_weight is not null and rank_by_weight <= 10
        ) as top10_weight,
        max(h.coverage_ratio) as holdings_coverage_ratio
    from
        (
            select
                h.*,
                row_number() over (
                    partition by h.compartment_id, h.holdings_period
                    order by h.weight desc nulls last
                ) as rank_by_weight
            from
                {{ ref('fact_holdings') }} as h
        ) as h
    group by
        1
),

latest_months as (
    select
        compartment_id,
        max(month) as last_flow_month,
        max(month) filter (where expense_ratio_pct is not null) as last_fee_month
    from
        {{ ref('mart_compartment_monthly_performance') }}
    group by
        compartment_id
),

-- Flows from the latest month with data. They are monthly, so the latest
-- month is enough.
latest_flows as (
    select
        m.compartment_id,
        m.month,
        m.net_flow_yield,
        m.market_growth,
        m.organic_growth
    from
        {{ ref('mart_compartment_monthly_performance') }} as m
    inner join latest_months as lm
        on lm.compartment_id = m.compartment_id
        and lm.last_flow_month = m.month
),

-- Fees only exist in closing months (June and December). Using the latest
-- flow month left them always null because that month is never a closing month.
latest_fees as (
    select
        m.compartment_id,
        m.month as fees_period,
        m.expense_ratio_pct,
        m.core_fee_share,
        m.fee_revenue_proxy
    from
        {{ ref('mart_compartment_monthly_performance') }} as m
    inner join latest_months as lm
        on lm.compartment_id = m.compartment_id
        and lm.last_fee_month = m.month
),

-- Anomalies per compartment, with counts by severity.
anomaly_counts as (
    select
        compartment_id,
        count(*) as n_anomalies,
        sum(case when severity = 'high' then 1 else 0 end) as n_anomalies_high
    from
        {{ ref('mart_fund_anomalies') }}
    group by
        1
),

-- Watchlist selection, if the compartment is in it.
watchlist as (
    select
        compartment_id,
        watchlist_status,
        rnk,
        percentile as watchlist_percentile,
        quartile as watchlist_quartile
    from
        {{ ref('mart_fund_watchlist') }}
    where
        watchlist_status = 'selected'
)

select
    '{{ var("as_of_period") }}' as as_of_period,
    d.fund_id,
    d.compartment_id,
    cl.class_id,
    d.vocation,
    d.vocation_family,
    cl.class_currency_code as currency,

    m.class_status,
    m.class_status_reason,
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

    a.aum,
    a.participants,

    r.is_representative,
    case
        when w.compartment_id is not null then 'selected'
        when r.class_key is null then 'not_representative'
        else 'not_selected'
    end as watchlist_status,
    case
        when w.compartment_id is not null then null
        when r.class_key is null then 'not_representative'
        when m.class_status <> 'eligible' then coalesce(m.class_status_reason, 'not_eligible')
        else 'not_selected'
    end as exclusion_reason,
    w.rnk,
    w.watchlist_percentile,
    w.watchlist_quartile,

    h.holdings_period,
    h.n_positions,
    h.hhi,
    h.effective_n,
    h.top10_weight,
    h.holdings_coverage_ratio,
    case
        when h.holdings_coverage_ratio is null then null
        when h.holdings_coverage_ratio < {{ var('min_holdings_coverage', 0.80) }}
          or h.holdings_coverage_ratio > {{ var('max_holdings_coverage', 1.20) }} then true
        else false
    end as holdings_incomplete,

    fl.net_flow_yield,
    fl.market_growth,
    fl.organic_growth,
    fee.fees_period,
    fee.core_fee_share,
    fee.expense_ratio_pct,
    fee.fee_revenue_proxy,

    coalesce(ac.n_anomalies, 0) as n_anomalies,
    coalesce(ac.n_anomalies_high, 0) as n_anomalies_high

from
    representatives as r
inner join {{ ref('dim_compartment') }} as d
    on d.compartment_key = r.compartment_key
inner join {{ ref('dim_class') }} as cl
    on cl.class_key = r.class_key
inner join {{ ref('int_class_metrics_36m') }} as m
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
left join watchlist as w
    on w.compartment_id = d.compartment_id
