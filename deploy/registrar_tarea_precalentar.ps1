# deploy/registrar_tarea_precalentar.ps1
#
# Registers (or replaces) the warm-up Windows Scheduled Task
# "Dashboards Fonda - Precalentar", which runs deploy\precalentar.ps1:
#   - every day at 02:30 (after the Wansoft pipeline of 01:30), and
#   - every hour from 07:00 to 21:00 (office hours, the meetings).
# Each run takes a few minutes (2026-11-18: week 35 s, month 174 s).
#
# Dev (this PC): run it in a normal PowerShell from the project folder; the
# task runs only while you are logged on (no password stored, no admin), in
# a hidden window (2026-11-18: a visible console closed by hand killed the
# first run with 0xC000013A; at most a brief flash remains).
# Production (app VM): run it in an ADMINISTRATOR PowerShell with -Servidor:
# logon type S4U, runs whether or not anyone is logged on, no password stored.
# Safe to run again (-Force replaces the task).
#
# ASCII only on purpose: Windows PowerShell 5.1 reads .ps1 files as ANSI.

param([switch]$Servidor)

$ErrorActionPreference = "Stop"

$Nombre = "Dashboards Fonda - Precalentar"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$Usuario = "$env:USERDOMAIN\$env:USERNAME"
if ($Servidor) {
    $Principal = New-ScheduledTaskPrincipal -UserId $Usuario -LogonType S4U -RunLevel Highest
} else {
    $Principal = New-ScheduledTaskPrincipal -UserId $Usuario -LogonType Interactive
}
$Ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

$Accion = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$(Join-Path $ProjectDir 'deploy\precalentar.ps1')`"" `
    -WorkingDirectory $ProjectDir

$Madrugada = New-ScheduledTaskTrigger -Daily -At "02:30"
$Oficina = New-ScheduledTaskTrigger -Daily -At "07:00"
$Cada = New-ScheduledTaskTrigger -Once -At "07:00" -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Hours 14)
$Oficina.Repetition = $Cada.Repetition   # 07:00, 08:00, ... 21:00 every day

Register-ScheduledTask -TaskName $Nombre -Action $Accion -Trigger @($Madrugada, $Oficina) `
    -Principal $Principal -Settings $Ajustes -Force | Out-Null

Get-ScheduledTask -TaskName $Nombre | Format-Table TaskName, State -AutoSize
Write-Host "Done. Daily 02:30 and hourly 07:00-21:00. Log: logs\precalentar.log"
