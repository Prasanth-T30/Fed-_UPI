param(
    [int]$Port = 5173,
    [int]$ApiPort = 8001
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path $ProjectRoot "Frontend"

Push-Location $FrontendDir
try {
    if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir "node_modules"))) {
        npm install
    }
    $env:VITE_API_TARGET = "http://127.0.0.1:$ApiPort"
    npm run dev -- --port $Port
} finally {
    Pop-Location
}
