@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

title PRAVISION — Universal OSINT & Intelligence Platform
color 0B

echo ===============================================================================
echo                PRAVISION — Universal OSINT & Intelligence Platform
echo         "See Everything. Connect Everything. Understand Everything."
echo ===============================================================================
echo.

:: 1. Verify working directory
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

:: 2. UTF-8 Environment Configuration
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

:: 3. Check Python Virtual Environment
if not exist "venv\Scripts\python.exe" (
    echo [!] Virtual environment not detected at %ROOT_DIR%venv
    echo [*] Launching automated setup via setup_pravision.ps1...
    powershell -ExecutionPolicy Bypass -File "%ROOT_DIR%setup_pravision.ps1"
    if errorlevel 1 (
        echo [ERROR] Environment setup encountered an error. Please inspect logs.
        pause
        exit /b 1
    )
)

:: 4. Verify Node / Frontend Build
if not exist "frontend\dist\index.html" (
    echo [*] Compiling frontend intelligence dashboard bundle...
    cd frontend
    call npm.cmd run build
    cd /d "%ROOT_DIR%"
)

:: 5. Start Supervised Production Watchdog & Engine
echo [*] Starting PRAVISION Supervised Production Engine & Tunnel Watchdog...
start "PRAVISION Production Supervisor" /min "%ROOT_DIR%venv\Scripts\python.exe" "%ROOT_DIR%scripts\health_watchdog.py"

:: 6. Launch Web UI Dashboard
echo [*] Launching PRAVISION Dashboard in your default browser...
timeout /t 3 /nobreak >nul
start https://pravision.pages.dev

echo.
echo ===============================================================================
echo [SUCCESS] PRAVISION Production Supervisor is running.
echo   - Local Engine: http://127.0.0.1:8000
echo   - Official Domain: https://pravision.pages.dev
echo   - Health Watchdog: Active (automatic restart on failure)
echo.
echo Press any key to stop all PRAVISION supervised processes...
echo ===============================================================================
pause >nul

:: Graceful Shutdown
taskkill /f /im python.exe /fi "WINDOWTITLE eq PRAVISION Production Supervisor*" >nul 2>&1
taskkill /f /im cloudflared.exe >nul 2>&1
echo [INFO] PRAVISION stopped. Ephemeral buffers purged.

