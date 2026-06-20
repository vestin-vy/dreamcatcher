# DreamCatcher dev runner (PowerShell).
# Usage:  .\run.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}
if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Created .env from .env.example - set SECRET_KEY and ADMIN_PASSWORD_HASH." -ForegroundColor Yellow
}

.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
