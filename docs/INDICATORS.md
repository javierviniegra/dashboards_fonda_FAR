# Indicator catalog

One row per indicator of the owner's list as it reaches the dashboards. The code catalog is `dashboards/indicadores.py` (`CATALOGO`); the in-app help reads its texts from there. Every value is computed by Central de Reportes' engine (pinned submodule) — this table says which function.

Status: **listo** (shown), **por construir** (source exists), **sin fuente** (no systematized source).

| Key | Tab | Indicator | Engine code | Comparison / light | Status | Cross-checked |
|---|---|---|---|---|---|---|
| `venta_bruta` | Dirección General | Venta bruta (con IVA) | `metricas.recolectar` → `tabla_comercial.construir_tabla`, row `venta_bruta` | vs same ISO week / same month last year and vs previous period; comparable branches only; arrows ±1%, s/cf below 90% coverage. light = Central's scorecard (last year +5%, else previous period +5%; green >=100%, orange >=90%, red below) | listo | Week 46 2026 (9-15 Nov), consolidated and Acoxpa: identical to the cent to Central's `probar_reporte`; lights orange / green as Central's |
