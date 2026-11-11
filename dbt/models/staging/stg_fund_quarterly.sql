with source as (
    select * from {{ source('silver', 'fund_quarterly') }}
)

select
    cast(FechaDatos as varchar) as period,
    Tipo as fund_type,
    NumeroRegistro as registration_number,
    CodigoDivisaIIC as iic_currency_code,
    NumeroCompartimento as compartment_number,
    VocacionInversora as vocation,
    ClaseFondo as fund_class,
    NumeroClase as class_number,
    ISIN as isin,
    CodigoDivisa as class_currency_code,
    NumeroParticipes as participants,
    NumeroParticipaciones as units,
    Beneficio_Dividendo_Bruto as gross_dividend,
    Patrimonio as aum,
    ValorLiquidativo as nav,

    ComisionGestion as management_fee_pct,
    BaseCalculo_ComisionGestion as management_fee_base,
    ComisionDepositario as depositary_fee_pct,
    SistemaImputacionComisiones as fee_imputation_system,
    ComisionSuscripcionMaxima as subscription_fee_max_pct,
    ComisionSuscripcionMinima as subscription_fee_min_pct,
    ComisionReembolsoMaxima as redemption_fee_max_pct,
    ComisionReembolsoMinima as redemption_fee_min_pct,
    ComisionDescuentoFavorFondoMaxima as discount_fee_max_pct,
    ComisionDescuentoFavorFondoMinima as discount_fee_min_pct,

    Rentabilidad_TrimestreActual as return_quarter_pct,
    Rentabilidad_T_1 as return_t1_pct,
    Rentabilidad_T_2 as return_t2_pct,
    Rentabilidad_T_3 as return_t3_pct,
    PeriodicidadCalculoVL as nav_frequency,
    Volatilidad_TrimestreActual as volatility_quarter_pct,
    Volatilidad_T_1 as volatility_t1_pct,
    Volatilidad_T_2 as volatility_t2_pct,
    Volatilidad_T_3 as volatility_t3_pct,

    RatioTotalGastos_TrimestreActual as total_expense_ratio_quarter_pct,
    RatioTotalGastos_T_1 as total_expense_ratio_t1_pct,
    RatioTotalGastos_T_2 as total_expense_ratio_t2_pct,
    RatioTotalGastos_T_3 as total_expense_ratio_t3_pct,

    Tipo || '|' || cast(NumeroRegistro as varchar) as fund_key,
    Tipo || '|' || cast(NumeroRegistro as varchar) || '|' || cast(NumeroCompartimento as varchar) as compartment_key,
    Tipo || '|' || cast(NumeroRegistro as varchar) || '|' || cast(NumeroCompartimento as varchar) || '|' || cast(NumeroClase as varchar) as class_key
from source