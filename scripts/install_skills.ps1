# install_skills.ps1
# Install kestrel-mcp skills from this repo into the user's Cursor skills dir.
#
# Usage:
#   .\scripts\install_skills.ps1           # symlink (requires admin or dev mode)
#   .\scripts\install_skills.ps1 -Mode copy  # copy instead of symlink
#   .\scripts\install_skills.ps1 -Uninstall
#
# After install, Cursor picks up skills on next restart.

param(
    [ValidateSet("symlink","copy")]
    [string]$Mode = "symlink",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$SourceDir = Join-Path $RepoRoot ".cursor\skills-cursor\kestrel-mcp"
$TargetDir = Join-Path $env:USERPROFILE ".cursor\skills-cursor\kestrel-mcp"

Write-Host "Kestrel-MCP Skills Installer" -ForegroundColor Cyan
Write-Host "  Source: $SourceDir"
Write-Host "  Target: $TargetDir"
Write-Host "  Mode:   $Mode"
Write-Host ""

if (-not (Test-Path $SourceDir)) {
    Write-Host "ERROR: Source skills dir not found: $SourceDir" -ForegroundColor Red
    exit 1
}

if ($Uninstall) {
    if (Test-Path $TargetDir) {
        Write-Host "Uninstalling..." -ForegroundColor Yellow
        $item = Get-Item $TargetDir -Force
        if ($item.LinkType -eq "SymbolicLink" -or $item.LinkType -eq "Junction") {
            Remove-Item $TargetDir -Force
        } else {
            Remove-Item $TargetDir -Recurse -Force
        }
        Write-Host "Removed $TargetDir" -ForegroundColor Green
    } else {
        Write-Host "Nothing to uninstall (target doesn't exist)" -ForegroundColor Yellow
    }
    exit 0
}

# Create parent if missing
$TargetParent = Split-Path $TargetDir -Parent
if (-not (Test-Path $TargetParent)) {
    New-Item -ItemType Directory -Path $TargetParent -Force | Out-Null
}

# Remove existing
if (Test-Path $TargetDir) {
    Write-Host "Target exists, removing..." -ForegroundColor Yellow
    $item = Get-Item $TargetDir -Force
    if ($item.LinkType -eq "SymbolicLink" -or $item.LinkType -eq "Junction") {
        Remove-Item $TargetDir -Force
    } else {
        Remove-Item $TargetDir -Recurse -Force
    }
}

# Install
if ($Mode -eq "symlink") {
    try {
        New-Item -ItemType SymbolicLink -Path $TargetDir -Target $SourceDir -Force | Out-Null
        Write-Host "Symlinked: $TargetDir -> $SourceDir" -ForegroundColor Green
    } catch {
        Write-Host "Symlink failed (need admin or developer mode). Falling back to copy." -ForegroundColor Yellow
        $Mode = "copy"
    }
}

if ($Mode -eq "copy") {
    Copy-Item -Path $SourceDir -Destination $TargetDir -Recurse -Force
    Write-Host "Copied $SourceDir -> $TargetDir" -ForegroundColor Green
    Write-Host "NOTE: Copy mode means edits to repo skills won't sync until you rerun this script." -ForegroundColor Yellow
}

# Inventory
Write-Host ""
Write-Host "Installed skills:" -ForegroundColor Cyan
Get-ChildItem -Path $TargetDir -Recurse -Filter "SKILL.md" | ForEach-Object {
    $rel = $_.FullName.Substring($TargetDir.Length).TrimStart('\')
    Write-Host "  $rel"
}

Write-Host ""
Write-Host "Done. Restart Cursor for skills to activate." -ForegroundColor Green
