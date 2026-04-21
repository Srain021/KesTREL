---
name: kestrel-mcp-exec-rfc-parallel
description: >
  Execute multiple RFCs in parallel with worktrees. Trigger on 骞惰璺?RFC, parallel RFC rollout, or multi-worktree execution.
---

# kestrel-mcp-exec-rfc-parallel

This is the Codex wrapper for the Kestrel-MCP Cursor skill set.

## Canonical source

Open and follow this file as the authoritative workflow before taking action:
- D:\TG PROJECT\kestrel-mcp\.cursor\skills-cursor\kestrel-mcp\exec\rfc-parallel\SKILL.md

## Repo anchors

- Repo root: D:\TG PROJECT\kestrel-mcp
- Cursor skill tree: D:\TG PROJECT\kestrel-mcp\.cursor\skills-cursor\kestrel-mcp
- Agent entry: D:\TG PROJECT\kestrel-mcp\README_FOR_AGENT.md
- Execution protocol: D:\TG PROJECT\kestrel-mcp\AGENT_EXECUTION_PROTOCOL.md
- RFC index: D:\TG PROJECT\kestrel-mcp\rfcs\INDEX.md

## Wrapper rules

1. Read the canonical source file above before acting.
2. Execute its procedure exactly, including file scope, ordering, and verification rules.
3. When the source skill routes to another Cursor path, use the Codex skill names in the routing map below instead.
4. Keep this port thin: do not fork or rewrite the source workflow unless you are intentionally updating the project skill system itself.

## Codex routing map

- Root -> kestrel-mcp
- bootstrap/ -> kestrel-mcp-bootstrap
- exec/rfc/ -> kestrel-mcp-exec-rfc
- exec/rfc-chain/ -> kestrel-mcp-exec-rfc-chain
- exec/rfc-parallel/ -> kestrel-mcp-exec-rfc-parallel
- plan/ -> kestrel-mcp-plan
- audit/codebase/ -> kestrel-mcp-audit-codebase
- audit/rfc/ -> kestrel-mcp-audit-rfc
- audit/diff/ -> kestrel-mcp-audit-diff
- handoff/ -> kestrel-mcp-handoff
- query/ -> kestrel-mcp-query
- health/ -> kestrel-mcp-health
- roles/spec-author/ -> kestrel-mcp-role-spec-author
- roles/backend-engineer/ -> kestrel-mcp-role-backend
- roles/code-reviewer/ -> kestrel-mcp-role-code-reviewer
- team/ -> kestrel-mcp-team

## Safety invariants

- Do not widen scope beyond the active RFC or the current skill's explicit boundary.
- Do not skip verify_cmd or change it to force green.
- Do not install dependencies unless a dedicated RFC explicitly changes dependency state.
- Do not self-modify these skills while doing normal product work.
- Treat the Cursor skill file as the source of truth when instructions differ.
