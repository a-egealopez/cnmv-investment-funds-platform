# Data Sources

Last updated: 2026-10-30

## Source

**Comisión Nacional del Mercado de Valores (CNMV)** — official public data on Spanish Collective Investment Schemes (IIC) — and the **European Central Bank (ECB)** for the risk-free benchmark series.

## Datasets

### 1. FONDMENS — Monthly Fund Messaging

| Field | Description |
|-------|-------------|
| **Origin** | CNMV — Descarga de ficheros de información individual de IIC |
| **URL** | https://www.cnmv.es/portal/publicaciones/descarga-informacion-individual |
| **Format** | ZIP with XML + XSD + explanatory PDF |
| **Frequency** | Monthly |
| **Volume** | ~15 MB per period; universe 1,438 entities / 3,116 classes |
| **Structure** | `FondMens > FechaDatos > Entidad > Compartimento > Clase > VLDiario / ParticipesDiario / PatrimonioDiario` |
| **Key fields** | ISIN, Tipo (FI/FHF/SICAV/SHF), NumeroRegistro, VL_Dia1..31, Participes_Dia1..31, Patrimonio_Dia1..31 |
| **Use** | Daily NAV time series, return and volatility calculation, fund screening |

### 2. FONDREGISTRO — Fund Registration Metadata

| Field | Description |
|-------|-------------|
| **Origin** | CNMV — Descarga de ficheros de información individual de IIC |
| **URL** | https://www.cnmv.es/portal/publicaciones/descarga-informacion-individual |
| **Format** | ZIP with XML + XSD + explanatory PDF |
| **Frequency** | Monthly |
| **Volume** | ~2 MB per period |
| **Structure** | `FondRegistro > FechaDatos > Entidad > Tipo, NumeroRegistro, Denominacion, ETF, Compartimento, Clase, Gestora, Depositario` |
| **Key fields** | Denominacion, ISIN, ETF, TipoGestora, DenominacionGestora, GrupoGestora, DenominacionDepositario, GrupoDepositario |
| **Use** | Fund metadata: managers, depositaries, share classes, ISINs |

### 3. FONDTRIM — Semiannual Fund Statements

| Field | Description |
|-------|-------------|
| **Origin** | CNMV — Descarga de ficheros de información individual de IIC (same portal as above) |
| **Format** | ZIP with XML + XSD + explanatory PDF |
| **Frequency** | Semiannual — only months 06 and 12 (verified in Bronze: 202303/202309 zips contain no FONDTRIM) |
| **Structure** | `FondTrim > FechaDatos > Entidad > Compartimento > Clase`; entity level: `CodigoDivisaIIC`; compartment level: `VocacionInversora`, `ClaseFondo`; class level: financial metrics |
| **Key fields** | AUM, participants/shares, VL, commissions (management/custody), official returns, `Volatilidad_T_x`, `RatioTotalGastos_T_x` (current quarter and T-1..3) |
| **Use** | Peer group (investor vocation), currency filter, official-volatility contrast, fee-rate cross-check |

### 4. FONDCART — Semiannual Portfolio Composition

| Field | Description |
|-------|-------------|
| **Origin** | CNMV — Descarga de ficheros de información individual de IIC (same portal as above) |
| **Format** | ZIP with XML + XSD + explanatory PDF |
| **Frequency** | Semiannual (months 06/12); ~103k positions / ~39 MB per file |
| **Structure** | Portfolio defined **per compartment**; one line per position |
| **Key fields** | `ClaseIF` (asset category, ~12 reported values), `DescripcionIF`, `CodigoISIN` (can be null), `DescripcionValor`, `Divisa` (underlying asset currency), `ValorMercado` (market value in **euros**, verified via coverage median ≈ 0.96) |
| **Use** | Concentration (HHI, effective N, top-10) and portfolio composition |

### 5. FONDPATRIMDISVAR — Patrimony and P&L Variations

