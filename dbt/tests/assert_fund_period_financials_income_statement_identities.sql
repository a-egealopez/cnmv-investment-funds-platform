{{ config(severity='warn') }}

-- Identidades del estado de resultados de FONDPATRIMDISVAR.
-- Unidad: puntos porcentuales (pp). Los gastos llegan negativos en el XML.
--   GR  = GastosRepercutidos
--   ING = Ingresos
--   RN  = RendimientosNetos
--   RG  = RendimientosGestion
-- La tolerancia 0,05 pp absorbe el redondeo de los componentes a 2 decimales.

with residuals as (
    -- GR: GastosRepercutidos = ComisionGestion + ComisionDepositario
    --     + GastosServiciosExteriores + OtrosGastosGestion + OtrosGastosRepercutidos
    select
        'GR' as identity,
        compartment_key,
        period,
        abs(charged_expenses_pct - (
            management_fee_pct
            + depositary_fee_pct
            + external_services_expenses_pct
            + other_management_expenses_pct
            + other_charged_expenses_pct)
        ) as residual
    from
        {{ ref('fact_fund_period_financials') }}

    union all

    -- ING: Ingresos = ComisionesDescuento + ComisionesRetrocedidas + OtrosIngresos
    select
        'ING' as identity,
        compartment_key,
        period,
        abs(income_pct - (
            discount_commissions_pct
            + retroceded_commissions_pct
            + other_revenues_pct)
        ) as residual
    from
        {{ ref('fact_fund_period_financials') }}

    union all

    -- RN: RendimientosNetos = RendimientosGestion + GastosRepercutidos + Ingresos
    --     (con el signo del XML: GastosRepercutidos ya es negativo)
    select
        'RN' as identity,
        compartment_key,
        period,
        abs(net_return_pct - (
            management_return_pct
            + charged_expenses_pct
            + income_pct)
        ) as residual
    from
        {{ ref('fact_fund_period_financials') }}

    union all

    -- RG: RendimientosGestion = Intereses + Dividendos + ResultadosRentaFija
    --     + ResultadosRentaVariable + ResultadosDepositos + ResultadosDerivados
    --     + ResultadosIIC + OtrosResultados + OtrosRendimientos
    select
        'RG' as identity,
        compartment_key,
        period,
        abs(
            management_return_pct
            - (
                interest_income_pct
                + dividend_income_pct
                + fixed_income_results_pct
                + equity_results_pct
                + deposit_results_pct
                + derivatives_results_pct
                + iic_results_pct
                + other_results_pct
                + other_returns_pct
            )
        ) as residual
    from {{ ref('fact_fund_period_financials') }}
)


select
    *
from
    residuals
where
    residual > 0.05