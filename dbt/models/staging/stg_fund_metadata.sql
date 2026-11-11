with source as (
    select * from {{ source('silver', 'fund_metadata') }}
)

select
    cast(FechaDatos as varchar) as period,
    Tipo as fund_type,
    NumeroRegistro as registration_number,
    Denominacion as fund_name,
    ETF as is_etf,
    NumeroCompartimento as compartment_number,
    DenominacionCompartimento as compartment_name,
    NumeroClase as class_number,
    ISIN as isin,
    DenominacionClase as class_name,
    NumeroRegistroGestora as manager_registration_number,
    DenominacionGestora as manager_name,
    TipoGestora as manager_type,
    DenominacionGrupoGestora as manager_group_name,
    DenominacionDepositario as depositary_name,
    NumeroRegistroDepositario as depositary_registration_number,
    DenominacionGrupoDepositario as depositary_group_name,

    Tipo || '|' || cast(NumeroRegistro as varchar) as fund_key,
    Tipo || '|' || cast(NumeroRegistro as varchar) || '|' || cast(NumeroCompartimento as varchar) as compartment_key,
    Tipo || '|' || cast(NumeroRegistro as varchar) || '|' || cast(NumeroCompartimento as varchar) || '|' || cast(NumeroClase as varchar) as class_key
from source