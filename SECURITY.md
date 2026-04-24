# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ (current development baseline) |
| < 0.1   | ❌ |

Pro LTS versions (when they exist) will receive 18 months of security patches;
see [`PRODUCT_LINES.md`](./PRODUCT_LINES.md) for LTS policy details.

## Reporting a vulnerability

**Do not file public GitHub issues for security bugs.** Instead:

1. Email the maintainers at `<maintainer-email-placeholder>`
   (TODO: set real address before public release — see RFC-H01).
2. Encrypt with our PGP key (TODO: publish key) for sensitive reports.
3. Include:
   - Affected version / commit SHA
   - Reproduction steps
   - Impact assessment (confidentiality / integrity / availability)
   - Proof-of-concept (optional but helpful)

We commit to:

- **Acknowledge** your report within 48 hours
- **Triage** severity within 5 business days
- **Patch** critical issues within 30 days of confirmation
- **Credit** you in the CHANGELOG (or acknowledge anonymous if preferred)
- **Not prosecute** good-faith security research per our
  [Responsible Use Addendum](./LICENSE)

## Scope

### In scope

- Authentication / authorization bypass in `redteam_mcp.security`
- Path traversal via `safe_path()` bypass
- Prompt injection via tool output not being redacted
- Subprocess argument injection (argv concatenation bugs)
- Credential storage decryption bypass in `CredentialService`
- MCP protocol smuggling / tool shadowing (see V-C4 in AUDIT_V2)
- SQL injection in any raw query path
- Dependency CVEs with direct exploit paths

### Out of scope

- Self-inflicted issues (user disables `scope_enforcement` then "hacks
  themselves")
- Social engineering of maintainers
- Issues in 3rd-party tools (nuclei, sliver, caido, etc.) — report upstream
- Theoretical attacks without a working PoC

## Responsible Use Disclaimer

Kestrel-MCP is an **offensive security tool**. It exists to help authorized
red team operators and security researchers test systems **they have permission
to test**.

**By using this software**, you agree that you:

- Have written authorization to test every target
- Comply with all applicable laws (including but not limited to CFAA, DMCA,
  GDPR, and the laws of your jurisdiction and the target's jurisdiction)
- Accept all liability for misuse

**The maintainers are not liable** for any damages arising from use of this
software, whether authorized or not.

See [`LICENSE`](./LICENSE) for the full legal text including the Responsible
Use Addendum.

## Known hardening gaps (tracked)

See [`AUDIT.md`](./AUDIT.md) and [`AUDIT_V2.md`](./AUDIT_V2.md) for the full
list of known weaknesses. Each has an assigned RFC or is queued for one.

Highest-impact open items:

- **D-9** (AUDIT.md): Credentials stored unencrypted until RFC-003 lands
- **V-C4** (AUDIT_V2.md): MCP tool shadowing prevention — awaits RFC-V03
- **V-A4** (AUDIT_V2.md): Tool output untrust wrapping — awaits RFC-V08
- **D-6/D-7** (AUDIT.md): Brittle parsing of nuclei/sliver stdout — awaits
  dedicated hardening RFC (not yet written)

## Defense-in-depth features (current)

- ✅ Scope enforcement (`ScopeService` + `ScopeGuard`) blocks out-of-scope
  targets by default in Pro edition
- ✅ Subprocess argv-list only (no `shell=True`) throughout the codebase
- ✅ Rate limiting per-tool per-engagement (`RateLimiter` token bucket)
- ✅ Path traversal protection via `safe_path()` for user-supplied file names
- ✅ Sensitive string redaction (`redact()`) on stderr before logging
- ✅ Structured errors (`core_errors.py`) with no leaking of internal state
- ✅ Pydantic `extra="forbid"` on critical models catches schema smuggling
- ⚠️ TLS for HTTP tools — depends on per-tool config (not uniformly enforced)
- ❌ MFA / SSO for multi-user deploys — Pro feature, awaits RFC-Pro-MultiAuth
