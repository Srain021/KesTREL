# Acceptable Use Policy

Kestrel MCP wraps offensive security tooling behind an LLM-callable
interface. The barrier to misuse is therefore lower than running the
underlying tools by hand. This document describes the use we will and
will not support.

This policy is in addition to the responsible-use clause in
[LICENSE](./LICENSE) and the reporting rules in [SECURITY.md](./SECURITY.md).

## You may use Kestrel MCP for

- Authorized penetration tests with a signed scope
- Red-team engagements sanctioned by the target's leadership
- Public bug-bounty programs, **strictly within the published scope**
- Capture-the-flag events on isolated lab ranges
- Security research on systems you own or operate
- Defensive emulation in environments you control
- Academic coursework on isolated lab infrastructure

In every case you must keep evidence of authorization. The audit log at
`~/.kestrel/audit.log` is one half of that record; the written
authorization from the target owner is the other half.

## You may not use Kestrel MCP for

- Scanning, exploiting, phishing, or persisting on systems you do not own
  and have no written authorization to test
- Targeting **critical infrastructure** (power, water, healthcare,
  transportation, financial settlement) without explicit owner consent
- Targeting **minors**, journalists, dissidents, activists, or other
  protected groups
- Operations that would violate sanctions, export controls, or the laws
  of your jurisdiction or the target's
- Stalkerware, harassment, or non-consensual surveillance of individuals
- Building services that resell unauthorized intrusion as a feature
- Concealing your activity from a system you have legitimate authorization
  to test (e.g., using the audit-bypass surface to avoid your own client's
  oversight)

If you are unsure whether your engagement qualifies, do not run the tool.
Ask your engagement lead, your legal team, or the target's security
contact first.

## Reporting abuse

If you observe Kestrel MCP being used against you or your organization
without authorization:

1. Preserve evidence (timestamps, source IPs, full HTTP requests).
2. Contact your local computer-crime authority. Unauthorized access is a
   criminal matter; we cannot pursue the attacker on your behalf.
3. Optionally notify the maintainers via the channel in
   [SECURITY.md](./SECURITY.md) so we can decide whether the abuse
   warrants additional guardrails in a future release.

We do not log usage. We cannot identify the attacker for you. Do not
expect a forensic response from this project.

## Maintainer stance

- We will not accept patches that **remove the scope guard, audit log,
  or dry-run mode**.
- We will not accept feature requests whose primary purpose is to make
  unauthorized intrusion easier to perform or harder to detect.
- We will accept defensive-quality patches (better redaction, stricter
  defaults, new audit fields, CVE updates) at any time.
- We will respond to credible legal process. We do not commit to fight
  takedown notices on a contributor's behalf.

This project exists because authorized red-team work needs better
tooling, not because intrusion needs to be more accessible.
