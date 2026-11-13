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

    Suscripciones_Reembolsos_Netos / 100.0 as net_subscriptions_redemptions_rate,
    BeneficiosBrutosDistribuidos / 100.0 as gross_distributed_profit_rate,
    RendimientosNetos / 100.0 as net_income_rate,
    RendimientosGestion / 100.0 as management_income_rate,
    Intereses / 100.0 as interest_income_rate,
    Dividendos / 100.0 as dividend_income_rate,
    ResultadosRentaFija / 100.0 as fixed_income_results_rate,
    ResultadosRentaVariable / 100.0 as equity_results_rate,
    ResultadosDepositos / 100.0 as deposit_results_rate,
    ResultadosDerivados / 100.0 as derivatives_results_rate,
    ResultadosIIC / 100.0 as iic_results_rate,
    OtrosResultados / 100.0 as other_results_rate,
    OtrosRendimientos / 100.0 as other_returns_rate,

    GastosRepercutidos / 100.0 as charged_expenses_rate,
    ComisionGestion / 100.0 as management_fee_rate,
    ComisionDepositario / 100.0 as depositary_fee_rate,
    GastosServiciosExteriores / 100.0 as external_services_expenses_rate,
    OtrosGastosGestion / 100.0 as other_management_expenses_rate,
    OtrosGastosRepercutidos / 100.0 as other_charged_expenses_rate,
    Ingresos / 100.0 as income_rate,
    ComisionesDescuento / 100.0 as discount_commissions_rate,
    ComisionesRetrocedidas / 100.0 as retroceded_commissions_rate,
    OtrosIngresos / 100.0 as other_revenues_rate,

    Tipo || '|' || cast(NumeroRegistro as varchar) as fund_key,
    Tipo || '|' || cast(NumeroRegistro as varchar) || '|' || cast(NumeroCompartimento as varchar) as compartment_key
from source
