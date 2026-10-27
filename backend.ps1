param(
    [int]$Port = 8001,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectRoot "Backend"
$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    python -m venv (Join-Path $BackendDir ".venv")
}

& $Python -m pip install -q -r (Join-Path $BackendDir "requirements.txt")
Push-Location $BackendDir
try {
    if ($Reload) {
        & $Python -m flask --app app.main run --host 127.0.0.1 --port $Port --debug
    } else {
        & $Python -m waitress --listen="127.0.0.1:$Port" app.main:app
    }
} finally {
    Pop-Location
}
