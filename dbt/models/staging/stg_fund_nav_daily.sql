with source as (
    select * from {{ source('silver', 'fund_nav_daily') }}
)

select
    cast(FechaDatos as varchar) as period,
    value_date,
    VL as nav,
    Patrimonio as aum,
    Participes as holders,
    ISIN as isin,
    Tipo as fund_type,
    NumeroRegistro as registration_number,
    NumeroCompartimento as compartment_number,
    NumeroClase as class_number,

    Tipo || '|' || cast(NumeroRegistro as varchar) as fund_key,
    Tipo || '|' || cast(NumeroRegistro as varchar) || '|' || cast(NumeroCompartimento as varchar) as compartment_key,
    Tipo || '|' || cast(NumeroRegistro as varchar) || '|' || cast(NumeroCompartimento as varchar) || '|' || cast(NumeroClase as varchar) as class_key
from source