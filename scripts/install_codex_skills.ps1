param(
    [string]$RepoRoot,
    [string]$OutputDir = (Join-Path $env:USERPROFILE ".codex\skills"),
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$RepoCandidates = @()
if ($RepoRoot) {
    $RepoCandidates += $RepoRoot
}
$RepoCandidates += (Get-Location).Path
$RepoCandidates += (Split-Path -Parent $PSScriptRoot)

$ResolvedRepoRoot = $null
foreach ($Candidate in $RepoCandidates) {
    if (-not $Candidate) {
        continue
    }
    $ResolvedCandidate = (Resolve-Path -LiteralPath $Candidate).Path
    if (Test-Path (Join-Path $ResolvedCandidate ".cursor\skills-cursor\kestrel-mcp")) {
        $ResolvedRepoRoot = $ResolvedCandidate
        break
    }
}

if (-not $ResolvedRepoRoot) {
    throw "Could not resolve repo root. Pass -RepoRoot explicitly."
}

$RepoRoot = $ResolvedRepoRoot
$CursorSkillRoot = Join-Path $RepoRoot ".cursor\skills-cursor\kestrel-mcp"

if (-not (Test-Path $CursorSkillRoot)) {
    throw "Cursor skill source dir not found: $CursorSkillRoot"
}

$RoutingMap = [ordered]@{
    "Root" = "kestrel-mcp"
    "bootstrap/" = "kestrel-mcp-bootstrap"
    "exec/rfc/" = "kestrel-mcp-exec-rfc"
    "exec/rfc-chain/" = "kestrel-mcp-exec-rfc-chain"
    "exec/rfc-parallel/" = "kestrel-mcp-exec-rfc-parallel"
    "plan/" = "kestrel-mcp-plan"
    "audit/codebase/" = "kestrel-mcp-audit-codebase"
    "audit/rfc/" = "kestrel-mcp-audit-rfc"
    "audit/diff/" = "kestrel-mcp-audit-diff"
    "handoff/" = "kestrel-mcp-handoff"
    "query/" = "kestrel-mcp-query"
    "health/" = "kestrel-mcp-health"
    "roles/spec-author/" = "kestrel-mcp-role-spec-author"
    "roles/backend-engineer/" = "kestrel-mcp-role-backend"
    "roles/code-reviewer/" = "kestrel-mcp-role-code-reviewer"
    "team/" = "kestrel-mcp-team"
}

$Skills = @(
    [pscustomobject]@{
        Name = "kestrel-mcp"
        SourceRel = "SKILL.md"
        Description = "Root skill for the Kestrel-MCP repo. Trigger on kestrel-mcp, kestrel, RFC execution, 审计, 查进度, 交接, or repo-wide workflow questions."
    },
    [pscustomobject]@{
        Name = "kestrel-mcp-bootstrap"
        SourceRel = "bootstrap\SKILL.md"
        Description = "Bootstrap a new agent or human in this repo. Trigger on 开始工作, 我刚接手, new session, project overview, or bootstrap agent."
    },
    [pscustomobject]@{
        Name = "kestrel-mcp-exec-rfc"
        SourceRel = "exec\rfc\SKILL.md"
        Description = "Execute one RFC in this repo. Trigger on run RFC-NNN, implement RFC-NNN, 执行 RFC, or when bootstrap routes here."
    },
    [pscustomobject]@{
        Name = "kestrel-mcp-exec-rfc-chain"
        SourceRel = "exec\rfc-chain\SKILL.md"
        Description = "Execute multiple RFCs in DAG order. Trigger on 连续执行 RFC, batch RFC chain, or sequential RFC rollout."
    },
    [pscustomobject]@{
        Name = "kestrel-mcp-exec-rfc-parallel"
        SourceRel = "exec\rfc-parallel\SKILL.md"
        Description = "Execute multiple RFCs in parallel with worktrees. Trigger on 并行跑 RFC, parallel RFC rollout, or multi-worktree execution."
    },
    [pscustomobject]@{
        Name = "kestrel-mcp-plan"
        SourceRel = "plan\SKILL.md"
        Description = "Write a new RFC or split an oversized RFC. Trigger on 把 X 写成 RFC, draft RFC, split RFC, or plan implementation."
    },
    [pscustomobject]@{
        Name = "kestrel-mcp-audit-codebase"
        SourceRel = "audit\codebase\SKILL.md"
        Description = "Audit the whole codebase in AUDIT_V2 style. Trigger on 审计代码库, gap analysis, audit repo, or find missing pieces."
    },
    [pscustomobject]@{
        Name = "kestrel-mcp-audit-rfc"
        SourceRel = "audit\rfc\SKILL.md"
        Description = "Review RFC format and executability. Trigger on 审这份 RFC, RFC review, RFC compliance, or can this RFC be executed."
    },
    [pscustomobject]@{
        Name = "kestrel-mcp-audit-diff"
        SourceRel = "audit\diff\SKILL.md"
        Description = "Review a diff or PR for bugs, risk, and regressions. Trigger on review 这次改动, PR review, or diff audit."
    },
    [pscustomobject]@{
        Name = "kestrel-mcp-handoff"
        SourceRel = "handoff\SKILL.md"
        Description = "Create or restore a project handoff snapshot. Trigger on 快照, 交接, resume, snapshot progress, or restore session."
    },
    [pscustomobject]@{
        Name = "kestrel-mcp-query"
        SourceRel = "query\SKILL.md"
        Description = "Answer status questions about RFCs, threats, next steps, and metrics. Trigger on 查进度, next RFC, what's done, or progress report."
    },
    [pscustomobject]@{
        Name = "kestrel-mcp-health"
        SourceRel = "health\SKILL.md"
        Description = "Run repo health checks or rollback workflow. Trigger on 健康检查, rollback, verify, full_verify, or fix broken baseline."
    },
    [pscustomobject]@{
        Name = "kestrel-mcp-role-spec-author"
        SourceRel = "roles\spec-author\SKILL.md"
        Description = "RFC author persona for writing crisp executable specs. Trigger on RFC author mode, spec-author persona, or write RFC as an architect."
    },
    [pscustomobject]@{
        Name = "kestrel-mcp-role-backend"
        SourceRel = "roles\backend-engineer\SKILL.md"
        Description = "Execution persona for implementing RFCs. Trigger on backend engineer mode, 执行模式, or implement RFC with disciplined habits."
    },
    [pscustomobject]@{
        Name = "kestrel-mcp-role-code-reviewer"
        SourceRel = "roles\code-reviewer\SKILL.md"
        Description = "Review persona focused on severity-ranked findings. Trigger on 审查模式, code reviewer mode, or review with strict severity levels."
    },
    [pscustomobject]@{
        Name = "kestrel-mcp-team"
        SourceRel = "team\SKILL.md"
        Description = "Team Edition operations workflow. Trigger on team mode, unleash, engagement bootstrap, crew session, or Team Edition ops."
    }
)

function Get-RoutingMarkdown {
    $lines = @()
    foreach ($entry in $RoutingMap.GetEnumerator()) {
        $lines += "- $($entry.Key) -> $($entry.Value)"
    }
    return ($lines -join [Environment]::NewLine)
}

function New-WrapperContent {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Skill
    )

    $SourcePath = Join-Path $CursorSkillRoot $Skill.SourceRel
    if (-not (Test-Path $SourcePath)) {
        throw "Missing source skill: $SourcePath"
    }

    $RoutingSection = Get-RoutingMarkdown

    return @"
---
name: $($Skill.Name)
description: >
  $($Skill.Description)
---

# $($Skill.Name)

This is the Codex wrapper for the Kestrel-MCP Cursor skill set.

## Canonical source

Open and follow this file as the authoritative workflow before taking action:
- $SourcePath

## Repo anchors

- Repo root: $RepoRoot
- Cursor skill tree: $CursorSkillRoot
- Agent entry: $(Join-Path $RepoRoot "README_FOR_AGENT.md")
- Execution protocol: $(Join-Path $RepoRoot "AGENT_EXECUTION_PROTOCOL.md")
- RFC index: $(Join-Path $RepoRoot "rfcs\INDEX.md")

## Wrapper rules

1. Read the canonical source file above before acting.
2. Execute its procedure exactly, including file scope, ordering, and verification rules.
3. When the source skill routes to another Cursor path, use the Codex skill names in the routing map below instead.
4. Keep this port thin: do not fork or rewrite the source workflow unless you are intentionally updating the project skill system itself.

## Codex routing map

$RoutingSection

## Safety invariants

- Do not widen scope beyond the active RFC or the current skill's explicit boundary.
- Do not skip verify_cmd or change it to force green.
- Do not install dependencies unless a dedicated RFC explicitly changes dependency state.
- Do not self-modify these skills while doing normal product work.
- Treat the Cursor skill file as the source of truth when instructions differ.
"@
}

