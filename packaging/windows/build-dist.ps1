<#
.SYNOPSIS
  Build the standalone Windows x64 distribution of QuakeLogic HVSR Studio.
.DESCRIPTION
  Wrapper around packaging/build_dist.py. Requirements on the build machine:
    - Python 3.12 (py launcher)          https://www.python.org
    - Node.js 22+ LTS (npm)              https://nodejs.org
    - PHP 8.4 CLI + composer.phar        (put composer.phar in .tools\ or install Composer)
    - Inno Setup 6 (optional, installer) https://jrsoftware.org/isinfo.php
  Internet access is required at build time only.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File packaging\windows\build-dist.ps1
  powershell -ExecutionPolicy Bypass -File packaging\windows\build-dist.ps1 -SkipFrontend -Installer
#>
param(
    [string]$Out = "dist",
    [string]$PhpSeries = "8.4",
    [string]$PythonSeries = "3.12",
    [switch]$SkipFrontend,
    [switch]$SkipRuntimes,
    [switch]$Installer
)
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { $python = @("py", "-3.12") } else { $python = @("python") }

$args = @("packaging\build_dist.py", "--out", $Out, "--php-series", $PhpSeries, "--python-series", $PythonSeries)
if ($SkipFrontend) { $args += "--skip-frontend" }
if ($SkipRuntimes) { $args += "--skip-runtimes" }
& $python[0] ($python[1..($python.Length)] + $args)
if ($LASTEXITCODE -ne 0) { throw "build_dist.py failed with exit code $LASTEXITCODE" }

if ($Installer) {
    $iscc = Get-Command iscc -ErrorAction SilentlyContinue
    if (-not $iscc) {
        $candidates = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe")
        $iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    if (-not $iscc) { throw "Inno Setup 6 (ISCC.exe) not found; install it or omit -Installer" }
    $version = (Get-Content "$Root\engine\pyproject.toml" | Select-String '^version = "(.+)"').Matches[0].Groups[1].Value
    & $iscc "/DAppVersion=$version" "/DStageDir=$Root\$Out\QuakeLogic-HVSR-Studio" "/DOutDir=$Root\$Out" "$Root\packaging\windows\installer.iss"
    if ($LASTEXITCODE -ne 0) { throw "ISCC failed" }
    Write-Host "Installer written to $Out\"
}
