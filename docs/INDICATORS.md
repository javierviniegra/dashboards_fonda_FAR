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
| `canal_plataformas` | Comercial | Venta por plataformas (delivery) | row `canal_plataformas` | no light (no target) | listo | Week 46: 3.6% consolidated (channel pie) |

Charts of the Comercial tab: see `dashboards/graficas.py` (Central's `construir_graficas`, `composicion.construir`, channel and mix rows). Cards shared with the overview (sales, guests, check, ticket, mix) are the same rows.

## Operaciones (block 4)

| Key | Indicator | Engine code | Light | Status |
|---|---|---|---|---|
| `venta_mesero_dia` | Venta por mesero por día | `reporte_meseros` row `venta_mesero_dia` | **draft: green >= $14,500, orange >= $11,500** (rule in `indicadores.UMBRALES_BORRADOR`) | listo |
| `venta_mesero` | Venta por mesero | row `venta_mesero` | — | listo |
| `plantilla` | Meseros activos | row `plantilla` | — | listo |
| `cuentas` | Mesas atendidas | row `cuentas` | — | listo |
| `propina` | Propina % (of card payments) | row `propina` | **draft: green >= 9%, orange >= 8%** | listo |
| `tiempo_mesa` | Tiempo de mesa (min) | row `tiempo_mesa` | — | listo |
| `pct_control` | Cortesías + descuentos % | row `pct_control` | — | listo |
| `cortesias`, `descuentos`, `cancelaciones` | Control ($) | rows of the same names | — | listo |
| `merma_tablajeria` | Merma tablajería % | `tablajeria.construir` total `indice` (vs last year, vs every branch) | — | listo |
| `costo_merma` | Costo de la merma | `tablajeria` total `costo_merma` | — | listo |
| `costo_teorico` | Costo real vs teórico | — | — | pendiente (no engine code) |
| `platillos_86` | Platillos en «86» y devoluciones | — | — | sin fuente |
| `gastos_operativos` | Gas, carbón, limpieza, mantenimiento | Central's scorecard expenses (not on GitHub) | — | pendiente |

Week 46 2026: the ten waiters' cards identical to Central's `reporte_meseros.armar` for the consolidated and every branch (200 comparisons).

## CEDIS (block 5)

| Key | Indicator | Engine code | Light | Status |
|---|---|---|---|---|
| `fill_rate`, `fill_bodegon`, `fill_empanadas` | Fill rate (total, per provider) | `fill_rate.resumen` over `reporte_cedis.leer` | green >= 98%, orange >= 95% (`fill_rate.estado`) | listo |
| `pedidos_cedis` | Pedidos al CEDIS | `reporte_cedis.total_resumen` `ordenes` | — | listo |
| `pct_modificados` | Pedidos modificados % | `total_resumen` `pct` | — | listo |
| `modif_por_cedis` | Modificados por el CEDIS | `total_resumen` `por_cedis` / `por_sucursal` | — | listo |
| `diferencia_cedis` | Diferencia de los modificados | `total_resumen` `diferencia` | — | listo |
| `inflacion_top20` | Inflación top 20 insumos | `inflacion_insumos.calcular` (Laspeyres vs last year) | vs INPC: green <= INPC, orange <= INPC + 2 pp | listo |
| `exactitud_inventario` | Exactitud de inventario CEDIS | — | — | pendiente (source to define) |
| `rechazos_calidad`, `cuatro_candados` | Rechazos de calidad, 4 candados | — | — | sin fuente |

Week 46 2026: identical to the same read inside Central (136 orders, fill 91.43%, 39 modified, -$39,005.58).

