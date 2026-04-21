---
id: RFC-T00b
title: Team runtime feature gates
epic: T-Team
status: done
owner: agent
role: backend-engineer
blocking_on: [RFC-T00, RFC-003b, RFC-004]
edition: both
budget:
  max_files_touched: 10
  max_new_files: 1
  max_lines_added: 260
  max_minutes_human: 45
  max_tokens_model: 10000
files_to_read:
  - src/kestrel_mcp/features.py
  - src/kestrel_mcp/server.py
  - src/kestrel_mcp/core/services.py
  - src/kestrel_mcp/domain/services/credential_service.py
  - tests/unit/core/test_rate_limit.py
  - tests/unit/domain/test_credential_service.py
files_will_touch:
  - rfcs/RFC-T00b-team-runtime-feature-gates.md  # modified
  - src/kestrel_mcp/domain/services/credential_service.py  # modified
  - src/kestrel_mcp/core/services.py             # modified
  - src/kestrel_mcp/server.py                    # modified
  - tests/unit/domain/test_credential_service.py # modified
  - README.md                                    # modified
  - SECURITY.md                                  # modified
  - CHANGELOG.md                                 # modified
  - rfcs/INDEX.md                                # modified
verify_cmd: .venv\Scripts\python.exe -m pytest tests/unit/core/test_rate_limit.py tests/unit/domain/test_credential_service.py -v
rollback_cmd: git checkout -- .
skill_id: rfc-t00b-team-runtime-feature-gates
---

# RFC-T00b - Team runtime feature gates

## Mission

Consume the remaining Team runtime flags for rate limiting and credentials.

## Context

- RFC-A04 added `rate_limit_enabled` and `credential_encryption_required`.
- RFC-T00 intentionally deferred these two gates.
- RFC-004 already added the rate-limit gate in `server._apply_rate_limit()`
  and tests prove Team skips buckets while Pro enforces them.
- RFC-003a/b added the credential vault; it still always encrypts at rest.

## Non-goals

- Do not change scope enforcement; RFC-T00 already owns that.
- Do not retrofit Impacket/G05/G07 handlers to consume `cred://` refs.
- Do not add OS keychain, Vault, or external KMS.

## Design

Keep Pro conservative: `credential_encryption_required=True` seals secrets with
Fernet and refuses to unseal plaintext-at-rest rows. Team can set
`credential_encryption_required=False`; in that mode `CredentialService` stores
`plaintext-v1` rows intentionally for shared crew workflows and can unseal them.
`ServiceContainer` accepts the flag and `serve()` passes it from resolved
settings. Rate-limit gating is left unchanged but documented in this RFC
because it is already implemented and covered.

## Steps

### Step 1 - Add credential encryption mode

REPLACE src/kestrel_mcp/domain/services/credential_service.py
<<<<<<< SEARCH
from pathlib import Path
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
=======
from pathlib import Path
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/domain/services/credential_service.py
<<<<<<< SEARCH
_KEY_ENV = "KESTREL_MCP_CREDENTIAL_KEY"
_KDF = "fernet-v1"
=======
_KEY_ENV = "KESTREL_MCP_CREDENTIAL_KEY"
_KDF = "fernet-v1"
_PLAINTEXT_KDF = "plaintext-v1"
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/domain/services/credential_service.py
<<<<<<< SEARCH
    def __init__(
        self,
        *args: object,
        key: str | bytes | None = None,
        key_path: Path | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._fernet = Fernet(_resolve_key(key=key, key_path=key_path))
=======
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        *,
        key: str | bytes | None = None,
        key_path: Path | None = None,
        encryption_required: bool = True,
    ) -> None:
        super().__init__(sessionmaker)
        self.encryption_required = encryption_required
        self._key = key
        self._key_path = key_path
        self._fernet: Fernet | None = None
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/domain/services/credential_service.py
<<<<<<< SEARCH
        try:
            ciphertext = self._fernet.encrypt(plaintext.encode("utf-8"))
        except Exception as exc:  # pragma: no cover - Fernet errors are defensive
            raise CredentialSealError("Credential encryption failed.") from exc
