# Decisions

Newest first. Each entry: what, why, and where it applies.

## 2026-11-18 — Gross sales light: the scorecard's (owner)

- **What (owner, 2026-11-18):** the gross sales card carries Central's Semáforos scorecard light, the same one Central's commercial report shows: target = the same period last year +5% (`scorecard.CRECIMIENTO_META`); without a comparable last year, the previous period +5%; green from 100% of the target, orange from 90%, red below (`semaforos.PCT_META_VERDE` / `PCT_META_NARANJA`); comparable branches only, no light without a reliable base. The draft's "cumplimiento de presupuesto de ventas" (>=100% / 92-99.9% / <92%) is not used: there is no sales budget in any source.
- **How:** the colour, the share of the target and its base are taken from Central's commercial table row (`Fila.semaforo`, `logro`, `meta_contra`); the target shown is `scorecard.meta_historica` of that same base. The card shows "93.4% de la meta ($15,081,071.88, año anterior +5%)". The rule's text (card help, `/ayuda/`) is written from those constants.
- **Engine behaviour worth knowing:** a branch whose last year is not reliable (<90% of days) leaves that comparison, so its target falls back to the previous period +5% (it is not left without a light). Covered by a test.
- **Week 46 2026:** consolidated orange (93.4%), Acoxpa green (101.2%) -- the same colours as Central's `probar_reporte`; Puebla green (107.1%, previous week +5%, no last year).

## 2026-11-18 — The engine's files must match the pinned commit (guard test)

