# Data Sources

Last updated: 2026-09-26

## Source

**Comisión Nacional del Mercado de Valores (CNMV)** — official public data on Spanish Collective Investment Schemes (IIC).

## Datasets

### 1. FONDMENS — Monthly Fund Messaging

| Field | Description |
|-------|-------------|
| **Origin** | CNMV — Descarga de ficheros de información individual de IIC |
| **URL** | https://www.cnmv.es/portal/publicaciones/descarga-informacion-individual |
| **Format** | ZIP with XML + XSD + explanatory PDF |
| **Frequency** | Monthly |
| **Volume** | ~15 MB per period, ~1428 funds |
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

### 3. IPP per-Fund — Periodic Public Information

| Field | Description |
|-------|-------------|
| **Origin** | CNMV — Per-fund consultation portal |
| **URL** | https://www.cnmv.es/portal/Consultas/IIC/Fondo.aspx?nreg={NUMERO_REGISTRO} |
| **Format** | XML (per-fund download) + explanatory PDF |
| **Frequency** | Semiannual / Annual |
| **Volume** | Per individual fund |
| **Structure** | Holdings, portfolio composition, sector allocation, transactions |
| **Key fields** | Holdings (concrete assets), weight in portfolio, sector, country |
| **Use** | Portfolio composition, asset rotation, concentration analysis |

### 4. Entity Catalog

| Field | Description |
|-------|-------------|
| **Origin** | Extracted from FONDREGISTRO XML |
| **Format** | Derived (no separate download) |
| **Use** | All nreg numbers for iterating IPP per-fund downloads |

## Relationships

```
FONDREGISTRO (nreg, ISIN, metadata) → FONDMENS (daily time series)
FONDREGISTRO (nreg) → IPP per-fund (detailed holdings)
```

## Temporal Availability

- Data available from 2012
- FONDMENS: monthly, 2012–2026
- FONDREGISTRO: monthly, 2012–2026
- IPP per-fund: semiannual/annual

## Usage Conditions

- Official public data
- Free, no usage restrictions
- Traceability must be maintained (origin, download date)
- Source: CNMV Circular 4/2008
