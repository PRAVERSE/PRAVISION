# PRAVISION — Windows Automatic Startup & Service Registration
# Supports:
#   1. Elevated Administrator: Registers Scheduled Task with AtStartup (pre-logon) & AtLogOn.
#   2. Standard User: Installs Startup Shortcut in User Programs Startup folder (runs on logon).

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$PythonExe = Join-Path $RootDir 'venv\Scripts\python.exe'
$WatchdogScript = Join-Path $RootDir 'scripts\health_watchdog.py'
$StartupFolder = [Environment]::GetFolderPath('Startup')

Write-Host '=================================================================' -ForegroundColor Cyan
Write-Host 'PRAVISION — PRODUCTION AUTO-STARTUP CONFIGURATION' -ForegroundColor Cyan
Write-Host '=================================================================' -ForegroundColor Cyan

$TaskName = 'PRAVISION-Production-Daemon'
$IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($IsAdmin) {
    Write-Host '[*] Administrator privileges detected: Configuring Task Scheduler (Pre-Logon Boot)...' -ForegroundColor Green
    $ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($ExistingTask) {
        Write-Host "[*] Unregistering previous scheduled task '$TaskName'..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    $Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$WatchdogScript`"" -WorkingDirectory $RootDir
    $Triggers = @(
        (New-ScheduledTaskTrigger -AtStartup),
        (New-ScheduledTaskTrigger -AtLogOn)
    )
    $Principal = New-ScheduledTaskPrincipal -UserId 'NT AUTHORITY\SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 365)

    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Triggers -Settings $Settings -Principal $Principal -Description 'PRAVISION Universal Intelligence Platform Watchdog and Production Daemon' | Out-Null
    Write-Host "[SUCCESS] Task '$TaskName' registered for boot startup (pre-logon execution active)." -ForegroundColor Green
} else {
    Write-Host '[*] Non-elevated session detected.' -ForegroundColor Yellow
    Write-Host '    Windows security policy requires Administrator privileges for Task Scheduler / pre-logon boot services.' -ForegroundColor Yellow
    Write-Host ('[*] Installing automatic startup shortcut in User Startup folder: ' + $StartupFolder) -ForegroundColor Cyan

    $WshShell = New-Object -ComObject WScript.Shell
    $ShortcutPath = Join-Path $StartupFolder 'PRAVISION-Production-Daemon.lnk'
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $PythonExe
    $Shortcut.Arguments = "`"$WatchdogScript`""
    $Shortcut.WorkingDirectory = $RootDir
    $Shortcut.WindowStyle = 7 # Minimized
    $Shortcut.Description = 'PRAVISION Production Health Supervisor'
    $Shortcut.Save()

    Write-Host "[SUCCESS] User Startup shortcut created successfully: $ShortcutPath" -ForegroundColor Green
    Write-Host '  - Auto-start trigger: Runs automatically upon user logon (no UAC required)'
    Write-Host '  - Execution mode: Minimized background watchdog'
    Write-Host '  [NOTE] For pre-logon boot startup before interactive logon, open an elevated PowerShell prompt as Administrator and re-run this script.' -ForegroundColor Gray
}

Write-Host "  - Command: $PythonExe $WatchdogScript"
Write-Host '=================================================================' -ForegroundColor Cyan