=======
        if self.encryption_required:
            try:
                ciphertext = self._get_fernet().encrypt(plaintext.encode("utf-8"))
            except Exception as exc:  # pragma: no cover - Fernet errors are defensive
                raise CredentialSealError("Credential encryption failed.") from exc
            secret_kdf = _KDF
        else:
            ciphertext = plaintext.encode("utf-8")
            secret_kdf = _PLAINTEXT_KDF
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/domain/services/credential_service.py
<<<<<<< SEARCH
            secret_ciphertext=ciphertext,
            secret_kdf=_KDF,
=======
            secret_ciphertext=ciphertext,
            secret_kdf=secret_kdf,
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/domain/services/credential_service.py
<<<<<<< SEARCH
        try:
            plaintext = self._fernet.decrypt(row.secret_ciphertext).decode("utf-8")
        except InvalidToken as exc:
            raise CredentialSealError("Credential decryption failed.") from exc
=======
        plaintext = self._unseal_row(row)
>>>>>>> REPLACE

### Step 2 - Wire ServiceContainer and server settings

REPLACE src/kestrel_mcp/core/services.py
<<<<<<< SEARCH
    def __init__(
        self,
        engine: AsyncEngine,
        sessionmaker: async_sessionmaker[AsyncSession],
        database_url: str,
    ) -> None:
=======
    def __init__(
        self,
        engine: AsyncEngine,
        sessionmaker: async_sessionmaker[AsyncSession],
        database_url: str,
        *,
        credential_encryption_required: bool = True,
    ) -> None:
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/core/services.py
<<<<<<< SEARCH
        self.finding = FindingService(sessionmaker)
        self.credential = CredentialService(sessionmaker)
=======
        self.finding = FindingService(sessionmaker)
        self.credential = CredentialService(
            sessionmaker,
            encryption_required=credential_encryption_required,
        )
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/core/services.py
<<<<<<< SEARCH
    def from_url(cls, database_url: str, *, echo: bool = False) -> ServiceContainer:
        engine = make_engine(database_url, echo=echo)
        sm = make_sessionmaker(engine)
        return cls(engine=engine, sessionmaker=sm, database_url=database_url)
=======
    def from_url(
        cls,
        database_url: str,
        *,
        echo: bool = False,
        credential_encryption_required: bool = True,
    ) -> ServiceContainer:
        engine = make_engine(database_url, echo=echo)
        sm = make_sessionmaker(engine)
        return cls(
            engine=engine,
            sessionmaker=sm,
            database_url=database_url,
            credential_encryption_required=credential_encryption_required,
        )
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/core/services.py
<<<<<<< SEARCH
    def in_memory(cls) -> ServiceContainer:
=======
    def in_memory(cls, *, credential_encryption_required: bool = True) -> ServiceContainer:
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/core/services.py
<<<<<<< SEARCH
        return cls.from_url("sqlite+aiosqlite:///:memory:")
=======
        return cls.from_url(
            "sqlite+aiosqlite:///:memory:",
            credential_encryption_required=credential_encryption_required,
        )
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/core/services.py
<<<<<<< SEARCH
    def default_on_disk(cls, *, data_dir: Path | None = None) -> ServiceContainer:
=======
    def default_on_disk(
        cls,
        *,
        data_dir: Path | None = None,
        credential_encryption_required: bool = True,
    ) -> ServiceContainer:
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/core/services.py
<<<<<<< SEARCH
        return cls.from_url(url)
=======
        return cls.from_url(
            url,
            credential_encryption_required=credential_encryption_required,
        )
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/server.py
<<<<<<< SEARCH
        container = ServiceContainer.default_on_disk()
=======
        container = ServiceContainer.default_on_disk(
            credential_encryption_required=settings.features.credential_encryption_required,
        )
