# SKILLS INTEGRATION

> Cursor Agent Skills for Kestrel-MCP. This document describes the **actual
> delivered** skills and how they plug into the RFC + AGENT_EXECUTION_PROTOCOL
> system.

**Version**: 2.0 (superseded v1 design doc with real implementation)
**Last changed**: 2026-04-21

---

## 1. What got delivered

15 `SKILL.md` files under `.cursor/skills-cursor/kestrel-mcp/`, organized in 7
categories, plus an install script.

```
.cursor/skills-cursor/kestrel-mcp/
├── README.md                         (navigation doc)
├── SKILL.md                          (root — always loaded)
├── bootstrap/SKILL.md                (new agent onboarding)
├── exec/
│   ├── rfc/SKILL.md                  (single RFC execution)
│   ├── rfc-chain/SKILL.md            (sequential multi-RFC)
│   └── rfc-parallel/SKILL.md         (worktree parallel multi-RFC)
├── plan/SKILL.md                     (author + split RFCs)
├── audit/
│   ├── codebase/SKILL.md             (AUDIT_V2-style gap analysis)
│   ├── rfc/SKILL.md                  (RFC format validation)
│   └── diff/SKILL.md                 (PR/diff review)
├── handoff/SKILL.md                  (snapshot + resume)
├── query/SKILL.md                    (status lookups)
├── health/SKILL.md                   (verify + rollback)
├── roles/
│   ├── spec-author/SKILL.md          (persona for RFC authoring)
│   ├── backend-engineer/SKILL.md     (persona for RFC execution)
│   └── code-reviewer/SKILL.md        (persona for reviews)
└── team/SKILL.md                     (Team Edition ops)

scripts/install_skills.ps1            (symlink or copy into user Cursor dir)
```

Plus: `.cursor/skills-cursor/kestrel-mcp/README.md` as human-readable navigation.

---

## 2. The workflow mental model

```
         ┌─────────────┐
         │  bootstrap  │  (one-time per session)
         └──────┬──────┘
                │
                ▼
         ┌─────────────┐     ┌─────────────┐
    ┌───▶│    query    │────▶│    plan     │  (author new RFC)
    │    └──────┬──────┘     └──────┬──────┘
    │           │                   │
    │           ▼                   ▼
    │    ┌─────────────┐     ┌─────────────┐
    │    │    exec     │     │    audit    │  (RFC format check)
    │    │   (rfc /    │     │   (rfc)     │
    │    │    chain /  │     └──────┬──────┘
    │    │   parallel) │            │
    │    └──────┬──────┘            │
    │           │  ◀─────────────────┘
    │           ▼
    │    ┌─────────────┐
    │    │   health    │  (verify_state)
    │    └──────┬──────┘
    │           │
    │           ├───────┐
    │           ▼       ▼
    │    ┌─────────────┐
    └────│   audit/    │  (PR review post-exec)
         │    diff     │
         └──────┬──────┘
                │
                ▼
         ┌─────────────┐
         │  handoff    │  (snapshot for next session)
         └─────────────┘

         Orthogonal: roles/ (activate any time for persona)
                     team/  (activate when edition=team)
```

---

## 3. Key differences from v1 design

| v1 plan (old SKILLS_INTEGRATION.md) | v2 actual |
|-------------------------------------|-----------|
| Per-RFC skill files (`rfc-001`, `rfc-002`, ...) | **Dropped.** One `exec/rfc/` handles any RFC — routing is via RFC id parameter. Scaling 40+ per-RFC stubs was waste. |
| Flat skill list | **Hierarchical** tree (category/skill/SKILL.md). Cursor supports this. |
| No audit skills | **3 audit skills** (codebase, rfc, diff) — per AUDIT_V2 lessons |
| No handoff skill | **Added** (snapshot + resume) — critical for multi-session work |
| No team skill | **Added** — Team Edition needs its own ops flow |
| No install automation | **Added** `install_skills.ps1` |

---

## 4. Skill-skill interaction rules

Skills **do not call each other directly**. They **route** — suggest the user
activate another skill. This is because Cursor's matcher needs the user message
to match; cross-skill invocation would bypass that.

Example routing in `exec/rfc/` Step 5 (verify_cmd fails):
> "After 3 fails: set RFC `status: blocked`, ... route to `audit/rfc/` skill"

That means the skill *tells the user/agent* to use `audit/rfc/` next, not auto-invokes it.

---

## 5. Local model (Qwen-7B) compatibility

Each skill is < 200 lines so fits in a typical 4k window alongside an open file.

Cookbook for weak models:
- `bootstrap/` is safe first skill (read-only, no ambiguity)
- `exec/rfc/` has zero creative decisions (every step is WRITE/REPLACE/RUN)
- `roles/backend-engineer/` pairs with `exec/rfc/` for style consistency
- `query/` is safe to call anywhere (read-only)
- `health/` is the safety net (verify + rollback)

Discouraged for weak models (requires judgment):
- `plan/` (writing good RFCs is a strong-model task)
- `audit/codebase/` (finding novel gaps requires broader context)
- `exec/rfc-parallel/` (worktree management has many failure modes)

---

## 6. Install + activation

### Install

```powershell
cd "d:\TG PROJECT\redteam-mcp"
.\scripts\install_skills.ps1
```

Symlinks `.cursor/skills-cursor/kestrel-mcp/` in repo to
`$env:USERPROFILE\.cursor\skills-cursor\kestrel-mcp\`. Cursor picks it up on
next launch.

### Activation

Skills activate automatically by matching user's natural language against each
skill's `description` field. No manual `/activate` needed.

To confirm a skill is active, look for Cursor's skill indicator in the UI
(varies by version). Or verify: ask agent "what skills are you using right
now?"

---

## 7. Security considerations

All skills ship these forbidden-action constraints:

- No `pip install` / `uv add` / `curl` / `wget` during skill execution
- No `Get-ChildItem -Recurse` / `find` / unrestricted `grep`
- No writing outside `files_will_touch` (or explicit scope for non-RFC skills)
- No modifying skills themselves during execution (prevents self-exfiltration)
- No executing `verify_cmd` for "testing" purposes outside of RFC execution flow

If a skill ever needs a dependency install, it routes back to user: "this needs
a new RFC to add dep X".

---

## 8. Maintenance

- **Adding a new skill**: write `<category>/<name>/SKILL.md`, update root
  `SKILL.md` routing table + `README.md` skill tree + this doc.
- **Changing a skill**: edit in-place. Commit. Users re-install or (if
  symlinked) automatically pick up next Cursor reload.
- **Removing a skill**: delete file + purge references from root SKILL.md +
  README + this doc.

---

## 9. Future extensions (not yet done)

- `exec/rfc-resume/SKILL.md` — resume a mid-flight RFC from HANDOFF.md
- `audit/security/SKILL.md` — specialized security audit (STRIDE-focused)
- `team/debrief/SKILL.md` — structured post-op debrief
- `roles/test-writer/SKILL.md` — persona for test-authoring sprints
- `roles/frontend-engineer/SKILL.md` — when Tier 2/3 Web UI RFCs start

These are stubs — add when actually needed, not pre-emptively.

---

## 10. Changelog

- **2.0 (2026-04-21)** — Real implementation delivered. 15 skills across 7
  categories + install script. Dropped v1's per-RFC skill plan.
- **1.0 (2026-04-21 earlier)** — Design document only. See git history.
