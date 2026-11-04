# PRAVISION — Windows Service / Scheduled Task Registration
# Configures the PRAVISION Watchdog to run on boot / logon with automatic recovery

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$PythonExe = Join-Path $RootDir "venv\Scripts\python.exe"
$WatchdogScript = Join-Path $RootDir "scripts\health_watchdog.py"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "PRAVISION — AUTOMATIC SERVICE REGISTRATION (WINDOWS)" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$TaskName = "PRAVISION-Production-Daemon"

# Check if task already exists
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    Write-Host "[*] Unregistering previous scheduled task '$TaskName'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$WatchdogScript`"" -WorkingDirectory $RootDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 365)

Write-Host "[*] Registering task '$TaskName' to start on logon with automatic restart recovery..." -ForegroundColor Green
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "PRAVISION Universal Intelligence Platform Watchdog & Production Daemon" | Out-Null

Write-Host "[SUCCESS] Task '$TaskName' registered successfully." -ForegroundColor Green
Write-Host "  - Command: $PythonExe $WatchdogScript"
Write-Host "  - Auto-restart: Enabled (up to 3 retries every 1m)"
Write-Host "  - Trigger: At user logon"
Write-Host "=================================================================" -ForegroundColor Cyan
