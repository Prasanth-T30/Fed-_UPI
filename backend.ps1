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

function Test-BackendDependencies {
    # PowerShell 5 converts native stderr into error records. Use Process so a
    # failed import can be inspected without triggering NativeCommandError.
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $python
    $startInfo.Arguments = '-c "import flask, flask_cors, waitress, torch, sklearn, sqlalchemy, openpyxl, docx, reportlab"'
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    [void]$process.Start()
    $standardOutput = $process.StandardOutput.ReadToEnd()
    $standardError = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    [pscustomobject]@{
        ExitCode = $process.ExitCode
        Output = ($standardOutput + $standardError).Trim()
    }

    $process.Dispose()
}

$dependencyProbe = Test-BackendDependencies
if ($dependencyProbe.ExitCode -ne 0 -and $dependencyProbe.Output -match 'Application Control policy has blocked this file') {
    throw @"
Windows Smart App Control blocked native Python modules required by FedUPI (PyTorch/scikit-learn).

Open Windows Security > App & browser control > Smart App Control settings and turn Smart App Control Off, then run .\backend.ps1 again. Windows does not support per-app exceptions for Smart App Control.

Python error:
$($dependencyProbe.Output)
"@
}

if ($dependencyProbe.ExitCode -ne 0) {
    Write-Host 'Installing backend dependencies...'
    & $python -m pip install --upgrade pip
    & $python -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }

    $dependencyProbe = Test-BackendDependencies
    if ($dependencyProbe.ExitCode -ne 0) {
        throw "Backend dependencies were installed, but the import check still failed:`n$($dependencyProbe.Output)"
    }
}

if (-not (Test-Path 'artifacts\fedupi_model.pt')) {
    throw 'No model artifact found. Train from your labelled data first: cd Backend; .\.venv\Scripts\python.exe scripts\train.py --data <path-to-file> --quick'
}

if ($Reload) {
    Write-Warning 'Flask reload uses extra memory. Do not use it while training or running tests.'
    $env:FLASK_DEBUG = '1'
    & $python -m flask --app app.main run --host 127.0.0.1 --port $Port
} else {
    Write-Host "Backend: http://127.0.0.1:$Port  (health: /api/health)"
    & $python -m waitress --listen="127.0.0.1:$Port" app.main:app
}
