# Dashboards Fonda

Web "super dashboard" for the Dirección General of Grupo Fonda Argentina (Django). It gathers the network's and each branch's indicators on one screen for the weekly and monthly meetings, starting from the owner's draft ("Portal Directivo & Junta de Socios") and indicator list, and grows block by block.

- Repo: `dashboards_fonda_FAR` (private, on GitHub once the owner creates it).
- Dev: `http://127.0.0.1:8045/`. Production (later): `http://187.251.203.223:8088/dashboards_fonda/`.

## Status

| Block | What | State |
|---|---|---|
| 0 | Skeleton: Django project, login, brand template, four tabs (Dirección General, Ranking, Comercial, Operaciones), help page, Central's engine as a pinned submodule, smoke tests | **Done in dev** (not committed until the owner approves) |
| 1 | One indicator end to end (gross sales with VAT vs last year): branch catalog, period picker (week / month), 1-hour cache, checked against Central's commercial report | Next |
| 2-5 | Dirección General overview, Comercial (block 3), Operaciones (block 4), Ranking (block 2) | Pending |

## How the numbers are computed

**No metric code lives in this repo.** Every figure comes from Central de Reportes' engine (`central.motor`), the code already tested and approved in that project:

- `vendor/central` is a **git submodule** of `analisis_ejecutivos_FAR`, **pinned to one commit**. Only `central.motor` is imported, as a library; Central's Django apps are not installed here, and Central's repo is never modified from this project.
- `dashboards/motor_central.py` is the single bridge to it. The engine's commit is shown in the footer of every page, so each figure traces to an exact version of the code that produced it.
- Updating the engine is deliberate: move the submodule to another commit, run the tests, record it in `docs/DECISIONS.md`.
- Settings append `vendor/central` to `sys.path` (never prepend: Central also has a `config` package, and ours must win; a test checks it).

Data is read **live, read-only** (Wansoft MySQL, Presupuestos AP, Odoo) and **cached for one hour** per view / branches / period (Django database cache, table `dashboards_cache`).

## Structure

- `config/` — Django project (env-driven settings, urls, wsgi). `config/.env` (gitignored) holds every secret; `config/.env.example` documents every variable with blank placeholders.
- `dashboards/` — the app: tabs (`views.PESTANAS`), the engine bridge (`motor_central.py`), the footer's engine version (`context_processors.py`), templates, tests.
- `templates/` — base page, login, admin branding. `static/dashboards/` — logo, CSS (brand green `#035953`, dark green `#023f3b`, orange `#eb6834`, cream `#f0e9d8`).
- `vendor/central/` — Central de Reportes (submodule, read-only).
- `docs/` — `DECISIONS.md` (newest first); `docs/reference/` (owner's draft and indicator list, local only, gitignored).

## Local setup (dev)

```
git clone --recurse-submodules <repo url>        # or: git submodule update --init
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy config\.env.example config\.env              # then fill it in
"C:\xampp\mysql\bin\mysql.exe" -u root -e "CREATE DATABASE dashboards_fonda_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createcachetable
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
