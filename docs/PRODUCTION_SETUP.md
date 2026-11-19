# Production setup

Same layout as Central de Reportes and Presupuestos AP:

| | |
|---|---|
| App VM | SVR-HIKCENTER (192.168.100.93), `C:\Apps\DashboardsFonda`, Waitress + WhiteNoise on port **8045** |
| Database | `dashboards_fonda` on 187.251.203.223 (MySQL), account `dashboards_fonda` |
| URL for users | **`http://187.251.203.223:8088/dashboards_fonda/`** (Apache reverse proxy on that server) |
| Sources (read-only) | Wansoft and Presupuestos AP with Central's SELECT-only account `central_reportes`; Odoo with Central's account; Central's DB (CEDIS mapping, INPC) with `dashboards_fonda` (SELECT on 3 tables) |
| Scheduled tasks | Arranque (startup), Actualizar (daily 05:30), Precalentar (02:30 and hourly 07:00-21:00) |

Production changes are run by the owner; every step says where it runs.

## 1. Database (DB server 187.251.203.223, phpMyAdmin > SQL, as root)

Open `deploy/sql/create_dashboards_fonda_db.sql`, replace `CHANGE_ME` with a real password and run it. It creates the database, the account, and gives the account SELECT on `centraldereportes.central_clientecedis`, `cuentas_sucursal` and `central_inflacion` only. Keep the password for step 3. (No initial data to import: the tables are created by `migrate`, the branches by `cargar_sucursales`.)

## 2. Code (app VM, PowerShell as administrator)

```powershell
cd C:\Apps
git clone --recurse-submodules https://github.com/javierviniegra/dashboards_fonda_FAR.git DashboardsFonda
cd DashboardsFonda
```

`--recurse-submodules` also downloads Central de Reportes' engine (`vendor/central`, pinned commit); the VM's Git credentials already reach both private repos.

## 3. Install (app VM, same administrator PowerShell)

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser   # once, if scripts are blocked
.\deploy\windows\instalar.ps1
```

It asks for the `dashboards_fonda` password (step 1) and for your administrator user, and does the rest: virtualenv and dependencies; `config\.env` (new secret key, `ENV=prod`, `FUENTES_ENV=prod`, prefix `/dashboards_fonda`, this app's DB; the read-only sources copied from `C:\Apps\CentralDeReportes\config\.env`; never printed, never overwritten if it exists); `deploy\update.ps1` (submodule, migrations, cache table, branches, static files, Waitress on 8045); the three scheduled tasks (`deploy\windows\registrar_tareas.ps1`).

Check on the VM: `Test-NetConnection 127.0.0.1 -Port 8045` must succeed; logs in `logs\waitress.*.log`.

## 4. Firewall (app VM, only if Apache cannot reach the port)

```powershell
New-NetFirewallRule -DisplayName "Dashboards Fonda 8045" -Direction Inbound -Protocol TCP -LocalPort 8045 -Action Allow
```

## 5. Reverse proxy (DB/proxy server, Apache `httpd-vhosts.conf`)

Inside the existing `<VirtualHost *:8088>`, next to `/central_reportes/`:

```apache
# Dashboards Fonda
ProxyPass /dashboards_fonda/ http://192.168.100.93:8045/
ProxyPassReverse /dashboards_fonda/ http://192.168.100.93:8045/
RedirectMatch ^/dashboards_fonda$ /dashboards_fonda/
```

(`ProxyTimeout 300` is already there for Central: a fresh reading of a month can take minutes.) Restart Apache. `DJANGO_FORCE_SCRIPT_NAME=/dashboards_fonda` makes every link carry the prefix; Apache strips it on the way in.

## 6. Check

Open `http://187.251.203.223:8088/dashboards_fonda/` from any PC, log in, and open each tab with the last closed week. The first opening of a period reads the sources (up to a few minutes); the warm-up keeps the last week and month ready.

## Updates

Automatic: the task **"Dashboards Fonda - Actualizar"** runs `deploy\windows\actualizar_diario.ps1` every day at 05:30; when GitHub `main` has new commits it runs `deploy\update.ps1`, otherwise it logs "No changes". **So a push to `main` reaches production at the next 05:30.** Log: `logs\update.log` ("FAILED" when the code did not reach `origin/main`, the port does not answer, or a step printed a Python traceback; a failed update is not retried: fix it and run `.\deploy\update.ps1` by hand). Moving the Central engine pin is a normal commit here and travels the same way.

By hand, any time: `.\deploy\update.ps1` (Waitress has no auto-reload: code changes take effect only after this restart).
