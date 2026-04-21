"""CredentialService - encrypted secret storage bound to engagements."""

from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from ...logging import audit_event
from .. import entities as ent
from ..errors import CredentialSealError, DomainError
from ..storage import CredentialRow
from ._base import _ServiceBase

_KEY_ENV = "KESTREL_MCP_CREDENTIAL_KEY"
_KDF = "fernet-v1"


class CredentialService(_ServiceBase):
    """Seal and unseal credential plaintext using Fernet."""

    def __init__(
        self,
        *args: object,
        key: str | bytes | None = None,
        key_path: Path | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._fernet = Fernet(_resolve_key(key=key, key_path=key_path))

    async def seal(
        self,
        *,
        engagement_id: UUID,
        kind: ent.CredentialKind,
        identity: str,
        plaintext: str,
        obtained_from_tool: str,
        target_id: UUID | None = None,
        secret_metadata: dict[str, str] | None = None,
        tags: list[str] | None = None,
        notes: str = "",
    ) -> ent.Credential:
        """Encrypt ``plaintext`` and persist a credential entity."""

        if not plaintext:
            raise CredentialSealError("Refusing to seal empty plaintext.")
        try:
            ciphertext = self._fernet.encrypt(plaintext.encode("utf-8"))
        except Exception as exc:  # pragma: no cover - Fernet errors are defensive
            raise CredentialSealError("Credential encryption failed.") from exc

        credential = ent.Credential(
            engagement_id=engagement_id,
            target_id=target_id,
            kind=kind,
            identity=identity,
            obtained_from_tool=obtained_from_tool,
            secret_ciphertext=ciphertext,
            secret_kdf=_KDF,
            secret_metadata=dict(secret_metadata or {}),
            tags=list(tags or []),
            notes=notes,
        )
        async with self._session() as session:
            session.add(_to_row(credential))
            audit_event(
                self.log,
                "credential.seal",
                credential_id=str(credential.id),
                engagement_id=str(engagement_id),
                kind=kind.value,
                identity=identity,
                tool=obtained_from_tool,
            )
        return credential

    async def unseal(self, reference: str) -> str:
        """Resolve ``cred://<engagement>/<id>`` and return plaintext."""

        engagement_id, credential_id = _parse_reference(reference)
        async with self._session() as session:
            row = await session.get(CredentialRow, credential_id)
        if row is None or row.engagement_id != engagement_id:
            raise DomainError(f"Credential not found: {reference!r}")
        if row.revoked:
            raise DomainError(f"Credential revoked: {reference!r}")
        try:
            plaintext = self._fernet.decrypt(row.secret_ciphertext).decode("utf-8")
        except InvalidToken as exc:
            raise CredentialSealError("Credential decryption failed.") from exc
        audit_event(
            self.log,
            "credential.unseal",
            credential_id=str(row.id),
            engagement_id=str(row.engagement_id),
        )
        return plaintext

    async def get(self, credential_id: UUID) -> ent.Credential | None:
        async with self._session() as session:
            row = await session.get(CredentialRow, credential_id)
        return _to_entity(row) if row is not None else None

    async def list_for_engagement(
        self,
        engagement_id: UUID,
        *,
        kind: ent.CredentialKind | None = None,
        include_revoked: bool = False,
    ) -> list[ent.Credential]:
        async with self._session() as session:
            stmt = select(CredentialRow).where(CredentialRow.engagement_id == engagement_id)
            if kind is not None:
                stmt = stmt.where(CredentialRow.kind == kind)
            if not include_revoked:
                stmt = stmt.where(CredentialRow.revoked.is_(False))
            rows = (await session.execute(stmt)).scalars().all()
        return [_to_entity(row) for row in rows]

    async def revoke(self, credential_id: UUID, *, reason: str = "") -> ent.Credential:
        async with self._session() as session:
            row = await session.get(CredentialRow, credential_id)
            if row is None:
                raise DomainError(f"Credential {credential_id} not found.")
            row.revoked = True
            if reason:
                row.notes = (row.notes + "\n" + reason).strip()
            audit_event(
                self.log,
                "credential.revoke",
                credential_id=str(credential_id),
                reason=reason,
            )
        credential = await self.get(credential_id)
        if credential is None:  # pragma: no cover - row existed above
            raise DomainError(f"Credential {credential_id} not found.")
        return credential


def _resolve_key(*, key: str | bytes | None, key_path: Path | None) -> bytes:
    if key is not None:
        return key.encode("utf-8") if isinstance(key, str) else key

    env_key = os.environ.get(_KEY_ENV)
    if env_key:
        return env_key.encode("utf-8")

    path = key_path or _default_key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.read_bytes().strip()

    generated = Fernet.generate_key()
    path.write_bytes(generated)
    with suppress(OSError):
        path.chmod(0o600)
    return generated


def _default_key_path() -> Path:
    root = Path(os.environ.get("KESTREL_DATA_DIR", "~/.kestrel")).expanduser()
    return root / "credential-master.key"


def _parse_reference(reference: str) -> tuple[UUID, UUID]:
    if not reference.startswith("cred://"):
        raise DomainError(f"Invalid credential reference: {reference!r}")
    try:
        engagement_raw, credential_raw = reference.removeprefix("cred://").split("/", 1)
        return UUID(engagement_raw), UUID(credential_raw)
    except ValueError as exc:
        raise DomainError(f"Malformed credential reference: {reference!r}") from exc


def _to_row(credential: ent.Credential) -> CredentialRow:
    return CredentialRow(
        id=credential.id,
        engagement_id=credential.engagement_id,
        kind=credential.kind,
        target_id=credential.target_id,
        obtained_from_tool=credential.obtained_from_tool,
        obtained_at=credential.obtained_at,
        identity=credential.identity,
        secret_ciphertext=credential.secret_ciphertext,
        secret_kdf=credential.secret_kdf,
        secret_metadata_json=dict(credential.secret_metadata),
        validated=credential.validated,
        validated_at=credential.validated_at,
        revoked=credential.revoked,
        tags_json=list(credential.tags),
        notes=credential.notes,
    )


def _to_entity(row: CredentialRow) -> ent.Credential:
    return ent.Credential(
        id=row.id,
        engagement_id=row.engagement_id,
        kind=row.kind,
        target_id=row.target_id,
        obtained_from_tool=row.obtained_from_tool,
        obtained_at=row.obtained_at,
        identity=row.identity,
        secret_ciphertext=row.secret_ciphertext,
        secret_kdf=row.secret_kdf,
        secret_metadata=dict(row.secret_metadata_json or {}),
        validated=row.validated,
        validated_at=row.validated_at,
        revoked=row.revoked,
        tags=list(row.tags_json or []),
        notes=row.notes,
    )
