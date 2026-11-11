with bounds as (
    {{ analysis_window() }}
),

classes as (
    select
        cl.class_key,
        c.compartment_key,
        c.fund_key
    from
        {{ ref('dim_class') }} as cl
    inner join {{ ref('dim_compartment') }} as c
        on c.compartment_key = cl.compartment_key
),

-- Weekly series anomalies, at class and quarter level.
nav_anomalies as (
    select
        c.compartment_key,
        c.fund_key,
        c.class_key,
        cast(date_trunc('quarter', w.week_end_date) as date) as period,
        'nav_extreme_return' as anomaly_type,
        'high' as severity,
        max(abs(w.ret_w)) as metric_value,
        {{ var('extreme_return_abs', 0.50) }} as threshold,
        'int_weekly_nav_returns' as source,
        'Retorno semanal absoluto por encima de extreme_return_abs' as description
    from
        {{ ref('int_weekly_nav_returns') }} as w
    inner join classes as c
        on c.class_key = w.class_key
    where
        w.is_extreme
    group by
        1, 2, 3, 4, 5, 6, 9, 10

    union all

    select
        c.compartment_key,
        c.fund_key,
        c.class_key,
        cast(date_trunc('quarter', w.week_end_date) as date) as period,
        'nav_gap' as anomaly_type,
        'warn' as severity,
        count(*) as metric_value,
        {{ var('max_gap_weeks', 1) }} as threshold,
        'int_weekly_nav_returns' as source,
        'Semanas sin semana anterior consecutiva' as description
    from
        {{ ref('int_weekly_nav_returns') }} as w
    inner join classes as c
        on c.class_key = w.class_key
    where
        w.is_gap
    group by
        1, 2, 3, 4, 5, 6, 9, 10
),

-- Series quality anomalies, at class and quarter level.
quality_anomalies as (
    select
        c.compartment_key,
        c.fund_key,
        c.class_key,
        -- A class without any valid week has no last_week: the anomaly is dated
        -- at the as-of date, when it is detected.
        coalesce(
            cast(date_trunc('quarter', m.last_week) as date),
            (select as_of_date from bounds)
        ) as period,
        m.class_status_reason as anomaly_type,
        case
            when m.class_status_reason = 'dormant' then 'high'
            else 'warn'
        end as severity,
        m.coverage_ratio as metric_value,
        {{ var('min_coverage', 0.90) }} as threshold,
        'int_class_metrics_36m' as source,
        case m.class_status_reason
            when 'dormant' then 'Class has weeks with zero liquidation value (padding or dormant class)'
            when 'stale_end' then 'Last observation is prior to window end'
            when 'coverage_lt_min' then 'Week coverage below minimum'
            else 'Class does not have complete 36-month history'
        end as description
    from
        {{ ref('int_class_metrics_36m') }} as m
    inner join classes as c
        on c.class_key = m.class_key
    where
        m.class_status_reason is not null
        and m.class_status_reason <> 'extreme_return'
        and m.class_status_reason <> 'gap_gt_max'
),

-- Stale week share above the maximum.
stale_anomalies as (
    select
        c.compartment_key,
        c.fund_key,
        c.class_key,
        cast(date_trunc('quarter', m.last_week) as date) as period,
        'nav_stale' as anomaly_type,
        'warn' as severity,
        m.stale_share as metric_value,
        {{ var('max_zero_week_share', 0.03) }} as threshold,
        'int_class_metrics_36m' as source,
        'Proportion of weeks with zero return above maximum' as description
    from
        {{ ref('int_class_metrics_36m') }} as m
    inner join classes as c
        on c.class_key = m.class_key
    where
        m.stale_share > {{ var('max_zero_week_share', 0.03) }}
),

trimmed_aum as (
    select
        class_key,
        period,
        aum as aum_trim,
        case
            when substr(period, 5, 2) = '12'
                then cast(substr(period, 1, 4) || '-12-31' as date)
            else last_day(cast(substr(period, 1, 4) || '-' || substr(period, 5, 2) || '-01' as date))
        end as reference_date
    from
        {{ ref('stg_fund_quarterly') }}
),

nav_aum as (
    select
        cast(f.class_id as varchar) as class_key,
        d.date_day,
        max(f.aum) as aum_nav
    from
        {{ ref('fact_nav_daily') }} as f
    inner join {{ ref('dim_date') }} as d
        on d.date_key = f.date_key
    group by
        1, 2
),

