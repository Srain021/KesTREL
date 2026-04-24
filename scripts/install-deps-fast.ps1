#Requires -Version 5.1
<#
.SYNOPSIS
    Install the smallest possible subset of redteam-mcp dependencies
    tolerant of slow/unstable networks (typical of split-tunnel VPN).

.DESCRIPTION
    Splits the dependency list into two tiers:
      * Tier 1 — REQUIRED for `redteam-mcp doctor` & offline tests
      * Tier 2 — REQUIRED for `redteam-mcp serve`
      * Tier 3 — nice-to-have
    If Tier 1 fails we stop early so the user knows to fix network first.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\install-deps-fast.ps1
#>

[CmdletBinding()]
param(
    [string]$Index = "https://pypi.tuna.tsinghua.edu.cn/simple",
    [int]$Timeout = 30,
    [int]$Retries = 5
)

$ErrorActionPreference = "Continue"
$commonFlags = @("--index-url", $Index, "--timeout", $Timeout, "--retries", $Retries, "-q")

function Install-Tier([string]$Name, [string[]]$Packages) {
    Write-Host "`n==> Tier $Name : $($Packages -join ', ')" -ForegroundColor Cyan
    $ok = $true
    foreach ($p in $Packages) {
        Write-Host "    installing $p..." -NoNewline
        $start = Get-Date
        & python -m pip install @commonFlags $p
        $dur = (Get-Date) - $start
        if ($LASTEXITCODE -eq 0) {
            Write-Host ("  OK ({0:N1}s)" -f $dur.TotalSeconds) -ForegroundColor Green
        } else {
            Write-Host "  FAIL" -ForegroundColor Red
            $ok = $false
        }
    }
    return $ok
}

Write-Host "==> redteam-mcp dependency installer (slow-network tolerant)" -ForegroundColor Cyan
Write-Host "    Index: $Index"
Write-Host "    Per-package timeout: $Timeout s, retries: $Retries`n"

$tier1 = @("pydantic", "pydantic-settings", "pyyaml", "anyio")
$tier2 = @("mcp", "structlog", "httpx", "typer")
$tier3 = @("rich", "shodan", "python-dotenv", "jinja2")

if (-not (Install-Tier "1 (required for offline tests)" $tier1)) {
    Write-Host "`n[FATAL] Tier 1 failed — fix your network before continuing." -ForegroundColor Red
    Write-Host "Hint: if you are on Tailscale Exit Node, disable it with:"
    Write-Host "      tailscale set --exit-node="
    exit 1
}

Install-Tier "2 (required for MCP serve)" $tier2 | Out-Null
Install-Tier "3 (nice-to-have)" $tier3 | Out-Null

Write-Host "`n==> Checking import health..." -ForegroundColor Cyan
$critical = @("pydantic", "pydantic_settings", "yaml", "anyio")
$broken = @()
foreach ($m in $critical) {
    $out = & python -c "import $m; print('ok')" 2>&1
    if ($LASTEXITCODE -ne 0) { $broken += $m }
}
if ($broken.Count -eq 0) {
    Write-Host "All critical packages importable." -ForegroundColor Green
    Write-Host "`nYou can now run the offline tests:" -ForegroundColor Yellow
    Write-Host "    pytest tests/test_security.py tests/test_config.py -v"
} else {
    Write-Host "Broken imports: $($broken -join ', ')" -ForegroundColor Red
}
