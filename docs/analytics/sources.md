# Data Sources

Last updated: 2026-11-15

## Source

Two official publishers: the **Comisión Nacional del Mercado de Valores (CNMV)**, source of all fund data, and the **European Central Bank (ECB)**, source of the risk-free rate.

## Datasets

### 1. FONDMENS: Monthly Fund Messaging

| Field | Description |
|-------|-------------|
| Origin | CNMV, Descarga de ficheros de información individual de IIC |
| URL | https://www.cnmv.es/portal/publicaciones/descarga-informacion-individual |
| Format | ZIP with XML + XSD + explanatory PDF |
| Frequency | Monthly |
| Volume | ~15 MB per period |
| Structure | `FondMens > FechaDatos > Entidad > Compartimento > Clase > VLDiario / ParticipesDiario / PatrimonioDiario` |
| Key fields | ISIN, Tipo (FI/FHF/SICAV/SHF), NumeroRegistro, VL_Dia1..31, Participes_Dia1..31, Patrimonio_Dia1..31 |
| Use | Daily NAV time series, return and volatility calculation, fund screening |

### 2. FONDREGISTRO: Fund Registration Metadata

| Field | Description |
|-------|-------------|
| Origin | CNMV, Descarga de ficheros de información individual de IIC |
| URL | https://www.cnmv.es/portal/publicaciones/descarga-informacion-individual |
| Format | ZIP with XML + XSD + explanatory PDF |
| Frequency | Monthly |
| Volume | ~2 MB per period |
| Structure | `FondRegistro > FechaDatos > Entidad > Tipo, NumeroRegistro, Denominacion, ETF, Compartimento, Clase, Gestora, Depositario` |
| Key fields | Denominacion, ISIN, ETF, TipoGestora, DenominacionGestora, GrupoGestora, DenominacionDepositario, GrupoDepositario |
| Use | Fund metadata: managers, depositaries, share classes, ISINs |

### 3. FONDTRIM: Periodic Fund Statements

| Field | Description |
|-------|-------------|
| Origin | CNMV, Descarga de ficheros de información individual de IIC (same portal as above) |
| Format | ZIP with XML + XSD + explanatory PDF |
| Frequency | Quarterly until 2022, semiannual (06/12) from 2023; Silver keeps 06/12. Each file reports the current quarter and the three previous ones (`t1`–`t3`), so the semiannual files still cover every quarter from 2020-Q1 |
| Structure | `FondTrim > FechaDatos > Entidad > Compartimento > Clase`; entity level: `CodigoDivisaIIC`; compartment level: `VocacionInversora`, `ClaseFondo`; class level: financial metrics |
| Key fields | AUM, participants/shares, VL, commissions (management/custody), official returns, `Volatilidad_T_x`, `RatioTotalGastos_T_x` (current quarter and T-1..3) |
| Use | Peer group (investor vocation), currency filter, official-volatility contrast, fee-rate cross-check |

### 4. FONDCART: Portfolio Composition

| Field | Description |
|-------|-------------|
| Origin | CNMV, Descarga de ficheros de información individual de IIC (same portal as above) |
| Format | ZIP with XML + XSD + explanatory PDF |
| Frequency | Quarterly until 2022, semiannual (06/12) from 2023; Silver keeps 06/12. ~103k positions / ~39 MB per file |
| Structure | Portfolio defined **per compartment**; one line per position |
| Key fields | `ClaseIF` (asset category, ~12 reported values), `DescripcionIF`, `CodigoISIN` (can be null), `DescripcionValor`, `Divisa` (underlying asset currency), `ValorMercado` (market value in **euros**, verified via coverage median ≈ 0.96) |
| Use | Concentration (HHI, effective N, top-10) and portfolio composition |

### 5. FONDPATRIMDISVAR: Patrimony and P&L Variations

| Field | Description |
|-------|-------------|
| Origin | CNMV, Descarga de ficheros de información individual de IIC |
| Format | ZIP with XML + XSD + explanatory PDF |
| Frequency | Quarterly until 2022, semiannual (06/12) from 2023; Silver keeps 06/12 |
| Universe | FI only; compartment level |
| Structure | `FondPatrimDisVar > FechaDatos > Entidad > Compartimento` with patrimony distribution and P&L variation items; `NumeroCompartimento = 0` when the IIC has no compartments |
| Key fields | Distribution: `DPInversionesFinancieras`, `CarteraInterior`, `CarteraExterior`, `InteresesCartera`, `InversionesDudosas`, `Liquidez`, `Resto`, `TotalPatrimonio`; expenses: `GastosRepercutidos`, `ComisionGestion`, `ComisionDepositario`, `GastosServiciosExteriores`, `OtrosGastosGestion`, `OtrosGastosRepercutidos`; income: `ComisionesDescuento`, `ComisionesRetrocedidas`, `OtrosIngresos`; flows: `Suscripciones_Reembolsos_Netos`; returns: `RendimientosGestion`, `RendimientosNetos`; `IndiceRotacionCarteraActual`; `BeneficiosBrutosDistribuidos`; opening/closing patrimony |
| Units | Variation fields (from `PatrimonioFinPeriodoAnterior` to `PatrimonioFinPeriodoActual`, except the two patrimony fields) are **% of average daily patrimony, cumulative since the previous year-end**. Distribution fields and the two patrimony fields are monetary amounts in the fund currency. Expenses are negative. |
| Use | AUM flow bridge, fee/income decomposition, net return, turnover, quality and anomalies |

