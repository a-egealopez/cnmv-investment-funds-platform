-- The 5-year window contains the 3-year one and its running peak can only be
-- higher, so a class's 5-year max drawdown can never be below its 3-year one.
-- A violation means the two horizons stopped sharing the same daily series.
select
    m.class_key,
    m.max_drawdown as max_drawdown_3y,
    m5.max_drawdown as max_drawdown_5y
from {{ ref('int_class_metrics') }} as m
inner join {{ ref('int_class_metrics_5y') }} as m5
    on m5.class_key = m.class_key
where m5.max_drawdown < m.max_drawdown - 1e-12
