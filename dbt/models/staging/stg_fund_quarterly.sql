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

    ComisionGestion / 100.0 as management_fee_rate,
    BaseCalculo_ComisionGestion as management_fee_base,
    ComisionDepositario / 100.0 as depositary_fee_rate,
    SistemaImputacionComisiones as fee_imputation_system,
    ComisionSuscripcionMaxima / 100.0 as subscription_fee_max_rate,
    ComisionSuscripcionMinima / 100.0 as subscription_fee_min_rate,
    ComisionReembolsoMaxima / 100.0 as redemption_fee_max_rate,
    ComisionReembolsoMinima / 100.0 as redemption_fee_min_rate,
    ComisionDescuentoFavorFondoMaxima / 100.0 as discount_fee_max_rate,
    ComisionDescuentoFavorFondoMinima / 100.0 as discount_fee_min_rate,

    Rentabilidad_TrimestreActual / 100.0 as return_quarter_rate,
    Rentabilidad_T_1 / 100.0 as return_t1_rate,
    Rentabilidad_T_2 / 100.0 as return_t2_rate,
    Rentabilidad_T_3 / 100.0 as return_t3_rate,
    PeriodicidadCalculoVL as nav_frequency,
    Volatilidad_TrimestreActual / 100.0 as volatility_quarter_rate,
    Volatilidad_T_1 / 100.0 as volatility_t1_rate,
    Volatilidad_T_2 / 100.0 as volatility_t2_rate,
    Volatilidad_T_3 / 100.0 as volatility_t3_rate,

    RatioTotalGastos_TrimestreActual / 100.0 as total_expense_ratio_quarter_rate,
    RatioTotalGastos_T_1 / 100.0 as total_expense_ratio_t1_rate,
    RatioTotalGastos_T_2 / 100.0 as total_expense_ratio_t2_rate,
    RatioTotalGastos_T_3 / 100.0 as total_expense_ratio_t3_rate,

    Tipo || '|' || cast(NumeroRegistro as varchar) as fund_key,
    Tipo || '|' || cast(NumeroRegistro as varchar) || '|' || cast(NumeroCompartimento as varchar) as compartment_key,
    Tipo || '|' || cast(NumeroRegistro as varchar) || '|' || cast(NumeroCompartimento as varchar) || '|' || cast(NumeroClase as varchar) as class_key
from source