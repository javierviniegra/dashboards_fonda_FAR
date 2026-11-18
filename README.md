# Dashboards Fonda

Web "super dashboard" for the Dirección General of Grupo Fonda Argentina (Django). It gathers the network's and each branch's indicators on one screen for the weekly and monthly meetings, starting from the owner's draft ("Portal Directivo & Junta de Socios") and indicator list, and grows block by block.

- Repo: https://github.com/javierviniegra/dashboards_fonda_FAR (private). Clone with `--recurse-submodules`; the submodule is Central de Reportes' private repo, so the cloning account needs access to both.
- Dev: `http://127.0.0.1:8045/`. Production (later): `http://187.251.203.223:8088/dashboards_fonda/`.

## Status

| Block | What | State |
|---|---|---|
| 0 | Skeleton: Django project, login, brand template, four tabs (Dirección General, Ranking, Comercial, Operaciones), help page, Central's engine as a pinned submodule, smoke tests | **Done** (commit 1a1d456) |
| 1 | One indicator end to end (gross sales with VAT vs last year): branch catalog from Central's list, closed week / month picker, 1-hour cached reading of every branch, card on the Dirección General tab, help per indicator; cross-checked to the cent against Central's commercial report | **Done in dev** (awaiting the owner's approval) |
| 2 | Dirección General overview: ten cards (sales, guests, check, ticket, drinks mix, both costs with Central's lights; dining-room guests and EBITDA grey as pending); cache warm-up task | **Done in dev** |
| 3 | Comercial: compact cards with tooltips (sales, guests, check, ticket, mix, delivery share) and Central's charts (sales/guests per day, 12-month trend, channels, mix, time bands, payment methods, platforms, weekday, hour) | **Done in dev** (first version) |
| 4 | Operaciones: waiters' productivity, tips, table time, control, butchery shrinkage (Central's waiters' report and butchery section; draft thresholds on sales per waiter per day and tips); pending grey cards for theoretical cost, 86s and operating expenses | **Done in dev** |
| 5 | Ranking (block 2: waits for Central to publish its scorecard reading) | Pending |

## How the numbers are computed

**No metric code lives in this repo.** Every figure comes from Central de Reportes' engine (`central.motor`), the code already tested and approved in that project:

- `vendor/central` is a **git submodule** of `analisis_ejecutivos_FAR`, **pinned to one commit**. Only `central.motor` is imported, as a library; Central's Django apps are not installed here, and Central's repo is never modified from this project.
- `dashboards/motor_central.py` is the single bridge to it. The engine's commit is shown in the footer of every page, so each figure traces to an exact version of the code that produced it.
- Updating the engine is deliberate: move the submodule to another commit, run the tests, record it in `docs/DECISIONS.md`.
- Settings append `vendor/central` to `sys.path` (never prepend: Central also has a `config` package, and ours must win; a test checks it).

Data is read **live, read-only** (Wansoft MySQL, Presupuestos AP, Odoo) and **cached for one hour** per period (Django database cache, table `dashboards_cache`): one read holds every active branch, so the consolidated and each branch come from it.

**Warm-up:** `python manage.py precalentar` reads the last closed week and month ahead; the scheduled task "Dashboards Fonda - Precalentar" runs it daily at 02:30 and hourly 07:00-21:00 (register with `deploy/registrar_tarea_precalentar.ps1`; production adds `-Servidor`, in an administrator PowerShell). Log: `logs/precalentar.log`.

## Structure

- `config/` — Django project (env-driven settings, urls, wsgi). `config/.env` (gitignored) holds every secret; `config/.env.example` documents every variable with blank placeholders.
- `dashboards/` — the app: tabs (`views.PESTANAS`), the engine bridge (`motor_central.py`), the footer's engine version (`context_processors.py`), `models.Sucursal` (engine-facing branch fields; `manage.py cargar_sucursales` loads them from Central's own list), `lectura.py` (closed periods; one cached read of every branch through Central's `metricas.recolectar`, and a separate one for Operaciones -- `meseros.recolectar` and the butchery pieces; consolidated / single-branch selection with Central's comparable-branches rule), `indicadores.py` (indicator catalog: definition, source, rule, and the Central function behind each card), `graficas.py` (Central's chart data as JSON; drawn by `static/dashboards/js/graficas.js` with Chart.js 4.5.1), templates, tests.
- `templates/` — base page, login, admin branding. `static/dashboards/` — logo, CSS (brand green `#035953`, dark green `#023f3b`, orange `#eb6834`, cream `#f0e9d8`).
- `vendor/central/` — Central de Reportes (submodule, read-only).
- `docs/` — `DECISIONS.md` (newest first), `INDICATORS.md` (catalog with the engine code and cross-checks of each indicator); `docs/reference/` (owner's draft and indicator list, local only, gitignored).

## Local setup (dev)

```
git clone --recurse-submodules <repo url>        # or: git submodule update --init
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy config\.env.example config\.env              # then fill it in
"C:\xampp\mysql\bin\mysql.exe" -u root -e "CREATE DATABASE dashboards_fonda_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createcachetable
.venv\Scripts\python.exe manage.py cargar_sucursales
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver 8045
```

Tests: `.venv\Scripts\python.exe manage.py test` (needs the local MariaDB).

**Port 8045** (8000 XAMPP, 8010/8020 Presupuestos AP, 8040-8044 other apps).

## Help

In-app help at `/ayuda/` (link "Ayuda" in the header). It grows with every indicator added: definition, source and traffic-light rule.

## Rules

- Data sources are read-only. Sibling repos (Wansoft ETL, ControlPresupuestos_AP, Central de Reportes) are never modified from here.
- Secrets only in `config/.env`.
- Every number traces to approved Python code; no metric, threshold or target is invented — definitions come from the owner.
- Every change of behaviour, structure or a decision updates this README and/or `docs/` in the same commit. Commits and docs in English; the UI in Spanish.
