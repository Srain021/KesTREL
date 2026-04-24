#Requires -Version 5.1
<#
.SYNOPSIS
    One-shot Windows installer for redteam-mcp.

.DESCRIPTION
    1. Creates / re-uses a Python venv at %USERPROFILE%\.redteam-mcp\venv
    2. Installs this project in editable mode along with its deps.
    3. Runs `redteam-mcp doctor` to surface missing tools / API keys.
    4. Offers to register the server with Cursor via register_cursor.py.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
#>

[CmdletBinding()]
param(
    [string]$VenvDir = "$env:USERPROFILE\.redteam-mcp\venv",
    [switch]$SkipCursorRegister
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

Write-Host "==> redteam-mcp installer" -ForegroundColor Cyan
Write-Host "    Repo:  $repoRoot"
Write-Host "    Venv:  $VenvDir"

$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue) }
if (-not $python) { throw "Python 3.10+ not found on PATH. Install Python first." }

Write-Host "==> Creating venv..." -ForegroundColor Cyan
if (-not (Test-Path $VenvDir)) {
    & $python.Source -m venv $VenvDir
}

$venvPy = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $venvPy)) { throw "venv python not found at $venvPy" }

Write-Host "==> Upgrading pip / build tooling..." -ForegroundColor Cyan
& $venvPy -m pip install --upgrade pip wheel setuptools

Write-Host "==> Installing redteam-mcp (editable + dev extras)..." -ForegroundColor Cyan
& $venvPy -m pip install -e "$repoRoot[dev]"

Write-Host "==> Running doctor..." -ForegroundColor Cyan
& $venvPy -m redteam_mcp doctor

if (-not $SkipCursorRegister) {
    Write-Host ""
    Write-Host "==> Register with Cursor now? (y/N)" -ForegroundColor Yellow -NoNewline
    $ans = Read-Host " "
    if ($ans -match '^(y|Y)') {
        & $venvPy (Join-Path $repoRoot "scripts\register_cursor.py")
    }
}

Write-Host ""
Write-Host "DONE. Activate the venv with:" -ForegroundColor Green
Write-Host "    $VenvDir\Scripts\Activate.ps1"
