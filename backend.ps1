param(
    [ValidateRange(1, 65535)][int]$Port = 8001,
    [switch]$Reload
)

# Stable Windows backend launcher. Reload is deliberately opt-in because each
# reload duplicates the PyTorch model briefly and can exhaust editor memory.
$ErrorActionPreference = 'Stop'
$backend = Join-Path $PSScriptRoot 'Backend'
Set-Location $backend

$env:OMP_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
$env:OPENBLAS_NUM_THREADS = '2'
$env:NUMEXPR_NUM_THREADS = '2'
$env:PYTHONUNBUFFERED = '1'

try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/health" -UseBasicParsing -TimeoutSec 2
    if ($health.StatusCode -eq 200 -and $health.Content -match '"status"\s*:\s*"ok"') {
        Write-Host "FedUPI backend is already running on http://127.0.0.1:$Port"
        exit 0
    }
} catch {}

$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($listener) {
    throw "Port $Port is already used by process $($listener[0].OwningProcess). Stop it or run: .\backend.ps1 -Port <another-port>"
}

$python = Join-Path $backend '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Host 'Creating Backend/.venv...'
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv .venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv .venv
    } else {
        throw 'Python 3.10+ was not found. Install Python, then run this script again.'
    }
}

& $python -c "import fastapi, torch, sklearn, sqlalchemy, openpyxl, docx, reportlab" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing backend dependencies...'
    & $python -m pip install --upgrade pip
    & $python -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
}

if (-not (Test-Path 'artifacts\fedupi_model.pt')) {
    throw 'No model artifact found. Train from your labelled data first: cd Backend; .\.venv\Scripts\python.exe scripts\train.py --data <path-to-file> --quick'
}

$uvicornArgs = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$Port")
if ($Reload) {
    Write-Warning 'Reload mode temporarily uses extra memory. Do not use it while training or running tests.'
    $uvicornArgs += @('--reload', '--reload-dir', 'app')
}

Write-Host "Backend: http://127.0.0.1:$Port  (API docs: /docs)"
& $python @uvicornArgs
