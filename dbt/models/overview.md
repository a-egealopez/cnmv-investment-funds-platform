{% docs __overview__ %}

# CNMV Investment Funds Platform · modelos dbt

Transformaciones analíticas sobre datos públicos de la **CNMV** (ficheros FONDMENS, FONDREGISTRO, FONDTRIM, FONDCART y FONDPATRIMDISVAR) y el índice **€STR** del BCE. Parten de las tablas Silver (Parquet) que genera PySpark y terminan en un panel de Power BI.

Los resultados son **señales analíticas sobre datos históricos**, no recomendaciones de inversión ni conclusiones regulatorias.

## Cómo leer el linaje

Abre el grafo (icono azul abajo a la derecha) y filtra por carpeta. El flujo es siempre de izquierda a derecha:

| Capa | Carpeta | Qué contiene |
|---|---|---|
| Staging | `staging/` | Un modelo por fuente. Solo casteo y renombrado; los puntos porcentuales pasan a fracciones |
| Intermedia | `intermediate/` | Lógica reutilizable: retornos semanales, métricas por clase, puente de patrimonio, clase representativa, ranking de pares |
| Dimensiones | `dimensions/` | `dim_date`, `dim_compartment`, `dim_class`, `dim_manager_group`. Planas, con etiquetas únicas y miembro `-1` «Desconocido» |
| Hechos | `facts/` | Una fila por entidad y fecha, con una sola clave de fecha (`date_key`) |
| Vistas | `reports/` | `mart_fund_panorama` (una fila por compartimento) y `mart_fund_class_status` (auditoría) |
| Calidad | `quality/` | `quarantine_nav_daily`: filas descartadas por valores negativos materiales |
| Metadatos | `meta/` | `meta_run`: el corte de la ejecución (`as_of_period`), definido en un único sitio |

El nodo **Panel de fondos (Power BI)** del grafo es un *exposure*: muestra qué modelos alimentan el dashboard.

## Decisiones que conviene conocer

- **Estrella estricta.** Las dimensiones no se relacionan entre sí; los hechos llevan solo claves enteras y medidas.
- **Un único corte.** `as_of_period` (`latest` o un `YYYYMM`) se resuelve en `meta_run` y todas las tablas lo respetan; no hay datos posteriores al corte.
- **Calidad como parte del producto.** Más de 250 pruebas; las filas inválidas se aíslan en cuarentena y no se descartan en silencio. Las identidades contables de la fuente se comprueban sobre staging.
- **Validación independiente.** Las métricas de riesgo y rentabilidad se recalculan desde los datos crudos con código que no comparte nada con el SQL y se contrastan con las cifras oficiales de CNMV (`tests/integration/`); ese proceso encontró y corrigió dos errores.
- **Métricas propias, no oficiales.** Sortino, rating de pares o ingreso estimado de las gestoras son indicadores del proyecto y se distinguen de las cifras oficiales de CNMV (por ejemplo el TER).

## Documentación relacionada

`docs/analytics/financial_metrics.md` (definición de cada métrica) y `docs/technical/architecture.md` (arquitectura y decisiones).

{% enddocs %}
