# Indicator catalog

One row per indicator of the owner's list as it reaches the dashboards. The code catalog is `dashboards/indicadores.py` (`CATALOGO`); the in-app help reads its texts from there. Every value is computed by Central de Reportes' engine (pinned submodule) — this table says which function.

Status: **listo** (shown), **por construir** (source exists), **sin fuente** (no systematized source).

| Key | Tab | Indicator | Engine code | Comparison / light | Status | Cross-checked |
|---|---|---|---|---|---|---|
| `venta_bruta` | Dirección General | Venta bruta (con IVA) | `metricas.recolectar` → `tabla_comercial.construir_tabla`, row `venta_bruta` | vs same ISO week / same month last year and vs previous period; comparable branches only; arrows ±1%, s/cf below 90% coverage. light = Central's scorecard (last year +5%, else previous period +5%; green >=100%, orange >=90%, red below) | listo | Week 46 2026 (9-15 Nov), consolidated and Acoxpa: identical to the cent to Central's `probar_reporte`; lights orange / green as Central's |
| `venta_neta` | Dirección General | Venta neta (sin IVA) | row `venta_neta` | same comparisons; no light (no sales budget) | listo | Week 46: identical to Central |
| `clientes` | Dirección General | Clientes (all orders) | row `clientes` | scorecard light (last year +5%) | listo | Week 46: identical to Central |
| `afluencia_salon` | Dirección General | Afluencia de salón (restaurant orders only) | Central's scorecard reading (`reporte_scorecard`, not on GitHub yet) | scorecard | **pendiente** | — |
| `cheque_promedio` | Dirección General | Cheque promedio | row `cheque_promedio` | scorecard light | listo | Week 46: identical to Central |
| `ticket_promedio` | Dirección General | Ticket promedio | row `ticket_promedio` | scorecard light | listo | Week 46: identical to Central |
| `mix_bebidas` | Dirección General | Mezcla de bebidas | row `mix_bebidas` | scorecard threshold: green >=30%, orange >=26% | listo | Week 46: identical to Central |
| `costo_total_pct` | Dirección General | Costo total / venta neta | row `costo_total_pct` (incl. Odoo estimate) | commercial band: green 37%-<39%, orange <37%, red >=39% | listo | Week 46: identical to Central |
| `costo_ventas_pct` | Dirección General | Costo facturado / venta neta | row `costo_ventas_pct` (Presupuestos AP) | commercial band; consolidated only when every branch has it | listo | Week 46: identical to Central (Acoxpa 2.0% preliminary) |
| `ebitda` | Dirección General | EBITDA | — (Odoo accounting, to build) | — | **sin fuente** | — |
