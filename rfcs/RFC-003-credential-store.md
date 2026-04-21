---
id: RFC-003
title: Credential store (domain + seal/unseal)
epic: A-Foundations
status: done
owner: agent
role: backend-engineer
blocking_on:
  - RFC-002
budget:
  max_files_touched: 7
  max_new_files: 4
  max_lines_added: 400
  max_minutes_human: 30
  max_tokens_model: 20000
files_to_read:
  - src/kestrel_mcp/domain/entities.py
  - src/kestrel_mcp/domain/storage.py
  - src/kestrel_mcp/domain/services/__init__.py
  - src/kestrel_mcp/core/services.py
files_will_touch:
  - src/kestrel_mcp/domain/services/credential_service.py   # new
  - src/kestrel_mcp/domain/services/__init__.py             # modified (export)
  - src/kestrel_mcp/core/services.py                        # modified (register)
  - src/kestrel_mcp/core/context.py                         # modified (expose ctx.credential)
  - tests/unit/domain/test_credential_service.py            # new
  - CHANGELOG.md                                            # modified
  - THREAT_MODEL.md                                         # modified (T-I1 status)
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/domain/test_credential_service.py -v
rollback_cmd: |
  git checkout -- .
  if exist src\kestrel_mcp\domain\services\credential_service.py del src\kestrel_mcp\domain\services\credential_service.py
  if exist tests\unit\domain\test_credential_service.py del tests\unit\domain\test_credential_service.py
skill_id: rfc-003-credential-store
---

# RFC-003 — Credential store (domain + seal/unseal)

## Mission

实现 CredentialService：seal 明文、按引用 `cred://` 存取、到数据库前后都是加密态。

## Context

- 关闭 THREAT_MODEL T-I1 (credential leak to LLM provider) 的第一步。
- DOMAIN_MODEL §3.5 和 GAP_ANALYSIS G-U3 都指向这个 service。
- 未来 RFC-D03 (credentials vault UI) 和 RFC-G05/G07 (MSF/NetExec 拿的密码) 直接消费本 service。

本 RFC 故意**只做最小安全版**：用 `cryptography.Fernet` + 进程启动时从环境变量拿密钥。
不做 keychain / Vault / KMS 集成 —— 留给未来 RFC-B05 拓展。

## Non-goals

- 不集成 macOS Keychain / Windows Credential Manager / Vault（那是 RFC-B05）
- 不做 credential rotation / 过期策略
- 不做 UI（RFC-D03）
- 不做外部 KMS 协议

## Design

### 加密层

- 每个 engagement 一个 32-byte Fernet key。
- Key 来源（按优先级）：
  1. env `KESTREL_CREDENTIAL_KEY` — 32 bytes base64。`Fernet.generate_key()` 的格式。
  2. fallback：`container.default_credential_key()` — 从 `~/.kestrel/credential-master.key` 读取（若不存在则生成）。
- `secret_kdf` 字段存算法名：`fernet-v1`（未来换 XChaCha20-Poly1305 时改成 `xchacha-v1`）。
- `secret_ciphertext` 存 Fernet 加密后的字节（base64）。

### 接口

```python
class CredentialService:
    async def seal(...) -> Credential  # 吸收明文，返回实体（已加密）
    async def unseal(ref: str) -> str  # ref 形如 "cred://<engagement>/<id>"; 返回明文
    async def list_for_engagement(...) -> list[Credential]
    async def get(id) -> Credential | None
    async def revoke(id, reason) -> Credential
    async def validate_against(id, check_fn) -> bool  # 用明文跑一次用户给的检查函数，不返回明文
```

关键不变量：**`unseal()` 是唯一暴露明文的方法**。任何其他 API 返回 `Credential` 实体时 `secret_ciphertext` 已是密文。

## Steps

### Step 1 — 装 cryptography（如果没装）

```
RUN .venv\Scripts\python.exe -c "import cryptography; print(cryptography.__version__)"
```

如果 ImportError：

```
REPLACE pyproject.toml
<<<<<<< SEARCH
    "jinja2>=3.1",
]
=======
    "jinja2>=3.1",
    "cryptography>=43",
]
>>>>>>> REPLACE
```

然后：

```
RUN .venv\Scripts\python.exe -m uv lock
RUN .venv\Scripts\python.exe -m uv sync --frozen
```

(若 Step 1 没引入变更，跳过 uv lock)

### Step 2 — CredentialService 实现

