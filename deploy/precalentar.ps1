# deploy/precalentar.ps1
#
# Warm-up of the dashboards' cache: reads the last closed week and month
# ahead (python manage.py precalentar), so the meetings open them at once.
# Run by the scheduled task "Dashboards Fonda - Precalentar"
# (deploy/registrar_tarea_precalentar.ps1).
#
# Log: logs\precalentar.log (one line per run and period; kept as one file,
# trimmed to its last 2000 lines). Exit code 1 when the warm-up fails, so
# Task Scheduler shows the run as failed.
#
# ASCII only on purpose: Windows PowerShell 5.1 reads .ps1 files as ANSI.

$ProjectDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectDir "logs"
$Log = Join-Path $LogDir "precalentar.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Escribir($texto) {
    $linea = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $texto"
    Add-Content -Path $Log -Value $linea -Encoding UTF8
}

Set-Location $ProjectDir
$env:PYTHONIOENCODING = "utf-8"
Escribir "Start"
# Output to files in a separate process: in Windows PowerShell 5.1, "2>&1"
# on a native command turns its stderr lines (Django's log) into errors.
$Salida = Join-Path $LogDir "precalentar_ultima.out.log"
$Errores = Join-Path $LogDir "precalentar_ultima.err.log"
$p = Start-Process -FilePath $Python -ArgumentList "manage.py", "precalentar" -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $Salida -RedirectStandardError $Errores
# Touch the handle before waiting: without it Windows PowerShell 5.1 loses
# the exit code of a Start-Process -PassThru process (ExitCode comes back empty).
$null = $p.Handle
$p.WaitForExit()
foreach ($l in (Get-Content -Path $Salida -Encoding UTF8 -ErrorAction SilentlyContinue)) { Escribir "  $l" }
if ($p.ExitCode -ne 0) {
    Escribir "FAILED (exit $($p.ExitCode)); see logs\precalentar_ultima.err.log"
} else {
    Escribir "Done"
}

# Keep the log short.
$todas = Get-Content -Path $Log -Encoding UTF8
if ($todas.Count -gt 2000) { $todas | Select-Object -Last 2000 | Set-Content -Path $Log -Encoding UTF8 }
exit $p.ExitCode
