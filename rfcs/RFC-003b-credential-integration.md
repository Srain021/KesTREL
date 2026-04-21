---
id: RFC-003b
title: Credential service integration and release docs
epic: A-Foundations
status: done
owner: agent
role: backend-engineer
blocking_on: [RFC-003a]
edition: both
budget:
  max_files_touched: 10
  max_new_files: 1
  max_lines_added: 280
  max_minutes_human: 45
  max_tokens_model: 10000
files_to_read:
  - src/kestrel_mcp/domain/services/__init__.py
  - src/kestrel_mcp/core/services.py
  - src/kestrel_mcp/core/context.py
  - tests/unit/core/test_context.py
  - SECURITY.md
  - README.md
files_will_touch:
  - rfcs/RFC-003b-credential-integration.md  # modified
  - rfcs/RFC-003-credential-store.md         # modified
  - rfcs/INDEX.md                            # modified
  - CHANGELOG.md                             # modified
  - src/kestrel_mcp/domain/services/__init__.py  # modified
  - src/kestrel_mcp/core/services.py         # modified
  - src/kestrel_mcp/core/context.py          # modified
  - tests/unit/core/test_context.py          # modified
  - SECURITY.md                              # modified
  - README.md                                # modified
verify_cmd: .venv\Scripts\python.exe -m pytest tests/unit/core/test_context.py tests/unit/domain/test_credential_service.py -v
rollback_cmd: git checkout -- .
skill_id: rfc-003b-credential-integration
---

# RFC-003b - Credential service integration and release docs

## Mission

Wire CredentialService into the runtime container and close the RFC-003 umbrella.

## Context

- RFC-003a added and tested the standalone encrypted credential service.
- Tool and UI integrations need `ctx.credential` / `container.credential`.
- The original RFC-003 file is stale and over budget, so this RFC marks it as
  completed-by-split instead of trying to execute its old SEARCH blocks.

## Non-goals

- Do not retrofit Impacket, future Metasploit, or NetExec handlers to consume
  credential refs yet.
- Do not add credential vault UI.
- Do not add OS keychain, Vault, or external KMS support.

## Design

Export `CredentialService`, register one instance on `ServiceContainer`, and
expose it through `RequestContext.credential`. Update core context tests to
prove a request can seal and unseal through the context. Update release docs to
say credentials are encrypted at rest while acknowledging that some tool
wrappers still accept plaintext input arguments until follow-up RFCs adopt
`cred://` references.

## Steps

### Step 1 - Export the service

REPLACE src/kestrel_mcp/domain/services/__init__.py
<<<<<<< SEARCH
from .engagement_service import EngagementService
from .finding_service import FindingService
from .scope_service import ScopeService
from .target_service import TargetService
=======
from .credential_service import CredentialService
from .engagement_service import EngagementService
from .finding_service import FindingService
from .scope_service import ScopeService
from .target_service import TargetService
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/domain/services/__init__.py
<<<<<<< SEARCH
__all__ = [
    "EngagementService",
    "FindingService",
    "ScopeService",
    "TargetService",
]
=======
__all__ = [
    "CredentialService",
    "EngagementService",
    "FindingService",
    "ScopeService",
    "TargetService",
]
>>>>>>> REPLACE

### Step 2 - Wire ServiceContainer and RequestContext

REPLACE src/kestrel_mcp/core/services.py
<<<<<<< SEARCH
from ..domain.services import (
    EngagementService,
    FindingService,
    ScopeService,
    TargetService,
)
=======
from ..domain.services import (
    CredentialService,
    EngagementService,
    FindingService,
    ScopeService,
    TargetService,
)
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/core/services.py
<<<<<<< SEARCH
        self.target = TargetService(sessionmaker)
        self.finding = FindingService(sessionmaker)
=======
        self.target = TargetService(sessionmaker)
        self.finding = FindingService(sessionmaker)
        self.credential = CredentialService(sessionmaker)
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/core/context.py
<<<<<<< SEARCH
if TYPE_CHECKING:
    from ..domain.services import EngagementService, FindingService, ScopeService, TargetService
    from .services import ServiceContainer
=======
if TYPE_CHECKING:
    from ..domain.services import (
        CredentialService,
        EngagementService,
        FindingService,
        ScopeService,
        TargetService,
    )
    from .services import ServiceContainer
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/core/context.py
<<<<<<< SEARCH
    @property
    def finding(self) -> FindingService:
        return self.container.finding

    # ---- engagement helpers ----
=======
    @property
    def finding(self) -> FindingService:
        return self.container.finding

    @property
    def credential(self) -> CredentialService:
        return self.container.credential

    # ---- engagement helpers ----
>>>>>>> REPLACE

### Step 3 - Add integration test

REPLACE tests/unit/core/test_context.py
<<<<<<< SEARCH
@pytest.fixture
async def container():
    c = ServiceContainer.in_memory()
=======
@pytest.fixture
async def container(tmp_path, monkeypatch):
    monkeypatch.setenv("KESTREL_DATA_DIR", str(tmp_path))
    c = ServiceContainer.in_memory()
>>>>>>> REPLACE