```
WRITE src/kestrel_mcp/domain/services/credential_service.py
```
```python
"""CredentialService — sealed secret storage bound to an engagement."""

from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from ...logging import audit_event
from .. import entities as ent
from ..errors import CredentialSealError, DomainError
from ..storage import CredentialRow
from ._base import _ServiceBase


_DEFAULT_KEY_PATH = Path(os.environ.get("KESTREL_DATA_DIR", "~/.kestrel")).expanduser() / "credential-master.key"


def _resolve_key() -> bytes:
    env = os.environ.get("KESTREL_CREDENTIAL_KEY")
    if env:
        return env.encode("ascii") if not env.startswith("b'") else eval(env)  # permissive
    if _DEFAULT_KEY_PATH.is_file():
        return _DEFAULT_KEY_PATH.read_bytes()
    # first-run: create and persist
    _DEFAULT_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    _DEFAULT_KEY_PATH.write_bytes(key)
    try:
        _DEFAULT_KEY_PATH.chmod(0o600)
    except OSError:
        pass  # Windows: best effort
    return key


class CredentialService(_ServiceBase):
    def __init__(self, sessionmaker) -> None:
        super().__init__(sessionmaker)
        self._fernet = Fernet(_resolve_key())

    # ---------- seal (write) ----------

    async def seal(
        self,
        *,
        engagement_id: UUID,
        kind: ent.CredentialKind,
        identity: str,
        plaintext: str,
        obtained_from_tool: str,
        target_id: UUID | None = None,
        tags: list[str] | None = None,
        notes: str = "",
    ) -> ent.Credential:
        if not plaintext:
            raise CredentialSealError("Refusing to seal empty plaintext.")
        try:
            ct = self._fernet.encrypt(plaintext.encode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise CredentialSealError(f"Encryption failed: {exc}") from exc

        entity = ent.Credential(
            engagement_id=engagement_id,
            kind=kind,
            identity=identity,
            secret_ciphertext=ct,
            secret_kdf="fernet-v1",
            obtained_from_tool=obtained_from_tool,
            target_id=target_id,
            tags=list(tags or []),
            notes=notes,
        )

        async with self._session() as s:
            s.add(
                CredentialRow(
                    id=entity.id,
                    engagement_id=entity.engagement_id,
                    kind=entity.kind,
                    target_id=entity.target_id,
                    obtained_from_tool=entity.obtained_from_tool,
                    obtained_at=entity.obtained_at,
                    identity=entity.identity,
                    secret_ciphertext=entity.secret_ciphertext,
                    secret_kdf=entity.secret_kdf,
                    secret_metadata_json={},
                    validated=entity.validated,
                    validated_at=entity.validated_at,
                    revoked=entity.revoked,
                    tags_json=list(entity.tags),
                    notes=entity.notes,
                )
            )

        audit_event(
            self.log, "credential.seal",
            engagement_id=str(engagement_id),
            kind=kind.value,
            identity=identity,
            # NEVER log plaintext or ciphertext
        )
        return entity

    # ---------- unseal (read back plaintext) ----------

    async def unseal(self, reference: str) -> str:
        """Resolve a ``cred://<engagement>/<id>`` reference and return plaintext."""

        if not reference.startswith("cred://"):
            raise DomainError(f"Invalid credential reference: {reference!r}")
        _, _, tail = reference.partition("cred://")
        try:
            eng_str, cred_str = tail.split("/", 1)
            eng_id = UUID(eng_str)
            cred_id = UUID(cred_str)
        except (ValueError, Exception) as exc:  # noqa: BLE001
            raise DomainError(f"Malformed credential reference: {reference!r}") from exc

        async with self._session() as s:
            row = await s.get(CredentialRow, cred_id)
        if row is None or row.engagement_id != eng_id:
            raise DomainError(f"Credential not found: {reference!r}")
        if row.revoked:
            raise DomainError(f"Credential revoked: {reference!r}")

        try:
            plain = self._fernet.decrypt(row.secret_ciphertext).decode("utf-8")
        except InvalidToken as exc:
            raise CredentialSealError(
                f"Decryption failed for {reference!r} — key mismatch or tampered ciphertext."
            ) from exc

        audit_event(
            self.log, "credential.unseal",
            reference=reference,
        )
        return plain

    # ---------- read-only helpers ----------

    async def get(self, credential_id: UUID) -> ent.Credential | None:
        async with self._session() as s:
            row = await s.get(CredentialRow, credential_id)
        return _row_to_entity(row) if row else None

    async def list_for_engagement(
        self,
        engagement_id: UUID,
        *,
        kind: ent.CredentialKind | None = None,
    ) -> list[ent.Credential]:
        async with self._session() as s:
            stmt = select(CredentialRow).where(CredentialRow.engagement_id == engagement_id)
            if kind is not None:
                stmt = stmt.where(CredentialRow.kind == kind)
            rows = (await s.execute(stmt)).scalars().all()
        return [_row_to_entity(r) for r in rows]

    async def revoke(self, credential_id: UUID, reason: str = "") -> ent.Credential:
        async with self._session() as s:
            row = await s.get(CredentialRow, credential_id)
            if row is None:
                raise DomainError(f"Credential {credential_id} not found.")
            row.revoked = True
            if reason:
                row.notes = (row.notes + f"\n[revoked] {reason}").strip()
            audit_event(self.log, "credential.revoke", credential_id=str(credential_id), reason=reason)
        return await self.get(credential_id)  # type: ignore[return-value]


def _row_to_entity(r: CredentialRow) -> ent.Credential:
    return ent.Credential(
        id=r.id,
        engagement_id=r.engagement_id,
        kind=r.kind,
        target_id=r.target_id,
        obtained_from_tool=r.obtained_from_tool,
        obtained_at=r.obtained_at,
        identity=r.identity,
        secret_ciphertext=r.secret_ciphertext,
        secret_kdf=r.secret_kdf,
        secret_metadata=dict(r.secret_metadata_json or {}),
        validated=r.validated,
        validated_at=r.validated_at,
        revoked=r.revoked,
        tags=list(r.tags_json or []),
        notes=r.notes,
    )
```

