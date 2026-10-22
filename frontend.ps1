param(
    [ValidateRange(1, 65535)][int]$Port = 5173,
    [ValidateRange(1, 65535)][int]$ApiPort = 8001
)

# Stable Windows frontend launcher with strict duplicate-process protection.
$ErrorActionPreference = 'Stop'
$frontend = Join-Path $PSScriptRoot 'Frontend'
Set-Location $frontend

if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'Node.js 18+ and npm were not found. Install Node.js, then run this script again.'
}

try {
    $page = Invoke-WebRequest -Uri "http://127.0.0.1:$Port" -UseBasicParsing -TimeoutSec 2
    if ($page.StatusCode -eq 200 -and $page.Content -match 'FedUPI') {
        Write-Host "FedUPI frontend is already running on http://127.0.0.1:$Port"
        exit 0
    }
} catch {}

$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($listener) {
    throw "Port $Port is already used by process $($listener[0].OwningProcess). Stop it or run: .\frontend.ps1 -Port <another-port>"
}

if (-not (Test-Path 'node_modules')) {
    Write-Host 'Installing frontend dependencies...'
    & npm.cmd ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
}

$env:VITE_API_TARGET = "http://127.0.0.1:$ApiPort"
Write-Host "Frontend: http://127.0.0.1:$Port  (API: $env:VITE_API_TARGET)"
& npm.cmd run dev -- --host 127.0.0.1 --port $Port --strictPort
