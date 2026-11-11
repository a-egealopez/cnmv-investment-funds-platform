with source as (
    select * from {{ source('silver', 'fund_period_financials')}}
)

select
    cast(FechaDatos as varchar) as period,
    Tipo as fund_type,
    NumeroRegistro as registration_number,
    CodigoDivisaIIC as icc_currency_code,
    NumeroCompartimento as compartment_number,

    IndiceRotacionCarteraActual as portfolio_turnover_current,
    IndiceRotacionCarteraAnterior as portfolio_turnover_previous,

    DPInversionesFinancieras as financial_investments,
    CarteraInterior as domestic_portfolio,
    CarteraExterior as foreign_portfolio,
    InteresesCartera as portfolio_interest,
    InversionesDudosas as doubtful_investments,
    Liquidez as cash,
    Resto as other_assets,
    TotalPatrimonio as total_patrimony,
    PatrimonioFinPeriodoAnterior as patrimony_previous_period,
    PatrimonioFinPeriodoActual as patrimony_current_period,

    Suscripciones_Reembolsos_Netos as net_subscriptions_redemptions_pct,
    BeneficiosBrutosDistribuidos as gross_distributed_profit_pct,
    RendimientosNetos as net_income_pct,
    RendimientosGestion as management_income_pct,
    Intereses as interest_income_pct,
    Dividendos as dividend_income_pct,
    ResultadosRentaFija as fixed_income_results_pct,
    ResultadosRentaVariable as equity_results_pct,
    ResultadosDepositos as deposit_results_pct,
    ResultadosDerivados as derivatives_results_pct,
    ResultadosIIC as iic_results_pct,
    OtrosResultados as other_results_pct,
    OtrosRendimientos as other_returns_pct,

    GastosRepercutidos as charged_expenses_pct,
    ComisionGestion as management_fee_pct,
    ComisionDepositario as depositary_fee_pct,
    GastosServiciosExteriores as external_services_expenses_pct,
    OtrosGastosGestion as other_management_expenses_pct,
    OtrosGastosRepercutidos as other_charged_expenses_pct,
    Ingresos as income_pct,
    ComisionesDescuento as discount_commissions_pct,
    ComisionesRetrocedidas      as retroceded_commissions_pct,
    OtrosIngresos               as other_revenues_pct,

    Tipo || '|' || cast(NumeroRegistro as varchar) as fund_key,
    Tipo || '|' || cast(NumeroRegistro as varchar) || '|' || cast(NumeroCompartimento as varchar) as compartment_key
from source