-- Reconciliation between official FONDTRIM AUM and FONDMENS AUM. Comparison
-- is class by class at the file's closing date.
reconciliation as (
    select
        c.compartment_key,
        c.fund_key,
        q.class_key,
        cast(substr(q.period, 1, 4) || '-' || substr(q.period, 5, 2) || '-01' as date) as period,
        abs(q.aum_trim - n.aum_nav) / nullif(n.aum_nav, 0) as recon_error
    from
        trimmed_aum as q
    inner join classes as c
        on c.class_key = q.class_key
    inner join nav_aum as n
        on n.class_key = q.class_key
        and n.date_day = q.reference_date
        and n.aum_nav > 0
),

recon_anomalies as (
    select
        r.compartment_key,
        r.fund_key,
        r.class_key,
        r.period,
        'recon_error' as anomaly_type,
        'high' as severity,
        r.recon_error as metric_value,
        {{ var('max_recon_error', 0.01) }} as threshold,
        'stg_fund_quarterly + fact_nav_daily' as source,
        'El patrimonio oficial de FONDTRIM no coincide con el de FONDMENS en la fecha de cierre' as description
    from
        reconciliation as r
    where
        r.recon_error > {{ var('max_recon_error', 0.01) }}
),

-- Fee anomalies: out-of-range expense and compartment without a fee record.
fee_anomalies as (
    select
        c.compartment_key,
        c.fund_key,
        null as class_key,
        cast(substr(m.month, 1, 4) || '-' || substr(m.month, 6, 2) || '-01' as date) as period,
        'fee_outlier' as anomaly_type,
        'warn' as severity,
        m.expense_ratio_pct as metric_value,
        5.0 as threshold,
        'fact_fund_period_financials' as source,
        'Gastos totales sobre el patrimonio por encima del 5% anual' as description
    from
        {{ ref('mart_compartment_monthly_performance') }} as m
    inner join {{ ref('dim_compartment') }} as c
        on c.compartment_id = m.compartment_id
    where
        m.expense_ratio_pct > 5.0

    union all

    select
        c.compartment_key,
        c.fund_key,
        null as class_key,
        cast(substr(f.period, 1, 4) || '-' || substr(f.period, 5, 2) || '-01' as date) as period,
        'fee_period_missing' as anomaly_type,
        'info' as severity,
        null as metric_value,
        null as threshold,
        'stg_fund_period_financials' as source,
        'El compartimento no informa en FONDPATRIMDISVAR para este cierre' as description
    from
        {{ ref('dim_compartment') }} as c
    inner join {{ ref('stg_fund_period_financials') }} as f
        on f.compartment_key = c.compartment_key
    where
        f.total_patrimony is null
),

-- Flow anomalies: outflows above the limit.
flow_anomalies as (
    select
        c.compartment_key,
        c.fund_key,
        null as class_key,
        cast(substr(m.month, 1, 4) || '-' || substr(m.month, 6, 2) || '-01' as date) as period,
        'flow_extreme_outflow' as anomaly_type,
        'warn' as severity,
        m.net_flow_yield as metric_value,
        {{ var('max_outflow_yield', -0.10) }} as threshold,
        'mart_compartment_monthly_performance' as source,
        'Net outflows above limit over average patrimonio' as description
    from
        {{ ref('mart_compartment_monthly_performance') }} as m
    inner join {{ ref('dim_compartment') }} as c
        on c.compartment_id = m.compartment_id
    where
        m.net_flow_yield < {{ var('max_outflow_yield', -0.10) }}
),

all_anomalies as (
    select * from nav_anomalies
    union all select * from quality_anomalies
    union all select * from stale_anomalies
    union all select * from recon_anomalies
    union all select * from fee_anomalies
    union all select * from flow_anomalies
)

select
    '{{ var("as_of_period") }}' as as_of_period,
    f.fund_id,
    cp.compartment_id,
    cl.class_id,
    a.period,
    a.anomaly_type,
    a.severity,
    a.metric_value,
    a.threshold,
    a.source,
    a.description
from
    all_anomalies as a
left join {{ ref('dim_fund') }} as f
    on f.fund_key = a.fund_key
left join {{ ref('dim_compartment') }} as cp
    on cp.compartment_key = a.compartment_key
left join {{ ref('dim_class') }} as cl
    on cl.class_key = a.class_key
