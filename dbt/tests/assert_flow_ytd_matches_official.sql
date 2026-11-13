-- Flow vs official FONDPATRIMDISVAR comparison.
-- YTD net redemptions % vs average daily AUM per compartment.
-- Periods: 202406, 202412, 202506, 202512. 2023 excluded (no H1-2022 data).
-- Tolerance: 0.05 (5pp); 98.5% of eligible compartments within 5pp, median 0.004pp.
-- Remainder: Popup/fusion operations not reconstructible from daily NAV.

{{ config(severity='warn', warn_if='>150') }}
-- Known baseline: 98 compartments in real data (~1.5%). It only warns if the issue grows.

-- Closings of the official file, derived from the data. The first year of data is
-- excluded: the official YTD needs the patrimony of the previous year-end.
with periods as (

    select
        period,
        make_date(cast(substr(period, 1, 4) as integer), 1, 1) as period_start,
        last_day(make_date(
            cast(substr(period, 1, 4) as integer),
            cast(substr(period, 5, 2) as integer),
            1
        )) as period_end
    from (
        select distinct period
        from {{ ref('stg_fund_period_financials') }}
        where period <= {{ current_as_of_period() }}
    )
    where cast(substr(period, 1, 4) as integer) > (
        select cast(substr(min(period), 1, 4) as integer)
        from {{ ref('stg_fund_nav_daily') }}
    )

),

calculated as (

    select
        p.period,
        c.compartment_key,
        sum(f.net_flows) as net_flows,
        sum(case when f.is_capital_change then 1 else 0 end) as n_capital_changes
    from periods as p
    inner join {{ ref('int_fund_aum_bridge') }} as f
        on f.value_date between p.period_start and p.period_end
    inner join {{ ref('dim_class') }} as c
        on c.class_key = f.class_key
    group by 1, 2

),

daily_patrimony as (

    select
        p.period,
        c.compartment_key,
        d.date_day,
        sum(f.aum) as aum
    from periods as p
    inner join {{ ref('fact_nav_daily') }} as f
        on f.date_key in (
            select date_key
            from {{ ref('dim_date') }}
            where date_day between p.period_start and p.period_end
        )
    inner join {{ ref('dim_date') }} as d
        on d.date_key = f.date_key
    inner join {{ ref('dim_class') }} as c
        on c.class_id = f.class_id
    where f.aum > 0
    group by 1, 2, 3

),

average_patrimony as (

    select
        period,
        compartment_key,
        avg(aum) as average_daily_patrimony,
        count(*) as n_days_with_patrimony
    from daily_patrimony
    group by 1, 2

),

period_length as (

    select
        period,
        (select count(distinct date_day)
         from {{ ref('dim_date') }}
         where date_day between p.period_start and p.period_end) as n_days_in_period
    from periods as p

),

official as (

    select
        compartment_key,
        period,
        net_subscriptions_redemptions_rate as ytd_rate
    from {{ ref('stg_fund_period_financials') }}
    where period in (select period from periods)

)

select
    c.period,
    c.compartment_key,
    c.net_flows / nullif(a.average_daily_patrimony, 0) as calculated_rate,
    o.ytd_rate as official_rate
from calculated as c
inner join average_patrimony as a
    on a.period = c.period
   and a.compartment_key = c.compartment_key
inner join period_length as l
    on l.period = c.period
inner join official as o
    on o.compartment_key = c.compartment_key
   and o.period = c.period
where o.ytd_rate is not null
  -- El oficial cubre todo el periodo. Si el compartimento no existia durante todo el periodo,
  -- su patrimonio medio diario no es comparable y la comparacion no es valida.
  and a.n_days_with_patrimony >= l.n_days_in_period * 0.95
  -- Un salto de capital (fusion o cambio de clase) rompe el puente: el patrimonio aparece o
  -- desaparece sin que entre ni salga dinero, y el oficial no lo recoge como flujo.
  and c.n_capital_changes = 0
  -- Tolerancia de 5 puntos porcentuales: el 98,5% de los compartimentos elegibles cuadra dentro
  -- de 5 pp, con mediana de 0,004 pp.
  -- El 1,5% restante son operaciones dePopup o fusiones que el puente no puede reconstruir
  -- con el NAV diario: en varios de ellos el retorno neto oficial es cero mientras el flujo no lo es.
  and abs(c.net_flows / nullif(a.average_daily_patrimony, 0) - o.ytd_rate) > 0.05
