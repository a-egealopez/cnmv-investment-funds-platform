with periods as (

    -- All reported portfolio periods up to the as-of period. FONDCART is
    -- semestral (06 and 12); keeping every period enables portfolio evolution.
    select
        cast(period as varchar) as holdings_period,
        cast(strptime(cast(period as varchar) || '01', '%Y%m%d') as date)
            as month_start,
        cast(last_day(
            cast(strptime(cast(period as varchar) || '01', '%Y%m%d') as date)
        ) as date) as month_end
    from (
        select distinct period
        from {{ ref('stg_fund_holdings') }}
        where period <= {{ current_as_of_period() }}
    ) as p

),

period_reference as (

    -- Reference date for portfolio/AUM comparison: last calendar day available
    -- in dim_date on or before the period end. The portfolio is semestral and
    -- AUM daily, so both must be measured at the same instant.
    select
        p.holdings_period,
        p.month_start,
        p.month_end,
        (
            select max(d.date_day)
            from {{ ref('dim_date') }} as d
            where d.date_day <= p.month_end
        ) as reference_date
    from periods as p

),

positions as (

    select
        h.compartment_key,
        h.period as holdings_period,
        h.isin,
        h.asset_if_class as clase_if,
        h.asset_if_description as descripcion_if,
        h.asset_description,
        h.position_value,

        -- Clave de instrumento. XXXXXXXXXXXX es un sentinel de CNMV, no un ISIN:
        -- 148 lines across 26 compartments use this for 22 distinct instruments.
        -- Using a literal key would introduce extra instruments and bias the HHI.
        case
            when h.isin is not null and h.isin <> 'XXXXXXXXXXXX' then 'ISIN|' || h.isin
            when h.asset_description is not null
                then 'CLASE|' || h.asset_if_class || '|' || h.asset_if_description || '|' || h.asset_description
            else 'CLASE|' || h.asset_if_class || '|' || h.asset_if_description
        end as instrument_key

    from {{ ref('stg_fund_holdings') }} as h
    inner join periods as p
        on p.holdings_period = h.period

),

aggregated as (

-- Aggregates lines for the same instrument within the compartment.
-- Without this, HHI is underestimated: 1,462 instruments have duplicate lines.
    select
        p.compartment_key,
        p.holdings_period,
        p.instrument_key,
        max(p.isin)                    as isin,
        max(p.clase_if)                as clase_if,
        max(p.descripcion_if)         as descripcion_if,
        max(p.asset_description)      as asset_description,
        count(*)                        as n_lines,
        sum(p.position_value)         as position_value,
        sum(case when p.position_value <= 0 then 1 else 0 end) as n_nonpositive
    from positions as p
    group by p.compartment_key, p.holdings_period, p.instrument_key

),

totals as (

    -- Sum of positive-value positions: this is the basis for weights.
    select
        a.compartment_key,
        a.holdings_period,
        sum(case when a.position_value > 0 then a.position_value else 0 end) as total_position_value,
        count(*) filter (where a.position_value > 0) as n_positions,
        sum(a.n_nonpositive) as n_nonpositive
    from aggregated as a
    group by a.compartment_key, a.holdings_period

),

-- Compartment AUM on the SAME date as each portfolio, not as_of_date.
compartment_aum as (

    select
        c.compartment_key,
        r.holdings_period,
        sum(f.aum) as aum
    from {{ ref('fact_nav_daily') }} as f
    inner join {{ ref('dim_class') }} as cl
        on cl.class_id = f.class_id
    inner join {{ ref('dim_date') }} as d
        on d.date_key = f.date_key
    inner join {{ ref('dim_compartment') }} as c
        on c.compartment_id = cl.compartment_id
    inner join period_reference as r
        on d.date_day = r.reference_date
    group by c.compartment_key, r.holdings_period

),

weighted as (

    select
        a.*,
        t.total_position_value,
        t.n_positions,
        t.n_nonpositive,
-- Weight is calculated only on positive-value positions.
-- Non-positive positions are kept with their value and marked, but do not
-- enter the denominator: if they did, the sum of weights would be < 1.
        case
            when a.position_value <= 0 then null
            else a.position_value / nullif(t.total_position_value, 0)
        end as weight,
        t.total_position_value / nullif(c.aum, 0) as coverage_ratio
    from aggregated as a
    inner join totals as t
        on t.compartment_key = a.compartment_key
       and t.holdings_period = a.holdings_period
    left join compartment_aum as c
        on c.compartment_key = a.compartment_key
       and c.holdings_period = a.holdings_period

)

select
    p.compartment_id,
    dd.date_key as date_key,
    w.instrument_key,
    w.isin,
    w.clase_if,
    w.descripcion_if,
    w.asset_description,
    cast(w.position_value as double) as position_value,
    w.n_lines,
    w.weight,
    w.n_positions,
    cast(w.n_nonpositive as bigint) as n_nonpositive,
    w.coverage_ratio,
    w.position_value <= 0 as is_negative,
    -- Rank by weight within the compartment and period; nulls (non-positive
    -- positions) have no rank. Top ten = position_rank <= 10.
    case
        when w.weight is not null then row_number() over (
            partition by p.compartment_id, dd.date_key
            order by w.weight desc, w.instrument_key
        )
    end as position_rank
from weighted as w
inner join {{ ref('dim_compartment') }} as p
    on p.compartment_key = w.compartment_key
inner join period_reference as pr
    on pr.holdings_period = w.holdings_period
inner join {{ ref('dim_date') }} as dd
    on dd.date_day = pr.month_end
