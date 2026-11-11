{{ config(severity='warn') }}

-- Identidades del balance de FONDPATRIMDISVAR. Unidad: EUR.
--   IF = InversionesFinancieras
--   CI = CarteraInterior
--   CE = CarteraExterior
--   IC = InteresesCartera
--   ID = InversionesDudosas
--   TP = TotalPatrimonio
--   L  = Liquidez
--   R  = Resto
-- Tolerancia: 2.000 € fijos como umbral de materialidad, no de precisión.
-- La fuente publica euros con 2 decimales; el máximo residual no material
-- observado es 2.000 € (6 filas), y la única excepción material es 1,68 bn €.

with residuals as (
    -- IF: InversionesFinancieras = CarteraInterior + CarteraExterior
    --     + InteresesCartera + InversionesDudosas
    select
        'IF = CI + CE + IC + ID' as identity,
        compartment_key,
        period,
        abs(financial_investments - (
            domestic_portfolio
            + foreign_portfolio
            + portfolio_interest
            + doubtful_investments)
        ) as residual
    from {{ ref('fact_fund_period_financials') }}

    union all

    -- TP: TotalPatrimonio = InversionesFinancieras + Liquidez + Resto.
    --     No se comprueba TP = PatrimonioFinPeriodoActual porque no es una
    --     identidad estable en la fuente.
    select
        'TP = IF + L + R' as identity,
        compartment_key,
        period,
        abs(total_patrimony - (
            financial_investments
            + cash
            + other_assets)
        ) as residual
    from {{ ref('fact_fund_period_financials') }}
)


select
    *
from
    residuals
where
    residual > 2000