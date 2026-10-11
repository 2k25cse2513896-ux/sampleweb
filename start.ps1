Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$backendPython = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $backendPython)) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $python) {
        throw "Python is not installed. Install Python 3.11 or 3.12 first."
    }
    & $python.Source -m venv (Join-Path $backend ".venv")
}

$ErrorActionPreference = "Continue"
& $backendPython -c "import fastapi, sqlalchemy, uvicorn" 2>$null
$dependenciesReady = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = "Stop"
if (-not $dependenciesReady) {
    & $backendPython -m pip install -r (Join-Path $backend "requirements.txt")
}

$ErrorActionPreference = "Continue"
& $backendPython -c "import fastapi, sqlalchemy, uvicorn" 2>$null
$dependenciesReady = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = "Stop"
if (-not $dependenciesReady) {
    throw "Backend dependencies could not be installed. Use Python 3.11 or 3.12 and run the command again."
}

if (-not (Test-Path -LiteralPath (Join-Path $root "node_modules"))) {
    Push-Location $root
    npm install
    Pop-Location
}

$backendCommand = "Set-Location -LiteralPath '$backend'; & '$backendPython' -m uvicorn app.main:app --reload --port 8000"
$frontendCommand = "Set-Location -LiteralPath '$root'; npm run dev"

function Test-PortInUse([int]$port) {
    try {
        $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop | Select-Object -First 1
        return $null -ne $listener
    } catch {
        return $false
    }
}

if (Test-PortInUse 8000) {
    Write-Host "Backend already running on http://localhost:8000" -ForegroundColor Yellow
} else {
    Start-Process powershell.exe -ArgumentList @("-NoExit", "-Command", $backendCommand)
}

if (Test-PortInUse 5173) {
    Write-Host "Frontend already running on http://localhost:5173" -ForegroundColor Yellow
} else {
    Start-Process powershell.exe -ArgumentList @("-NoExit", "-Command", $frontendCommand)
}

Write-Host "Backend: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
