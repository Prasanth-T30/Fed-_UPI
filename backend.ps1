# Backend: first run sets everything up (venv, packages, model training), then starts the API on :8000
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot 'Backend')
$py = '.\.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv .venv } else { python -m venv .venv }
}
& $py -c "import fastapi, torch, sklearn, sqlalchemy, openpyxl, docx, reportlab" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $py -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
}
if (-not (Test-Path 'artifacts\fedupi_model.pt')) { & $py scripts\train.py }
Write-Host 'Backend: http://127.0.0.1:8000  (API docs: /docs)'
& $py -m uvicorn app.main:app --reload --port 8000
