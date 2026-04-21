---
id: RFC-003a
title: Credential service seal/unseal
epic: A-Foundations
status: done
owner: agent
role: backend-engineer
blocking_on: [RFC-002]
edition: both
budget:
  max_files_touched: 8
  max_new_files: 2
  max_lines_added: 360
  max_minutes_human: 45
  max_tokens_model: 12000
files_to_read:
  - src/kestrel_mcp/domain/entities.py
  - src/kestrel_mcp/domain/storage.py
  - src/kestrel_mcp/domain/services/_base.py
  - tests/unit/domain/conftest.py
files_will_touch:
  - rfcs/RFC-003a-credential-service.md             # modified
  - src/kestrel_mcp/domain/services/credential_service.py  # new
  - tests/unit/domain/test_credential_service.py    # new
  - pyproject.toml                                  # modified
  - uv.lock                                         # modified
  - rfcs/INDEX.md                                   # modified
  - CHANGELOG.md                                    # modified
verify_cmd: .venv\Scripts\python.exe -m pytest tests/unit/domain/test_credential_service.py -v
rollback_cmd: git checkout -- .
skill_id: rfc-003a-credential-service
---

# RFC-003a - Credential service seal/unseal

## Mission

Add the credential sealing domain service and unit tests.

## Context

- RFC-003 was too large and stale after the Web UI and package rename work.
- Credential rows and entities already exist, but no service owns seal/unseal.
- G05, G07, D03, and Team credential gates need a stable domain API.

## Non-goals

- Do not wire the service into `ServiceContainer`; RFC-003b does that.
- Do not add UI or tool ref plumbing.
- Do not integrate OS keychains, Vault, or external KMS.

## Design

Implement `CredentialService` with Fernet encryption. The service accepts an
explicit key for tests, otherwise it reads `KESTREL_MCP_CREDENTIAL_KEY`, then
falls back to a generated key file at `KESTREL_DATA_DIR/credential-master.key`
or `~/.kestrel/credential-master.key`.

Only `unseal()` returns plaintext. Other APIs return `Credential` entities with
opaque ciphertext and never log plaintext or ciphertext.

## Steps

### Step 1 - Add direct crypto dependency

REPLACE pyproject.toml
<<<<<<< SEARCH
    "impacket>=0.12",
]
=======
    "impacket>=0.12",
    "cryptography>=43",
]
>>>>>>> REPLACE

RUN .venv\Scripts\python.exe -m uv lock

### Step 2 - Add CredentialService

WRITE src/kestrel_mcp/domain/services/credential_service.py

### Step 3 - Add service tests

WRITE tests/unit/domain/test_credential_service.py

### Step 4 - Update trackers

REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-003 | Credential Store (domain + API)   | blocked ⚠ | RFC-002  |       |
=======
| RFC-003 | Credential Store (split umbrella) | blocked ⚠ | RFC-002  | agent |
| RFC-003a | Credential service seal/unseal   | done   | RFC-002     | agent |
>>>>>>> REPLACE

REPLACE CHANGELOG.md
<<<<<<< SEARCH
## [Unreleased]
=======
## [Unreleased]

### Added
- `RFC-003a` - Added encrypted credential seal/unseal domain service,
  Fernet key resolution, direct `cryptography` dependency, and unit tests.
>>>>>>> REPLACE

### Step 5 - Verify

RUN .venv\Scripts\python.exe scripts\validate_rfc.py rfcs\RFC-003a-credential-service.md

RUN .venv\Scripts\python.exe -m pytest tests/unit/domain/test_credential_service.py -v

RUN .venv\Scripts\python.exe scripts\full_verify.py

## Tests

- Seal/unseal roundtrip stores ciphertext, not plaintext.
- Empty plaintext is rejected.
- Invalid refs and revoked credentials cannot unseal.
- Listing can filter by kind.
- Default key file generation works without leaking plaintext.

## Post-checks

- `CredentialService` is not yet exported through `ServiceContainer`.
- `uv.lock` records `cryptography` as a direct dependency.
- `git diff --stat` stays inside `files_will_touch`.

## Rollback plan

Run `git checkout -- .` before commit.

## Updates to other docs

- Add RFC-003a to the RFC index.
- Add a changelog entry.

## Notes for executor

- Use `KESTREL_MCP_CREDENTIAL_KEY`, not the old pre-H01 env prefix.
- Do not log plaintext or ciphertext.
- Keep container/context integration for RFC-003b.

## Changelog

- **2026-04-21** - Executed: added direct crypto dependency, CredentialService,
  unit tests, lockfile refresh, RFC index, and changelog entry.
- **2026-04-21** - Expanded from the blocked RFC-003 into split part A.
