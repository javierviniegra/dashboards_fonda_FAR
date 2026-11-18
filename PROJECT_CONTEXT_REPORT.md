# PROJECT_CONTEXT_REPORT.md — Dashboards Fonda

Master continuity document. Regenerated **in full** (never as patches) at every chat handoff. **Read this first when picking the project up in a fresh chat**, then `README.md` and `docs/DECISIONS.md`.

Last generated: 2026-11-18 (block 0). Repo: `dashboards_fonda_FAR` (local git only; GitHub repo not created yet). No commits yet: block 0 awaits the owner's approval.

---

# 0. Permanent handoff rule (owner)

When the owner says the context is running out (only when **less than ~20%** remains; never push early handoffs), do ALL of these:

1. Regenerate this file in full (English).
2. Write the handoff prompt (Spanish), also kept in Section 9.
3. Give the new chat title: `FONDA (Dashboards Fonda): Paso N: <short description>`.
4. Commit/push if needed (English message, no secrets) and **stop the dev server** (port 8045).

---

# 1. What this project is

Web "super dashboard" for Grupo Fonda Argentina's Dirección General. It starts from the owner's draft (`docs/reference/portal_directivo_draft.html`, "Portal Directivo & Junta de Socios", hardcoded Sept 2026 mock) and indicator list (`docs/reference/indicators_list_owner.md`: 8 blocks + "innegociables" KPI cards per director + traffic-light table). It grows iteratively, human in the loop: definitions, formulas and thresholds come from the owner; nothing is invented.

v1 scope (owner, 2026-11-17): Dirección General overview, Comercial (block 3, traction only), Operaciones (block 4), Ranking (block 2).

---

# 2. Environment — READ FIRST

- **Path:** `C:\Users\JavierViniegra\OneDrive - GRUPO FONDA ARGENTINA\Escritorio\AnalisisRestaurantesBI\DashboardsFonda`. The harness shell resets its cwd to a dead `...\Desktop\...` path after every command: always `cd` to the real path or use absolute paths (Git-Bash: `/c/Users/...`).
- **Venv:** `.venv` (Python 3.13.14, Django 4.2.30). Run `.venv/Scripts/python.exe manage.py ...`.
- **Dev DB:** local XAMPP MariaDB, db `dashboards_fonda_dev`, root (dev only). XAMPP MySQL is not a Windows service: the owner starts it by hand; never suggest making it one.
- **`config/.env`** (gitignored) was filled from Central's `.env`: `FUENTES_ENV` and the `WANSOFT_DB_*`, `PRESUPUESTOS_DB_*`, `ODOO_*` variables (the app runs in dev but reads the production sources, read-only sessions). Never print its values.
- **Port 8045** (8000 XAMPP, 8010/8020 Presupuestos AP, 8040-8044 taken). Claude starts/stops the dev server and tells the owner the URL and what to look at.
- **Central's engine:** `vendor/central` = git submodule of `https://github.com/javierviniegra/analisis_ejecutivos_FAR.git`, pinned to `7181d5d`. Read-only; never edit files there.

---

# 3. Rules (owner)