**Limitation:** FONDPATRIMDISVAR has no separate success-fee field and only net subscriptions/redemptions; gross churn cannot be computed from it.

**Profiling evidence:** `notebooks/exploration/03_fondpatrimdisvar__financial_contract_profiling.ipynb` (6 closures, 10,237 rows; nullability, signs, units, identities and cross-check against daily NAV).

### 6. ECB €STR: Compounded Euro Short-Term Rate

| Field | Description |
|-------|-------------|
| Origin | European Central Bank, Data Portal |
| URL (API) | `https://data-api.ecb.europa.eu/service/data/EST/{key}?startPeriod=…&endPeriod=…&format=csvdata` |
| Series | Index: `B.EU000A2QQF08.CI` (compounded index, base 100 on 2019-10-01); rate: `B.EU000A2QQF16.CR` (% rate, contrast series) |
| Format | CSV (`KEY`, `TIME_PERIOD`, `OBS_VALUE`, `OBS_STATUS`) |
| Frequency | Daily (TARGET business days), published 09:15 CET |
| Use | Weekly risk-free return used as the minimum acceptable return in the Sortino ratio |

### 7. IPP per-Fund: Periodic Public Information (future)

| Field | Description |
|-------|-------------|
| Origin | CNMV, per-fund consultation portal |
| URL | https://www.cnmv.es/portal/Consultas/IIC/Fondo.aspx?nreg={NUMERO_REGISTRO} |
| Format | XML (per-fund download) + explanatory PDF |
| Frequency | Semiannual / Annual |
| Structure | Holdings, portfolio composition, sector allocation, transactions |
| Use | Future: deeper holdings detail. Not ingested: portfolio analysis uses FONDCART, which is bulk-downloadable |

## Relationships

```
FONDREGISTRO (nreg, ISIN, metadata) → FONDMENS (daily time series)
FONDTRIM (vocacion, currency, fees) ← compartment/entity keys → FONDMENS
FONDPATRIMDISVAR (flows, fees, net return) ← compartment keys → FONDMENS/FONDTRIM
FONDCART (positions per compartment) → FONDMENS (coverage vs AUM)
ECB €STR → independent series, joined on date in dbt
```

Business keys: `Tipo + NumeroRegistro + NumeroCompartimento + NumeroClase` (class) · `compartment_key` = first three · `entity_key` = first two.

## Temporal Availability

- CNMV offers data from 2012; **this project's Silver range is 202001–202608** (80 monthly periods) for FONDMENS/FONDREGISTRO, and 202006–202606 (13 semiannual closures) for FONDTRIM/FONDCART/FONDPATRIMDISVAR.
- **Cadence change in 2023**: CNMV published FONDTRIM/FONDCART/FONDPATRIMDISVAR quarterly until 2022 (03/06/09/12; the 202109 archive contains none of the three) and semiannually from 2023 (06/12). Silver keeps only the 06/12 closings for one homogeneous series (`spark/common/cadence.py`); the 03/09 files stay in Bronze. The XSDs are identical across 2020 and 2023. No quarterly metric is lost: FONDTRIM reports four quarters per file, so `fact_fund_quarterly_metrics` has all 26 quarters from 2020-Q1 to 2026-Q2. What the 03/09 files alone would add is the point-in-time data at those dates (2020–2022 only): holdings, the year-to-date P&L and the FONDTRIM AUM cross-check.
- €STR index series starts 2019-10-01.

## Usage Conditions

- Official public data, free to access. No raw data is committed to this repository; the pipeline downloads it from the source.
- Traceability must be maintained (origin, download date, file hash).
- Source regulation: CNMV Circular 4/2008 (periodic reporting); asset statement requirements in CNMV Circular 3/2008.

## Regulatory References

References backing project decisions:

- [CNMV: Investor vocation of funds](https://www.cnmv.es/portal/inversor/fondos-vocacion). Peer-group definition.
- [Circular CNMV 1/2009 (BOE)](https://boe.es/buscar/act.php?id=BOE-A-2009-2742). IIC regulation backing vocation semantics.
- [Reglamento de IIC, art. 3](https://papelea.com/es/leyes/reglamento-de-instituciones-de-inversion-colectiva/titulo-i_capitulo-i). Minimum participants: 100 per fund, 20 per compartment.
- [Reglamento de IIC, full text (art. 76)](https://www.inverco.es/archivosdb/riic-texto-web-octubre2015.pdf). Minimum patrimony.
- [CNMV: Traspasos entre fondos](https://www.cnmv.es/DocPortal/Publicaciones/Fichas/TraspasosEntreFondosDeInversion.pdf). Tax deferral context for dividend handling.
- [CNMV: Circular 3/2008 (asset statement requirements)](https://www.cnmv.es/DocPortal/Legislacion/Circulares/Circular_3_2008_Req_IICmobiliarias.pdf). Statements managers report to CNMV; context for FONDPATRIMDISVAR and FONDDERI.