| Field | Description |
|-------|-------------|
| **Origin** | CNMV — Descarga de ficheros de información individual de IIC |
| **Format** | ZIP with XML + XSD + explanatory PDF |
| **Frequency** | Nominal quarterly (03/06/09/12); **observed 06/12** in every downloaded CNMV archive 2023–2025 |
| **Universe** | FI only; compartment level |
| **Structure** | `FondPatrimDisVar > FechaDatos > Entidad > Compartimento` with patrimony distribution and P&L variation items; `NumeroCompartimento = 0` when the IIC has no compartments |
| **Key fields** | Distribution: `DPInversionesFinancieras`, `CarteraInterior`, `CarteraExterior`, `InteresesCartera`, `InversionesDudosas`, `Liquidez`, `Resto`, `TotalPatrimonio`; expenses: `GastosRepercutidos`, `ComisionGestion`, `ComisionDepositario`, `GastosServiciosExteriores`, `OtrosGastosGestion`, `OtrosGastosRepercutidos`; income: `ComisionesDescuento`, `ComisionesRetrocedidas`, `OtrosIngresos`; flows: `Suscripciones_Reembolsos_Netos`; returns: `RendimientosGestion`, `RendimientosNetos`; `IndiceRotacionCarteraActual`; `BeneficiosBrutosDistribuidos`; opening/closing patrimony |
| **Units** | Variation fields (from `PatrimonioFinPeriodoAnterior` to `PatrimonioFinPeriodoActual`, except the two patrimony fields) are **% of average daily patrimony, cumulative since the previous year-end**. Distribution fields and the two patrimony fields are monetary amounts in the fund currency. Expenses are negative. |
| **Use** | AUM flow bridge, fee/income decomposition, net return, turnover, quality and anomalies (D19–D23) |

**Limitation:** FONDPATRIMDISVAR has no separate success-fee field and only net subscriptions/redemptions; gross churn cannot be computed from it.

**Profiling evidence:** `notebooks/exploration/03_fondpatrimdisvar__financial_contract_profiling.ipynb` (6 closures, 10,237 rows; nullability, signs, units, identities and cross-check against daily NAV).

### 6. ECB €STR — Compounded Euro Short-Term Rate

| Field | Description |
|-------|-------------|
| **Origin** | European Central Bank — Data Portal |
| **URL (API)** | `https://data-api.ecb.europa.eu/service/data/EST/{key}?startPeriod=…&endPeriod=…&format=csvdata` |
| **Series** | Index: `B.EU000A2QQF08.CI` (compounded index, base 100 on 2019-10-01); rate: `B.EU000A2QQF16.CR` (% rate, contrast series) |
| **Format** | CSV (`KEY`, `TIME_PERIOD`, `OBS_VALUE`, `OBS_STATUS`) |
| **Frequency** | Daily (TARGET business days), published 09:15 CET |
| **Use** | Risk-free rate over the analysis window (`rf_window`) |

### 7. IPP per-Fund — Periodic Public Information (future)

| Field | Description |
|-------|-------------|
| **Origin** | CNMV — Per-fund consultation portal |
| **URL** | https://www.cnmv.es/portal/Consultas/IIC/Fondo.aspx?nreg={NUMERO_REGISTRO} |
| **Format** | XML (per-fund download) + explanatory PDF |
| **Frequency** | Semiannual / Annual |
| **Structure** | Holdings, portfolio composition, sector allocation, transactions |
| **Use** | Future: deeper holdings detail. **Not currently ingested** — portfolio analysis uses FONDCART, which is bulk-downloadable |

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

- CNMV offers data from 2012; **this project's Silver range is 202301–202605** (41 monthly periods) for FONDMENS/FONDREGISTRO, and 202306–202512 (6 closures) for FONDTRIM/FONDCART/FONDPATRIMDISVAR. FONDPATRIMDISVAR is documented as quarterly, but the downloaded zips only contain 06/12; no 03/09 files are available in this archive.
- €STR index series starts 2019-10-01.

## Usage Conditions

- Official public data; free, no usage restrictions (conditions to be re-checked before versioning any data sample).
- Traceability must be maintained (origin, download date, file hash).
- Source regulation: CNMV Circular 4/2008 (periodic reporting); asset statement requirements in CNMV Circular 3/2008.

## Regulatory References

Official CNMV / BOE pages backing project decisions:

- [CNMV — Investor vocation of funds](https://www.cnmv.es/portal/inversor/fondos-vocacion) (verified) — peer-group definition.
- [Circular CNMV 1/2009 (BOE)](https://boe.es/buscar/act.php?id=BOE-A-2009-2742) (verified) — IIC regulation backing vocation semantics.
- [Reglamento de IIC, art. 3](https://papelea.com/es/leyes/reglamento-de-instituciones-de-inversion-colectiva/titulo-i_capitulo-i) (verified) — minimum participants: 100 per fund, 20 per compartment.
- [Reglamento de IIC, full text (art. 76)](https://www.inverco.es/archivosdb/riic-texto-web-octubre2015.pdf) (verified, unread) — minimum patrimony.
- [CNMV — Traspasos entre fondos](https://www.cnmv.es/DocPortal/Publicaciones/Fichas/TraspasosEntreFondosDeInversion.pdf) (verified) — tax deferral context for dividend handling.
- [CNMV — Circular 3/2008 (asset statement requirements)](https://www.cnmv.es/DocPortal/Legislacion/Circulares/Circular_3_2008_Req_IICmobiliarias.pdf) (verified, orientative) — statements managers report to CNMV; context for FONDPATRIMDISVAR and FONDDERI.
