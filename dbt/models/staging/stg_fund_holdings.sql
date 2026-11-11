with source as (
    select * from {{ source('silver', 'fund_holdings')}}
)

select
    cast(FechaDatos as varchar) as period,
    Tipo as fund_type,
    NumeroRegistro as registration_number,
    NumeroCompartimento as compartment_number,

    ClaseIF as asset_if_class,
    DescripcionIF as asset_if_description,
    CodigoISIN as isin,
    DescripcionValor as asset_description,
    Divisa as asset_currency,
    ValorMercado as position_value,

    Tipo || '|' || cast(NumeroRegistro as varchar) as fund_key,
    Tipo || '|' || cast(NumeroRegistro as varchar) || '|' || cast(NumeroCompartimento as varchar) as compartment_key
from source