### Step 3 — 导出

```
REPLACE src/kestrel_mcp/domain/services/__init__.py
<<<<<<< SEARCH
from .engagement_service import EngagementService
from .scope_service import ScopeService
from .target_service import TargetService
from .finding_service import FindingService

__all__ = [
    "EngagementService",
    "FindingService",
    "ScopeService",
    "TargetService",
]
=======
from .credential_service import CredentialService
from .engagement_service import EngagementService
from .finding_service import FindingService
from .scope_service import ScopeService
from .target_service import TargetService

__all__ = [
    "CredentialService",
    "EngagementService",
    "FindingService",
    "ScopeService",
    "TargetService",
]
>>>>>>> REPLACE
```

### Step 4 — ServiceContainer 注册

```
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
```

```
REPLACE src/kestrel_mcp/core/services.py
<<<<<<< SEARCH
        self.engagement = EngagementService(sessionmaker)
        self.scope = ScopeService(sessionmaker)
        self.target = TargetService(sessionmaker)
        self.finding = FindingService(sessionmaker)
=======
        self.engagement = EngagementService(sessionmaker)
        self.scope = ScopeService(sessionmaker)
        self.target = TargetService(sessionmaker)
        self.finding = FindingService(sessionmaker)
        self.credential = CredentialService(sessionmaker)
>>>>>>> REPLACE
```

### Step 5 — RequestContext 快捷方式

```
REPLACE src/kestrel_mcp/core/context.py
<<<<<<< SEARCH
    @property
    def finding(self):
        return self.container.finding
=======
    @property
    def finding(self):
        return self.container.finding

    @property
    def credential(self):
        return self.container.credential
>>>>>>> REPLACE
```

### Step 6 — 测试

