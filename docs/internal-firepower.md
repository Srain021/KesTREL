# Internal Firepower Edition

`internal` is the private crew preset for authorized lab, CTF, and internal
red-team operations. It is separate from `team` so crews can turn on the full
tool surface without changing the safer Team MVP baseline.

## What It Changes

- Enables every bundled tool module by default: Shodan, Nuclei, Subfinder,
  httpx, Nmap, ffuf, Impacket, BloodHound, Caido, Evilginx, Sliver, Havoc,
  and Ligolo.
- Sets `scope_enforcement = warn_only`: the MCP server logs scope violations
  instead of blocking them.
- Disables rate limiting and soft timeouts for long-running operations.
- Allows plaintext credential storage until the CredentialService rollout is
  complete.
- Keeps audit logging and untrusted tool-output wrapping enabled.

## Start It

```powershell
kestrel --edition internal show-config
kestrel --edition internal team bootstrap --dry-run --name op-firepower --scope "target.lab,*.internal"
kestrel --edition internal serve
```

For MCP clients, use:

```json
{
  "command": "python",
  "args": ["-m", "kestrel_mcp", "--edition", "internal", "serve"],
  "env": {
    "KESTREL_EDITION": "internal",
    "KESTREL_MCP_SECURITY__AUTHORIZED_SCOPE": "target.lab,*.internal"
  }
}
```

## Operator Rule

This edition gives the team more reach, not automatic permission to fire.
High-risk actions still flow through the readiness and fire-control guidance:
prepare the packet, verify scope and rollback, then wait for a human operator
to approve execution.
