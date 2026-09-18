<#
.SYNOPSIS
  QuakeLogic HVSR Studio — from-source setup on Windows (developers).
.DESCRIPTION
  End users should use the packaged installer instead (see packaging/README.md).
  Requirements on PATH: php (8.3+ with pdo_sqlite, mbstring, openssl, curl, fileinfo, zip),
  composer, node/npm (22+), and Python 3.12 via the `py` launcher or `uv`.
#>
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root
Write-Host "==> PHP dependencies"; composer install --no-interaction
Write-Host "==> Python environment"
Push-Location engine
if (Get-Command uv -ErrorAction SilentlyContinue) { uv sync --extra dev --python 3.12 }
else {
  py -3.12 -m venv .venv
  .\.venv\Scripts\python.exe -m pip install --upgrade pip
  .\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt pytest httpx
}
Pop-Location
Write-Host "==> Frontend"; npm ci --no-audit --no-fund; npm run build
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Select-String -Path .env -Pattern '^APP_KEY=base64' -Quiet)) { php artisan key:generate --force }
Write-Host "==> Database"; php artisan hvsr:setup --no-interaction
Write-Host ""; Write-Host "Setup complete. Start the application with:  .\HVSR Studio.bat"
