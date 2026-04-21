"""Tests for domain entities — constructor validation and predicate helpers.

No DB involved. Pure Pydantic.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from kestrel_mcp.domain import entities as ent


class TestEngagement:
    def _build(self, **over):
        kwargs = {
            "name": "demo",
            "display_name": "Demo Engagement",
            "engagement_type": ent.EngagementType.CTF,
            "client": "Demo Co",
        }
        kwargs.update(over)
        return ent.Engagement(**kwargs)

    def test_defaults(self):
        e = self._build()
        assert e.status == ent.EngagementStatus.PLANNING
        assert e.dry_run is False
        assert e.opsec_mode is False
        assert e.owners == []

    @pytest.mark.parametrize(
        "bad_name",
        ["Upper Case", "has space", "slash/in/name", "dot.in.name", "unicode—char"],
    )
    def test_rejects_non_slug_name(self, bad_name: str):
        with pytest.raises(ValidationError):
            self._build(name=bad_name)

    def test_lowercases_slug(self):
        e = self._build(name="MY-ENGAGEMENT_01")
        assert e.name == "my-engagement_01"

    def test_is_mutable_states(self):
        assert self._build(status=ent.EngagementStatus.PLANNING).is_mutable()
        assert self._build(status=ent.EngagementStatus.ACTIVE).is_mutable()
        assert self._build(status=ent.EngagementStatus.PAUSED).is_mutable()
        assert not self._build(status=ent.EngagementStatus.CLOSED).is_mutable()

    def test_allows_dangerous_only_when_active_and_unexpired(self):
        now = datetime.now(timezone.utc)

        active = self._build(status=ent.EngagementStatus.ACTIVE)
        assert active.allows_dangerous_tools()

        planning = self._build(status=ent.EngagementStatus.PLANNING)
        assert not planning.allows_dangerous_tools()

        expired = self._build(
            status=ent.EngagementStatus.ACTIVE,
            expires_at=now - timedelta(hours=1),
        )
        assert not expired.allows_dangerous_tools()
        assert expired.is_expired()

        future = self._build(
            status=ent.EngagementStatus.ACTIVE,
            expires_at=now + timedelta(hours=1),
        )
        assert future.allows_dangerous_tools()


class TestFinding:
    def test_cvss_range_validation(self):
        with pytest.raises(ValidationError):
            ent.Finding(
                engagement_id=uuid4(),
                target_id=uuid4(),
                title="x",
                severity=ent.FindingSeverity.HIGH,
                discovered_by_tool="x",
                cvss_score=11.0,
            )

    def test_default_status_new(self):
        f = ent.Finding(
            engagement_id=uuid4(),
            target_id=uuid4(),
            title="x",
            severity=ent.FindingSeverity.MEDIUM,
            discovered_by_tool="nuclei",
        )
        assert f.status == ent.FindingStatus.NEW
        assert f.confidence == ent.Confidence.SUSPECTED


class TestCredential:
    def test_reference_format(self):
        c = ent.Credential(
            engagement_id=uuid4(),
            kind=ent.CredentialKind.NTLM_HASH,
            obtained_from_tool="secretsdump",
            identity="admin",
            secret_ciphertext=b"enc",
            secret_kdf="age-x25519-v1",
        )
        ref = c.reference()
        assert ref.startswith("cred://")
        assert str(c.engagement_id) in ref
        assert str(c.id) in ref
