# deploy/windows/actualizar_diario.ps1
#
# Daily automatic update (same idea as Central de Reportes and Presupuestos
# AP). Fetches GitHub; only when main has new commits it runs deploy\update.ps1
# (pull, submodule, dependencies, migrations, branches, static files, restart).
# Nothing new: logs it and exits, the server is not touched.
# Everything goes to logs\update.log; the full output of each run to
# logs\update_<date>.*.log (kept 30 days).
#
# Marks the run FAILED (exit code 1, so Task Scheduler shows it) when the code
# did not reach origin/main, when update.ps1 printed its "port is not
# responding" warning, or when a step printed a Python traceback (update.ps1
# does not stop on a failing native command). A FAILED update is NOT retried
# the next day (no new commit): fix the cause and run deploy\update.ps1 by hand.
#
# Registered by registrar_tareas.ps1 as "Dashboards Fonda - Actualizar".
# ASCII only on purpose: Windows PowerShell 5.1 reads .ps1 files as ANSI.

$ProjectDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$LogDir = Join-Path $ProjectDir "logs"
New-Item -ItemType Directory -Force $LogDir | Out-Null
$Log = Join-Path $LogDir "update.log"
$SafeDir = $ProjectDir -replace '\\', '/'

function Escribir([string]$msg) {
    Add-Content -Path $Log -Value ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg)
}

Set-Location $ProjectDir
git -c "safe.directory=$SafeDir" fetch origin main 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Escribir "FAILED: git fetch (exit $LASTEXITCODE)"; exit 1 }
$Local = (git -c "safe.directory=$SafeDir" rev-parse HEAD).Trim()
$Remoto = (git -c "safe.directory=$SafeDir" rev-parse origin/main).Trim()
if ($Local -eq $Remoto) {
    Escribir ("No changes ({0})" -f $Local.Substring(0, 7))
    exit 0
}

Escribir ("Updating {0} -> {1}" -f $Local.Substring(0, 7), $Remoto.Substring(0, 7))
$env:GIT_CONFIG_COUNT = "2"  # safe.directory for the update's own git pull and the submodule
$env:GIT_CONFIG_KEY_0 = "safe.directory"
$env:GIT_CONFIG_VALUE_0 = $SafeDir
$env:GIT_CONFIG_KEY_1 = "safe.directory"
$env:GIT_CONFIG_VALUE_1 = "$SafeDir/vendor/central"
# A separate process with its output to files: in Windows PowerShell 5.1,
# redirecting it here would turn git's progress on stderr into errors that stop
# update.ps1. WaitForExit() and not -Wait: -Wait also waits for child
# processes, and update.ps1 leaves Waitress running.
$Marca = Get-Date -Format "yyyyMMdd_HHmmss"
$Salida = Join-Path $LogDir "update_$Marca.out.log"
$Errores = Join-Path $LogDir "update_$Marca.err.log"
$Proceso = Start-Process powershell.exe -PassThru -NoNewWindow -WorkingDirectory $ProjectDir `
    -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $ProjectDir 'deploy\update.ps1')`"" `
    -RedirectStandardOutput $Salida -RedirectStandardError $Errores
$null = $Proceso.Handle
$Proceso.WaitForExit()
$Texto = Get-Content $Salida, $Errores -ErrorAction SilentlyContinue
$Texto | Add-Content -Path $Log
Get-ChildItem $LogDir -Filter "update_*.log" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -ErrorAction SilentlyContinue

$Ahora = (git -c "safe.directory=$SafeDir" rev-parse HEAD).Trim()
if ($Ahora -ne $Remoto) { Escribir "FAILED: the code did not reach origin/main, see above"; exit 1 }
if ($Texto -match "no responde todavia") { Escribir "FAILED: the server port is not responding, see logs\waitress.err.log"; exit 1 }
if ($Texto -match "Traceback \(most recent call last\)") { Escribir "FAILED: a step printed a Python traceback, see above"; exit 1 }
Escribir ("Done at {0}" -f $Ahora.Substring(0, 7))