- **Found:** after block 1, 91 Python files of `vendor/central` differed on disk from the pinned commit `7181d5d`: reformatted (black style) between 09:02:55 (clone) and 09:06:53. Cause unknown (nothing in this session formats code; no formatter hook in the Claude settings; this project's own files were not touched). Checked by AST: 87 files identical, the other 4 (`detalle.py`, `inflacion.py`, `reporte_cedis.py`, `views.py`, none used here) differ in layout of comments/strings only; every module the dashboards use (`metricas`, `tabla_comercial`, `comparativos`, `formato`, `periodo`, `fuentes`) was AST-identical, so block 1's figures were not affected.
- **Done:** the submodule restored to the pinned content (`git -C vendor/central checkout -- .`); week 46 re-read with it: same figures to the cent. New `motor_central.cambios_locales()` and a test that fails when any tracked file of the submodule differs from the pinned commit, so it cannot pass unnoticed again.

## 2026-11-18 — Block 1: branches, periods, cached reading, first indicator

- **Branches** (`dashboards.Sucursal`, same engine-facing fields as Central's `cuentas.Sucursal`) are loaded by `manage.py cargar_sucursales` **from Central's own list**: its `SUCURSALES` and `FORMATOS` constants are read with `ast` from the submodule (the module itself imports Central's `cuentas` app and cannot be imported here). One source for the branch mapping; 19 branches. Metepec gets `considerar_costo=False`, as Central's migration 0004 sets it (owner, 2026-10-05). Perisur and Lindavista are not in Central's list (Oracle Symphony).
- **Periods: closed ones only**, the last 12 weeks (Mon-Sun) and the last 12 months; default = last closed week. Central's engine counts every day of a period as expected, so a period in progress would always compare as "s/cf". Month to date can come later if the owner wants it.
- **One read serves every selection:** `lectura.leer` runs Central's `metricas.recolectar` for ALL active branches over the period, the previous period and the same period last year (batched: one query per period), and caches Central's `Metricas` objects one hour. The key includes the engine commit, so moving the submodule never serves numbers from older code. `lectura.seleccionar` cuts the consolidated or one branch with Central's `metricas.comparables`, as Central's commercial report does.
- **First indicator, gross sales with VAT,** taken from Central's commercial table row (`tabla_comercial.construir_tabla`), formatted with Central's `formato`. The card shows the value, the change vs last year and vs the previous period, and — when branches are left out of the comparison — the comparable branches' value and which branches are out, so "$16.0M vs $14.4M = -1.9%" does not look contradictory.
- **No traffic light on it yet** (settled the same day: the scorecard's, entry above).
- **Cross-check:** week 46 2026 (9-15 Nov), consolidated $16,019,867.17 (previous $15,952,694.06, = +0.4%; last year $14,362,925.60 over comparable branches, ▼ -1.9%; CentroMyJ, La Esquina Coyoacán and Puebla out) and Acoxpa $1,512,355.70 (▲ +2.1%, ▲ +6.3%): identical to the cent to Central's `probar_reporte` on the same week.
- **Measured cost of a fresh read: 93 s** (three periods, every branch, live production sources); from the cache 0.02 s. With "live + 1 h cache", the first viewer of each hour and period waits that long. Option to discuss with the owner: warm the cache on a schedule (e.g. the last closed week and month, after the 01:30 pipeline and every hour in office hours).
- **Sources down:** the page says so in a notice instead of failing.

## 2026-11-18 — Block 0: skeleton

- Django 4.2 (capped below 5.0: MariaDB 10.4), Python 3.13, own dev database `dashboards_fonda_dev` (local XAMPP), dev port 8045.
- Four tabs for v1: Dirección General, Ranking, Comercial, Operaciones; empty ("En construcción") until each block brings its indicators. Login required everywhere; help page `/ayuda/`.
- Light theme with the brand palette (green `#035953`, dark `#023f3b`, orange `#eb6834`, cream `#f0e9d8`), same look as Central de Reportes; own CSS, no Tailwind CDN. The draft's layout ideas (tabs, KPI cards on top, branch selector) are kept; its emerald/slate dark theme is not.
- `config/.env` for dev was filled from Central's `.env` (same read-only data-source variables); the secret key is new.
- The owner's reference files (`docs/reference/`) are gitignored for now: the draft carries figures that look real (banks, suppliers, EBITDA per branch). Pending the owner's word.

## 2026-11-17 — Architecture (owner)

- **Separate project and repo** (`DashboardsFonda`, `dashboards_fonda_FAR`, route `/dashboards_fonda/`), not an app inside Central de Reportes: Central stays untouched (it has work in progress from another session and deploys itself daily from `main`). Central may later link to this app; that would be a Central change, asked for separately.
- **Metrics reused from Central's engine through a git submodule pinned to one commit** (`vendor/central`, first pin `7181d5d`), imported as a library. Not a live path import (Central's uncommitted changes would change our numbers) and not a copy (duplication that diverges). Central's engine is plain Python except `fuentes/conexiones.py`, which reads `settings.FUENTES_ENV`: this app provides it. The engine expects branch objects with `nombre`, `wansoft_subsidiary_id`, `wansoft_ticket_nombre`, `odoo_company_id`, `formato`: this app will have its own `Sucursal` model with those fields (block 1). `reporte_comercial.armar()` reads Central's `Inflacion` model, so the dashboards will call the lower-level functions (`metricas.recolectar`, `scorecard`).
- **Live data with a one-hour cache** (owner chose it over a nightly snapshot, after the tradeoff: one period read of the commercial metrics takes seconds; tips alone 4-18 s for every branch; a consolidated semester or year takes minutes). v1 periods: week and month only; the page shows when it was read and offers "Actualizar".
- **v1 scope:** Dirección General overview, Comercial (block 3, commercial traction only), Operaciones (block 4), Ranking (block 2, on Central's Semáforos scorecard). Each built and approved block by block.
- **Already decided (setup session):** sales = gross sales WITH VAT. There is no sales budget in any source.
- **Open, to settle in their block:** the food-cost traffic light (Central's commercial band 37% to below 39% green / below 37% orange / 39%+ red, since 2026-10-29; the scorecard's Power BI rule <=37% green; the draft's <=37.0% green / >38.5% red); Perisur and Lindavista (Oracle Symphony, not in MySQL yet: show as "sin fuente" or hide); who logs in to v1; whether indicators without a source show grey "sin fuente".