>>>>>>> REPLACE

### Step 3 - Add tests

APPEND tests/unit/domain/test_credential_service.py

### Step 4 - Update docs and trackers

REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-T00 | Team unleashed mode                | done   |             | agent |
| RFC-T08 | Team bootstrap command             | done   |             | agent |
=======
| RFC-T00 | Team unleashed mode                | done   |             | agent |
| RFC-T00b | Team runtime feature gates        | done   | RFC-T00,RFC-003b,RFC-004 | agent |
| RFC-T08 | Team bootstrap command             | done   |             | agent |
>>>>>>> REPLACE

REPLACE CHANGELOG.md
<<<<<<< SEARCH
### Added
- `RFC-003b` - Wired `CredentialService` into `ServiceContainer` and
=======
### Added
- `RFC-T00b` - Consumed Team runtime feature gates: documented existing
  rate-limit bypass coverage and wired `credential_encryption_required` into
  `CredentialService`, `ServiceContainer`, and server startup.
- `RFC-003b` - Wired `CredentialService` into `ServiceContainer` and
>>>>>>> REPLACE

REPLACE SECURITY.md
<<<<<<< SEARCH
- **D-9 follow-up** (AUDIT.md): Credentials are encrypted at rest by
  `CredentialService`; some tool wrappers still accept plaintext input args
  until follow-up RFCs switch them to `cred://` references.
=======
- **D-9 follow-up** (AUDIT.md): Pro credentials are encrypted at rest by
  `CredentialService`. Team edition may intentionally store plaintext-at-rest
  credentials when `credential_encryption_required=false`; some tool wrappers
  still accept plaintext input args until follow-up RFCs switch them to
  `cred://` references.
>>>>>>> REPLACE

REPLACE README.md
<<<<<<< SEARCH
- `credential_encryption_required = false` — Team may accept plaintext input
  into the credential vault, while stored credentials are still sealed at rest.
=======
- `credential_encryption_required = false` — Team may store plaintext-at-rest
  credentials in the vault for crew sharing; Pro keeps encrypted-at-rest
  storage by default.
>>>>>>> REPLACE

### Step 5 - Verify

RUN .venv\Scripts\python.exe scripts\validate_rfc.py rfcs\RFC-T00b-team-runtime-feature-gates.md

RUN .venv\Scripts\python.exe -m pytest tests/unit/core/test_rate_limit.py tests/unit/domain/test_credential_service.py -v

RUN .venv\Scripts\python.exe scripts\full_verify.py

RUN .venv\Scripts\ruff.exe check src/ tests/

RUN .venv\Scripts\mypy.exe --strict src/kestrel_mcp/core src/kestrel_mcp/domain src/kestrel_mcp/webui

## Tests

- Existing rate-limit tests continue proving Team skips buckets and Pro enforces.
- CredentialService plaintext mode stores `plaintext-v1` and avoids key files.
- Pro mode refuses to unseal plaintext-at-rest rows.
- ServiceContainer passes the credential gate to CredentialService.

## Post-checks

- `git diff --stat` stays inside `files_will_touch`.
- `show-config --edition team` still shows both gates disabled.
- Working tree is clean after commit.

## Rollback plan

Run `git checkout -- .` before commit.

## Updates to other docs

- Add RFC-T00b to the Team RFC table.
- Add CHANGELOG entry.
- Update README and SECURITY wording around Team plaintext-at-rest behavior.

## Notes for executor

- Do not remove existing rate-limit tests; they are the proof for that half.
- Keep plaintext mode explicitly labeled `plaintext-v1`.
- Pro must reject plaintext-at-rest rows rather than silently returning them.

## Changelog

- **2026-04-21** - Executed: wired credential encryption gate, preserved
  existing rate-limit gate tests, updated docs and trackers.
- **2026-04-21** - Expanded from the post-Team-MVP T00b follow-up.
