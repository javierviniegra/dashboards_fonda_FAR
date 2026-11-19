# deploy/windows/registrar_tareas.ps1
#
# Registers (or updates) the three Windows Scheduled Tasks of Dashboards Fonda
# on the production app VM. Run once, in an ADMINISTRATOR PowerShell, from the
# project folder; safe to run again (-Force replaces them).
#
#   1. "Dashboards Fonda - Arranque":    at VM startup, starts the web server
#      (deploy\windows\iniciar_servidor.ps1), so a reboot does not leave it down.
#   2. "Dashboards Fonda - Actualizar":  daily at 05:30, deploys what was pushed
#      to GitHub (deploy\windows\actualizar_diario.ps1 runs update.ps1 only
#      when main has new commits; log in logs\update.log).
#   3. "Dashboards Fonda - Precalentar": the cache warm-up, daily 02:30 and
#      hourly 07:00-21:00 (deploy\registrar_tarea_precalentar.ps1 -Servidor).
#
# All run as the current user with logon type S4U: whether or not anyone is
# logged on, without storing a password (they only need the network: GitHub,
# Odoo and MySQL).
#
# ASCII only on purpose: Windows PowerShell 5.1 reads .ps1 files as ANSI.

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Usuario = "$env:USERDOMAIN\$env:USERNAME"
$Principal = New-ScheduledTaskPrincipal -UserId $Usuario -LogonType S4U -RunLevel Highest
$Ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# 1. Web server at startup.
$Arranque = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $ProjectDir 'deploy\windows\iniciar_servidor.ps1')`"" `
    -WorkingDirectory $ProjectDir
Register-ScheduledTask -TaskName "Dashboards Fonda - Arranque" -Action $Arranque -Trigger (New-ScheduledTaskTrigger -AtStartup) `
    -Principal $Principal -Settings $Ajustes -Force | Out-Null

# 2. Daily update from GitHub.
$Actualizar = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $ProjectDir 'deploy\windows\actualizar_diario.ps1')`"" `
    -WorkingDirectory $ProjectDir
Register-ScheduledTask -TaskName "Dashboards Fonda - Actualizar" -Action $Actualizar -Trigger (New-ScheduledTaskTrigger -Daily -At "05:30") `
    -Principal $Principal -Settings $Ajustes -Force | Out-Null

# 3. Cache warm-up (its own script, server mode).
& (Join-Path $ProjectDir "deploy\registrar_tarea_precalentar.ps1") -Servidor

Get-ScheduledTask -TaskName "Dashboards Fonda*" | Format-Table TaskName, State -AutoSize
Write-Host "Listo. Bitacoras: logs\update.log, logs\precalentar.log, logs\waitress.*.log"