REPLACE tests/unit/core/test_context.py
<<<<<<< SEARCH
async def test_require_engagement_with(container):
    e = await container.engagement.create(
        name="x",
        display_name="x",
        engagement_type=ent.EngagementType.CTF,
        client="c",
    )
    async with container.open_context(engagement_id=e.id) as ctx:
        assert ctx.require_engagement() == e.id
        assert ctx.has_engagement()


async def test_ensure_scope_noop_without_engagement(container):
=======
async def test_require_engagement_with(container):
    e = await container.engagement.create(
        name="x",
        display_name="x",
        engagement_type=ent.EngagementType.CTF,
        client="c",
    )
    async with container.open_context(engagement_id=e.id) as ctx:
        assert ctx.require_engagement() == e.id
        assert ctx.has_engagement()


async def test_context_exposes_credential_service(container):
    e = await container.engagement.create(
        name="credctx",
        display_name="credctx",
        engagement_type=ent.EngagementType.CTF,
        client="c",
    )
    async with container.open_context(engagement_id=e.id) as ctx:
        credential = await ctx.credential.seal(
            engagement_id=e.id,
            kind=ent.CredentialKind.PASSWORD_PLAINTEXT,
            identity="alice",
            plaintext="secret",
            obtained_from_tool="test",
        )
        assert ctx.credential is container.credential
        assert await ctx.credential.unseal(credential.reference()) == "secret"


async def test_ensure_scope_noop_without_engagement(container):
>>>>>>> REPLACE

### Step 4 - Close trackers and release docs

REPLACE rfcs/RFC-003-credential-store.md
<<<<<<< SEARCH
status: open
owner: unassigned
=======
status: done
owner: agent
>>>>>>> REPLACE

REPLACE rfcs/RFC-003-credential-store.md
<<<<<<< SEARCH
  max_lines_added: 450
=======
  max_lines_added: 400
>>>>>>> REPLACE

REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-003 | Credential Store (split umbrella) | blocked ⚠ | RFC-002  | agent |
| RFC-003a | Credential service seal/unseal   | done   | RFC-002     | agent |
=======
| RFC-003 | Credential Store (split umbrella) | done   | RFC-002  | agent |
| RFC-003a | Credential service seal/unseal   | done   | RFC-002     | agent |
| RFC-003b | Credential service integration   | done   | RFC-003a    | agent |
>>>>>>> REPLACE

REPLACE CHANGELOG.md
<<<<<<< SEARCH
### Added
- `RFC-003a` - Added encrypted credential seal/unseal domain service,
  Fernet key resolution, direct `cryptography` dependency, and unit tests.
=======
### Added
- `RFC-003b` - Wired `CredentialService` into `ServiceContainer` and
  `RequestContext`, closed the split RFC-003 umbrella, and updated release
  security docs for encrypted-at-rest credentials.
- `RFC-003a` - Added encrypted credential seal/unseal domain service,
  Fernet key resolution, direct `cryptography` dependency, and unit tests.
>>>>>>> REPLACE

REPLACE SECURITY.md
<<<<<<< SEARCH
- **D-9** (AUDIT.md): Credentials stored unencrypted until RFC-003 lands
=======
- **D-9 follow-up** (AUDIT.md): Credentials are encrypted at rest by
  `CredentialService`; some tool wrappers still accept plaintext input args
  until follow-up RFCs switch them to `cred://` references.
>>>>>>> REPLACE

REPLACE README.md
<<<<<<< SEARCH
- `credential_encryption_required = false` — plaintext creds OK inside the
  vault.
=======
- `credential_encryption_required = false` — Team may accept plaintext input
  into the credential vault, while stored credentials are still sealed at rest.
>>>>>>> REPLACE

### Step 5 - Verify

RUN .venv\Scripts\python.exe scripts\validate_rfc.py rfcs\RFC-003b-credential-integration.md

RUN .venv\Scripts\python.exe -m pytest tests/unit/core/test_context.py tests/unit/domain/test_credential_service.py -v

RUN .venv\Scripts\python.exe scripts\full_verify.py

RUN .venv\Scripts\ruff.exe check src/ tests/

RUN .venv\Scripts\mypy.exe --strict src/kestrel_mcp/core src/kestrel_mcp/domain src/kestrel_mcp/webui

RUN .venv\Scripts\python.exe scripts\validate_rfc.py rfcs\RFC-*.md --summary

## Tests

- Context exposes the container credential service.
- Seal/unseal works through `ctx.credential`.
- Existing credential service tests remain green.
- Validator sweep no longer has the RFC-003 known failure.

## Post-checks

- `git diff --stat` stays within the 10-file budget.
- The old RFC-003 file is status `done` only as a split umbrella.
- No release tag is created.

## Rollback plan

Run `git checkout -- .` before commit.

## Updates to other docs

- Mark RFC-003 umbrella and RFC-003b done in INDEX.
- Add CHANGELOG entry.
- Update README and SECURITY release notes around credential handling.

## Notes for executor

- The `CredentialService` key file is generated lazily during container
  construction today; tests must set `KESTREL_DATA_DIR` to a tmp directory.
- Do not retrofit any tool handler to credential refs in this RFC.
- Do not start T00b until this split pair lands cleanly.

## Changelog

- **2026-04-21** - Executed: exported CredentialService, wired container and
  context accessors, added integration test, closed RFC-003 umbrella, and
  updated release security docs.
- **2026-04-21** - Expanded from the blocked RFC-003 into split part B.