- Sources read-only (Odoo XML-RPC, Wansoft MySQL canonical/analytic tables, MySQL at 187.251.203.223). Never modify the sibling repos (Wansoft ETL, ControlPresupuestos_AP, Central de Reportes).
- Secrets only in `config/.env` (placeholders in `config/.env.example`).
- Every number traces to approved Python code (Central's engine, pinned).
- Small, explained blocks; **commit only after the owner approves each block**; README + `docs/DECISIONS.md` in the same commit. Code, commits and docs in English; chat and UI in Spanish (with accents).
- Local dev needs no permission. Anything production or external (creating the GitHub repo, push, Apache, the VM, prod DBs) needs confirmation first. `gh` is not installed: the owner creates the empty private repo on github.com (or propose `winget install GitHub.cli`).
- Production later: VM SVR-HIKCENTER (`C:\Apps\DashboardsFonda`, Waitress + WhiteNoise, own port), Apache proxy `http://187.251.203.223:8088/dashboards_fonda/`; copy Presupuestos AP's deploy pattern (`deploy/update.ps1`, `actualizar_diario.ps1`), confirm before touching production. The VM's clone needs `--recurse-submodules`.

---

# 4. Architecture (approved 2026-11-17)

See `docs/DECISIONS.md` for the reasons. Separate repo; Central's `central.motor` imported as a library from the pinned submodule (`settings` appends `vendor/central` to `sys.path`; our `config` must win, tested); `dashboards/motor_central.py` is the bridge and reports the engine commit (shown in every page footer). Live data, Django DB cache 1 h (`dashboards_cache`), v1 periods week and month.

Known engine facts for block 1: the engine expects branch objects with `nombre`, `pk`, `wansoft_subsidiary_id`, `wansoft_ticket_nombre`, `odoo_company_id`, `formato` (Central's `cuentas.Sucursal`; mirror its loader `cargar_sucursales`); `reporte_comercial.armar()` imports Central's `Inflacion` model → use `metricas.recolectar(cur_wansoft, cur_presupuestos, sucursales, periodo, odoo=..., incluir_costos=...)` and `reporte_scorecard` instead; connections via `central.motor.fuentes.conexiones.abrir_wansoft()` / `abrir_presupuestos()` (read-only sessions, 120 s cap).

---

# 5. Current state

Block 0 done in dev, not committed: Django project `config`, app `dashboards` (tabs `PESTANAS`: portada, ranking, comercial, operaciones — empty "En construcción"), login (Central's look), admin branding, `/ayuda/`, brand CSS `static/dashboards/css/tablero.css`, 11 smoke tests passing (engine importable from the submodule, our `config` wins, `conexiones.origen()` reads our settings, views, login). No superuser yet: the owner creates it with `createsuperuser`.

---

# 6. Findings about the draft and the sources

- Draft: all numbers hardcoded; broken template placeholders (e.g. `cumpVenta%demeta(...)`); says 12 branches (Wansoft has 19, plus Aeropuerto and Taquería Viaducto since 2026-11-02); emerald/slate colours instead of the brand.
- Sales = gross sales WITH VAT (decided). **No sales budget in any source** (Central's 2025 SharePoint targets only).
- Cost traffic light: three rules in play (Central commercial band 37%-<39% since 2026-10-29; scorecard/Power BI <=37% green; draft <=37.0% / >38.5%) — owner chooses in the block.
- Perisur and Lindavista are on Oracle Symphony, not in MySQL yet (separate pending integration).
- Indicator availability (setup session): ready = YoY sales, covers, check/ticket, food/drink mix, delivery, sales per waiter, real cost, shrinkage, gas/charcoal/cleaning/maintenance, input inflation, cash closings; needs build = P&L, EBITDA, banks, suppliers 201, bank reconciliation, draft entries, CEDIS fill rate/rejections/inventory accuracy, tip % and ticket times, expense budget compliance; no source = Mystery Shopper, Google Reviews, QR/NPS, CCTV, 86'd dishes, 4 Candados, all HR (Buk has no API), La Academia, IT SLA, accounting calendar, royalties/partner statement, consequences matrix, Rocas & Acuerdos. Central's Semáforos scorecard already computes 13 of its 24 KPIs (sales, cost, 7 expenses, drinks mix, check, ticket, guests).

---

# 7. Next steps

1. Owner approves block 0 → first commit (decide whether `docs/reference/` goes into the private repo).
2. Block 1: `Sucursal` model + loader, period picker (week/month), cache layer, indicator catalog contract (`docs/INDICATORS.md`), first indicator (gross sales with VAT vs last year) cross-checked against Central's commercial report.
3. Then blocks: Dirección General overview, Comercial, Operaciones, Ranking.

---

# 8. How to run

```
cd "C:\Users\JavierViniegra\OneDrive - GRUPO FONDA ARGENTINA\Escritorio\AnalisisRestaurantesBI\DashboardsFonda"
.venv\Scripts\python.exe manage.py test
.venv\Scripts\python.exe manage.py runserver 8045      # stop it when done
```

---

# 9. Handoff prompt

To be written at the first handoff.
