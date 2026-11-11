with staging as (
    select count(*) as n from {{ ref('stg_fund_nav_daily') }}
),

fact as (
    select count(*) as n from {{ ref('fact_nav_daily') }}
),

quarantine as (
    select count(*) as n from {{ ref('quarantine_nav_daily') }}
)

select
    staging.n as staging_rows,
    fact.n as fact_rows,
    quarantine.n as quarantine_rows
from staging, fact, quarantine
where staging.n <> fact.n + quarantine.n