if ($Uninstall) {
    Write-Host "Uninstalling Kestrel-MCP Codex skills from $OutputDir" -ForegroundColor Yellow
    foreach ($Skill in $Skills) {
        $SkillDir = Join-Path $OutputDir $Skill.Name
        if (Test-Path $SkillDir) {
            Remove-Item -LiteralPath $SkillDir -Recurse -Force
            Write-Host "  removed $SkillDir" -ForegroundColor Green
        }
    }
    exit 0
}

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

Write-Host "Installing Kestrel-MCP Codex skills" -ForegroundColor Cyan
Write-Host "  Source: $CursorSkillRoot"
Write-Host "  Target: $OutputDir"
Write-Host ""

foreach ($Skill in $Skills) {
    $SkillDir = Join-Path $OutputDir $Skill.Name
    if (Test-Path $SkillDir) {
        Remove-Item -LiteralPath $SkillDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $SkillDir -Force | Out-Null
    $Content = New-WrapperContent -Skill $Skill
    Set-Content -LiteralPath (Join-Path $SkillDir "SKILL.md") -Value $Content -Encoding UTF8
    Write-Host "  installed $($Skill.Name)" -ForegroundColor Green
}

Write-Host ""
Write-Host "Installed skills:" -ForegroundColor Cyan
foreach ($Skill in $Skills) {
    Write-Host "  $($Skill.Name)"
}

Write-Host ""
Write-Host "Done. Restart Codex or start a new session to pick up the new skills." -ForegroundColor Green
