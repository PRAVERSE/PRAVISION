# PRAVISION Automated Setup Script
# Verifies system environment, creates isolated virtual environment, and installs dependencies.

$ErrorActionPreference = "Stop"
$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $rootDir

Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "            PRAVISION Intelligence Platform — Environment Setup" -ForegroundColor Cyan
Write-Host "===============================================================================" -ForegroundColor Cyan

# 1. Check Python version
Write-Host "[1/5] Checking Python availability..." -ForegroundColor Yellow
try {
    $pythonVer = & python --version 2>&1
    Write-Host "  -> Detected: $pythonVer" -ForegroundColor Green
} catch {
    Write-Error "Python 3.12+ was not found on PATH. Please install Python 3.12."
}

# 2. Check Node.js and npm
Write-Host "[2/5] Checking Node.js and npm..." -ForegroundColor Yellow
try {
    $nodeVer = & node --version 2>&1
    $npmVer = & npm.cmd --version 2>&1
    Write-Host "  -> Node.js: $nodeVer | npm: $npmVer" -ForegroundColor Green
} catch {
    Write-Error "Node.js or npm.cmd was not found. Please ensure Node.js is installed."
}

# 3. Create or verify Python Virtual Environment
Write-Host "[3/5] Initializing Python virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "$rootDir\venv\Scripts\python.exe")) {
    Write-Host "  -> Creating venv in $rootDir\venv..." -ForegroundColor Gray
    & python -m venv "$rootDir\venv"
} else {
    Write-Host "  -> Virtual environment already exists." -ForegroundColor Green
}

# 4. Install backend dependencies
Write-Host "[4/5] Installing backend Python packages..." -ForegroundColor Yellow
& "$rootDir\venv\Scripts\python.exe" -m pip install -r "$rootDir\backend\requirements.txt" --quiet

# 5. Install frontend dependencies and build
Write-Host "[5/5] Installing frontend packages and compiling assets..." -ForegroundColor Yellow
Set-Location "$rootDir\frontend"
& npm.cmd install --silent
& npm.cmd run build
Set-Location $rootDir

# 6. Verify GHunt Installation & Configuration
Write-Host "`n[*] Verifying GHunt 2.3.4 environment..." -ForegroundColor Yellow
$ghuntExe = "C:\Users\hp\.local\bin\ghunt.exe"
$ghuntCreds = "$HOME\.malfrats\ghunt\creds.m"

if (Test-Path $ghuntExe) {
    Write-Host "  -> GHunt binary located at: $ghuntExe" -ForegroundColor Green
} else {
    Write-Host "  -> [WARNING] GHunt executable not found at $ghuntExe." -ForegroundColor DarkYellow
}

if (Test-Path $ghuntCreds) {
    Write-Host "  -> Stored GHunt session creds found at: $ghuntCreds" -ForegroundColor Green
} else {
    Write-Host "  -> [NOTICE] GHunt session not found. Run 'ghunt login' if Google audits are needed." -ForegroundColor DarkYellow
}

Write-Host "`n===============================================================================" -ForegroundColor Cyan
Write-Host "[SUCCESS] PRAVISION setup completed successfully!" -ForegroundColor Green
Write-Host "To launch PRAVISION, run: .\start_pravision.bat" -ForegroundColor Cyan
Write-Host "===============================================================================" -ForegroundColor Cyan
