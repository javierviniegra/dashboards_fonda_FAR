# Decisions

Newest first. Each entry: what, why, and where it applies.

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
