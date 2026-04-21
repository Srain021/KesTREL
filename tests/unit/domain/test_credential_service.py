"""CredentialService round-trip and safety invariants."""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from kestrel_mcp.domain import entities as ent
from kestrel_mcp.domain.errors import CredentialSealError, DomainError
from kestrel_mcp.domain.services.credential_service import CredentialService

pytestmark = pytest.mark.asyncio


async def _engagement_id(sm):
    from kestrel_mcp.domain.services.engagement_service import EngagementService

    engagement = await EngagementService(sm).create(
        name="cred",
        display_name="cred",
        engagement_type=ent.EngagementType.CTF,
        client="client",
    )
    return engagement.id


async def test_seal_unseal_roundtrip_encrypts_at_rest(sm) -> None:
    engagement_id = await _engagement_id(sm)
    svc = CredentialService(sm, key=Fernet.generate_key())

    credential = await svc.seal(
        engagement_id=engagement_id,
        kind=ent.CredentialKind.PASSWORD_PLAINTEXT,
        identity="alice",
        plaintext="s3cret-123!",
        obtained_from_tool="manual",
        tags=["initial"],
    )

    assert credential.secret_kdf == "fernet-v1"
    assert b"s3cret" not in credential.secret_ciphertext
    assert credential.reference().startswith(f"cred://{engagement_id}/")
    assert await svc.unseal(credential.reference()) == "s3cret-123!"


async def test_empty_plaintext_rejected(sm) -> None:
    svc = CredentialService(sm, key=Fernet.generate_key())
    with pytest.raises(CredentialSealError):
        await svc.seal(
            engagement_id=await _engagement_id(sm),
            kind=ent.CredentialKind.API_KEY,
            identity="api",
            plaintext="",
            obtained_from_tool="manual",
        )


async def test_invalid_reference_rejected(sm) -> None:
    svc = CredentialService(sm, key=Fernet.generate_key())
    with pytest.raises(DomainError):
        await svc.unseal("not-a-ref")
    with pytest.raises(DomainError):
        await svc.unseal("cred://malformed")


async def test_revoked_credential_cannot_unseal(sm) -> None:
    engagement_id = await _engagement_id(sm)
    svc = CredentialService(sm, key=Fernet.generate_key())
    credential = await svc.seal(
        engagement_id=engagement_id,
        kind=ent.CredentialKind.JWT,
        identity="token",
        plaintext="eyJhbGciOi",
        obtained_from_tool="manual",
    )

    revoked = await svc.revoke(credential.id, reason="rotated")

    assert revoked.revoked is True
    assert "rotated" in revoked.notes
    with pytest.raises(DomainError):
        await svc.unseal(credential.reference())


async def test_list_filters_kind_and_hides_revoked(sm) -> None:
    engagement_id = await _engagement_id(sm)
    svc = CredentialService(sm, key=Fernet.generate_key())
    password = await svc.seal(
        engagement_id=engagement_id,
        kind=ent.CredentialKind.PASSWORD_PLAINTEXT,
        identity="alice",
        plaintext="pw",
        obtained_from_tool="manual",
    )
    await svc.seal(
        engagement_id=engagement_id,
        kind=ent.CredentialKind.NTLM_HASH,
        identity="alice",
        plaintext="hash",
        obtained_from_tool="manual",
    )
    await svc.revoke(password.id)

    passwords = await svc.list_for_engagement(
        engagement_id,
        kind=ent.CredentialKind.PASSWORD_PLAINTEXT,
    )
    all_credentials = await svc.list_for_engagement(engagement_id, include_revoked=True)

    assert passwords == []
    assert len(all_credentials) == 2


async def test_default_key_file_created(sm, tmp_path: Path) -> None:
    key_path = tmp_path / "credential-master.key"
    svc = CredentialService(sm, key_path=key_path)

    await svc.seal(
        engagement_id=await _engagement_id(sm),
        kind=ent.CredentialKind.PASSWORD_PLAINTEXT,
        identity="alice",
        plaintext="secret",
        obtained_from_tool="manual",
    )

    assert key_path.exists()
    assert key_path.read_bytes().strip()
    assert isinstance(svc, CredentialService)


async def test_plaintext_mode_stores_plaintext_without_key_file(sm, tmp_path: Path) -> None:
    key_path = tmp_path / "credential-master.key"
    svc = CredentialService(sm, key_path=key_path, encryption_required=False)
    credential = await svc.seal(
        engagement_id=await _engagement_id(sm),
        kind=ent.CredentialKind.PASSWORD_PLAINTEXT,
        identity="team",
        plaintext="shared-secret",
        obtained_from_tool="manual",
    )

    assert credential.secret_kdf == "plaintext-v1"
    assert credential.secret_ciphertext == b"shared-secret"
    assert await svc.unseal(credential.reference()) == "shared-secret"
    assert not key_path.exists()


async def test_encrypted_mode_rejects_plaintext_rows(sm) -> None:
    engagement_id = await _engagement_id(sm)
    team_svc = CredentialService(sm, encryption_required=False)
    credential = await team_svc.seal(
        engagement_id=engagement_id,
        kind=ent.CredentialKind.PASSWORD_PLAINTEXT,
        identity="team",
        plaintext="shared-secret",
        obtained_from_tool="manual",
    )
    pro_svc = CredentialService(sm, key=Fernet.generate_key())

    with pytest.raises(CredentialSealError):
        await pro_svc.unseal(credential.reference())


async def test_container_threads_credential_encryption_gate(tmp_path: Path, monkeypatch) -> None:
    from kestrel_mcp.core import ServiceContainer

    monkeypatch.setenv("KESTREL_DATA_DIR", str(tmp_path))
    container = ServiceContainer.in_memory(credential_encryption_required=False)
    await container.initialise()
    try:
        credential = await container.credential.seal(
            engagement_id=await _engagement_id(container.sessionmaker),
            kind=ent.CredentialKind.PASSWORD_PLAINTEXT,
            identity="team",
            plaintext="shared-secret",
            obtained_from_tool="manual",
        )
        assert credential.secret_kdf == "plaintext-v1"
    finally:
        await container.dispose()