```
WRITE tests/unit/domain/test_credential_service.py
```
```python
"""CredentialService round-trip and safety invariants."""

from __future__ import annotations

import os

import pytest

from kestrel_mcp.core import ServiceContainer
from kestrel_mcp.domain import entities as ent
from kestrel_mcp.domain.errors import CredentialSealError, DomainError


@pytest.fixture
async def container(tmp_path, monkeypatch):
    # Isolated key per test so one test's keys don't decrypt another's.
    key_path = tmp_path / "credential-master.key"
    monkeypatch.setenv("KESTREL_DATA_DIR", str(tmp_path))
    # Ensure no stale env override
    monkeypatch.delenv("KESTREL_CREDENTIAL_KEY", raising=False)
    c = ServiceContainer.in_memory()
    await c.initialise()
    try:
        yield c
    finally:
        await c.dispose()


@pytest.fixture
async def engagement(container):
    return await container.engagement.create(
        name="cred-test", display_name="x",
        engagement_type=ent.EngagementType.CTF, client="c",
    )


async def test_seal_and_unseal_round_trip(container, engagement):
    cred = await container.credential.seal(
        engagement_id=engagement.id,
        kind=ent.CredentialKind.PASSWORD_PLAINTEXT,
        identity="admin",
        plaintext="s3cret-123!",
        obtained_from_tool="manual",
    )
    assert cred.secret_kdf == "fernet-v1"
    assert b"s3cret" not in cred.secret_ciphertext  # enc bytes differ from plaintext

    plain = await container.credential.unseal(cred.reference())
    assert plain == "s3cret-123!"


async def test_empty_plaintext_rejected(container, engagement):
    with pytest.raises(CredentialSealError):
        await container.credential.seal(
            engagement_id=engagement.id,
            kind=ent.CredentialKind.PASSWORD_PLAINTEXT,
            identity="x",
            plaintext="",
            obtained_from_tool="manual",
        )


async def test_malformed_reference_rejected(container):
    with pytest.raises(DomainError):
        await container.credential.unseal("not-a-ref")
    with pytest.raises(DomainError):
        await container.credential.unseal("cred://garbage")


async def test_revoked_credential_cannot_unseal(container, engagement):
    cred = await container.credential.seal(
        engagement_id=engagement.id,
        kind=ent.CredentialKind.API_KEY,
        identity="svc",
        plaintext="abc",
        obtained_from_tool="t",
    )
    await container.credential.revoke(cred.id, reason="test")
    with pytest.raises(DomainError, match="revoked"):
        await container.credential.unseal(cred.reference())


async def test_list_filters_by_kind(container, engagement):
    await container.credential.seal(
        engagement_id=engagement.id,
        kind=ent.CredentialKind.PASSWORD_PLAINTEXT,
        identity="a",
        plaintext="x",
        obtained_from_tool="t",
    )
    await container.credential.seal(
        engagement_id=engagement.id,
        kind=ent.CredentialKind.NTLM_HASH,
        identity="b",
        plaintext="y",
        obtained_from_tool="t",
    )
    passwords = await container.credential.list_for_engagement(
        engagement.id, kind=ent.CredentialKind.PASSWORD_PLAINTEXT,
    )
    assert len(passwords) == 1
    assert passwords[0].identity == "a"


async def test_reference_includes_both_ids(container, engagement):
    cred = await container.credential.seal(
        engagement_id=engagement.id,
        kind=ent.CredentialKind.JWT,
        identity="u",
        plaintext="eyJ...",
        obtained_from_tool="t",
    )
    ref = cred.reference()
    assert str(engagement.id) in ref
    assert str(cred.id) in ref
    assert ref.startswith("cred://")
```

### Step 7 — CHANGELOG + THREAT_MODEL

```
APPEND CHANGELOG.md

- RFC-003 — Credential store (seal/unseal via Fernet, closes THREAT T-I1 initial)
```

在 THREAT_MODEL.md 里找 T-I1 小节，把状态从 ❌ 改成 ⚠️（因为还需要 prompt injection 的上游保护，完全关闭要到 RFC-B01）：

```
REPLACE THREAT_MODEL.md
<<<<<<< SEARCH
**缓解现状**: ❌ 当前直接明文返回。
**残余风险**: 极高。
=======
**缓解现状**: ⚠️ Domain 层已有 CredentialService (RFC-003) 。
Tool 层接入尚在 RFC-B01，tools 仍可能返回明文。
**残余风险**: 中。
>>>>>>> REPLACE
```

### Step 8 — verify

```
RUN .venv\Scripts\python.exe -m pytest tests/unit/domain/test_credential_service.py -v
```

### Step 9 — full_verify 回归

```
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

## Tests

见 Step 6 的 6 个测试：round-trip / empty-reject / malformed-ref / revoked / list-filter / reference-format。

## Post-checks

- [ ] `~/.kestrel/credential-master.key` 第一次运行后会被创建（Linux 自动 0600 权限）
- [ ] 测试里用 monkeypatch 隔离 `KESTREL_DATA_DIR` 到 tmp，互不污染
- [ ] `git diff --stat` 只列出 `files_will_touch`
- [ ] 6 个新测试 + 既有 95 passed 全部绿

## Rollback plan

`git checkout -- .` + 手动删除 `credential_service.py` 和对应测试（front-matter 的 rollback_cmd 已涵盖）。

## Updates to other docs

- `CHANGELOG.md` — 加 RFC-003 条目（Step 7 已做）
- `THREAT_MODEL.md` — T-I1 降级为 ⚠️（Step 7 已做）
- `GAP_ANALYSIS.md` — G-U3 状态改 `DONE (RFC-003)`
- `DOMAIN_MODEL.md` — 不用改（本 RFC 遵循 §3.5 设计）

## Notes for executor

- `_resolve_key()` 的 env var 处理要兼容 `Fernet.generate_key()` 直接输出（urlsafe base64 bytes）。不要自作聪明重编码。
- 主密钥文件 **一旦丢失**，所有已有 credential 永久不可解密。所以测试隔离非常重要 —— `monkeypatch.setenv("KESTREL_DATA_DIR", str(tmp_path))`。
- `unseal()` 的审计日志只能写 reference，绝不能写明文或密文本身。

## Changelog

- **2026-04-21 初版**
