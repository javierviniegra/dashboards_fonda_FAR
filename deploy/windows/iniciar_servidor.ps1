# deploy/windows/iniciar_servidor.ps1
#
# Starts Dashboards Fonda with Waitress in the background on port 8045
# (8020 is Presupuestos AP's, 8040 Central de Reportes'; XAMPP holds
# 80/443/3306 on the VM).
# - Without arguments: starts it only if nothing is listening yet. This is what
#   the "at startup" scheduled task runs, so the app comes back by itself after
#   the VM restarts.
# - With -Reiniciar: stops the running one first (update.ps1 uses this).
#
# ASCII only on purpose: Windows PowerShell 5.1 reads .ps1 files as ANSI.

param([switch]$Reiniciar)

$ErrorActionPreference = "Stop"
$Port = 8045

$ProjectDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$WaitressExe = Join-Path $ProjectDir ".venv\Scripts\waitress-serve.exe"
$LogsDir = Join-Path $ProjectDir "logs"
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

$escuchando = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue
if ($escuchando.TcpTestSucceeded -and -not $Reiniciar) {
    Write-Host "Dashboards Fonda ya esta escuchando en el puerto $Port."
    exit 0
}

# Only this project's Waitress (the other apps on the VM use their own copies).
Get-Process waitress-serve -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $WaitressExe } |
    Stop-Process -Force
Start-Sleep -Seconds 1

# --channel-timeout 300: a fresh reading of a month can take minutes.
Start-Process -FilePath $WaitressExe `
    -ArgumentList "--host=0.0.0.0", "--port=$Port", "--threads=8", "--channel-timeout=300", "config.wsgi:application" `
    -WorkingDirectory $ProjectDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $LogsDir "waitress.out.log") `
    -RedirectStandardError (Join-Path $LogsDir "waitress.err.log")

Start-Sleep -Seconds 3
$escuchando = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue
if ($escuchando.TcpTestSucceeded) {
    Write-Host "Listo: Dashboards Fonda escucha en el puerto $Port."
} else {
    Write-Host "AVISO: el puerto $Port no responde todavia. Revisa logs\waitress.err.log."
}
