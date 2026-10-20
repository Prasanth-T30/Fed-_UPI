# Frontend: first run installs packages, then starts the UI on :5173 (needs backend.ps1 running)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot 'Frontend')
if (-not (Test-Path 'node_modules')) { npm.cmd install --no-audit --no-fund }
Write-Host 'Frontend: http://127.0.0.1:5173'
npm.cmd run dev
