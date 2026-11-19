# deploy/update.ps1
#
# Deploys what is on GitHub main to this machine (production app VM). Runs by
# itself every day at 05:30 when main has new commits (task "Dashboards Fonda -
# Actualizar", deploy\windows\actualizar_diario.ps1); run it by hand to deploy
# right away. Pulls the code AND the pinned Central de Reportes engine
# (git submodule), installs dependencies, migrates, loads the branches,
# collects static files and restarts the server.
#
# First-time setup (clone, venv, .env, database) is NOT part of this script:
# see docs/PRODUCTION_SETUP.md, once.
#
# ASCII only on purpose: Windows PowerShell 5.1 reads .ps1 files as ANSI.

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
Set-Location $ProjectDir

Write-Host "=== Pulling latest code from GitHub ==="
git pull origin main

Write-Host "=== Central de Reportes engine (submodule, pinned commit) ==="
# --force: the pinned code must be exactly the commit (a guard test checks it).
git submodule sync --recursive
git submodule update --init --force

Write-Host "=== Installing/updating dependencies ==="
& $Python -m pip install -r requirements.txt

Write-Host "=== Applying database migrations ==="
& $Python manage.py migrate --noinput

Write-Host "=== Cache table (only creates it if missing) ==="
& $Python manage.py createcachetable

Write-Host "=== Branches from Central's list (only creates missing ones; admin edits are kept) ==="
& $Python manage.py cargar_sucursales

Write-Host "=== Collecting static files ==="
& $Python manage.py collectstatic --noinput

Write-Host "=== Restarting the server ==="
& (Join-Path $PSScriptRoot "windows\iniciar_servidor.ps1") -Reiniciar
