-- Regression test: the downside deviation must be the root mean square of the
-- negative excess returns over the weeks that HAVE an excess return.
-- DuckDB's least(NULL, 0) returns 0, which once counted missing weeks as zero
-- downside and overstated the Sortino. This recomputes it with an explicit sum
-- and count, so a NULL can never be turned into a zero.
with expected as (
    select
        class_key,
        sqrt(
            sum(case when ret_w is not null and mar_w is not null
                     then power(least(ret_w - mar_w, 0), 2) end)
            / nullif(count(case when ret_w is not null and mar_w is not null then 1 end), 0)
        ) * sqrt(52) as downside_dev
    from {{ ref('int_weekly_nav_returns') }}
    group by class_key
)

select
    m.class_key,
    m.downside_dev as model_value,
    e.downside_dev as expected_value
from {{ ref('int_class_metrics') }} as m
inner join expected as e
    on e.class_key = m.class_key
where abs(m.downside_dev - e.downside_dev) > 1e-12
   or (m.downside_dev is null) <> (e.downside_dev is null)
