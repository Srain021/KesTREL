"""Domain entities (Pydantic models).

These are the **canonical** representations of business concepts. Everything
else — MCP tool returns, REST responses, DB rows — are projections of these.

Design rules per DOMAIN_MODEL.md:

    * Every entity has an immutable ``id`` (UUID).
    * Entities are frozen where practical (dataclass ``frozen=True`` equivalent).
    * All state transitions go through a service (see :mod:`.services`).
      Entities themselves expose predicates (``.can_close()``) but not mutators
      that bypass invariants.
    * Audit timestamps are UTC, set by services not callers.
    * No Pydantic v1 syntax; we require Pydantic 2.7+.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class _BaseEntity(BaseModel):
    """Shared configuration for every domain entity."""

    model_config = ConfigDict(
        frozen=False,                 # services rebuild with model_copy; fine.
        str_strip_whitespace=True,
        use_enum_values=False,        # keep Enum members, not raw strings
        validate_assignment=True,
        extra="forbid",
    )


# ---------------------------------------------------------------------------
# Actor — whoever is performing an action
# ---------------------------------------------------------------------------


class ActorKind(str, Enum):
    HUMAN = "human"
    LLM = "llm"
    AUTOMATION = "automation"


class Actor(_BaseEntity):
    id: UUID = Field(default_factory=uuid4)
    kind: ActorKind
    display_name: str

    # For LLM actors
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_client: str | None = None

    # For human actors
    handle: str | None = None
    contact: str | None = None

    created_at: datetime = Field(default_factory=_now_utc)
    last_seen_at: datetime = Field(default_factory=_now_utc)
    deactivated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Engagement — the top-level business container
# ---------------------------------------------------------------------------


class EngagementStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class EngagementType(str, Enum):
    PENTEST = "pentest"
    RED_TEAM = "red_team"
    CTF = "ctf"
    RESEARCH = "research"
    BUG_BOUNTY = "bug_bounty"
    INTERNAL_TRAINING = "internal_training"


_SLUG_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-_")


class Engagement(_BaseEntity):
    id: UUID = Field(default_factory=uuid4)

    name: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)

    status: EngagementStatus = EngagementStatus.PLANNING
    engagement_type: EngagementType

    client: str = Field(..., min_length=1, max_length=128)
    owners: list[UUID] = Field(default_factory=list)

    authorization_doc_ref: str | None = None
    started_at: datetime | None = None
    expires_at: datetime | None = None
    closed_at: datetime | None = None

    dry_run: bool = False
    opsec_mode: bool = False

    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)

    @field_validator("name")
    @classmethod
    def _slug_only(cls, v: str) -> str:
        if any(c.lower() not in _SLUG_CHARS for c in v):
            raise ValueError(
                "Engagement name must be a slug: a-z 0-9 - _ only. "
                "Use display_name for human-readable titles."
            )
        return v.lower()

    # --- Predicates (no state mutation; helpers for services) ---

    def is_mutable(self) -> bool:
        return self.status in (EngagementStatus.PLANNING, EngagementStatus.ACTIVE, EngagementStatus.PAUSED)

    def is_expired(self, *, at: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        return (at or _now_utc()) >= self.expires_at

    def allows_dangerous_tools(self) -> bool:
        if self.status != EngagementStatus.ACTIVE:
            return False
        if self.is_expired():
            return False
        return True


# ---------------------------------------------------------------------------
# Scope — authorized targets for an engagement
# ---------------------------------------------------------------------------


class ScopeEntryKind(str, Enum):
    HOSTNAME_EXACT = "hostname_exact"
    HOSTNAME_WILDCARD = "hostname_wildcard"
    HOSTNAME_APEX_WILDCARD = "hostname_apex_wildcard"  # .example.com style
    CIDR_V4 = "cidr_v4"
    CIDR_V6 = "cidr_v6"
    IP_V4 = "ip_v4"
    IP_V6 = "ip_v6"
    URL_PATH = "url_path"


class ScopeEntry(_BaseEntity):
    id: UUID = Field(default_factory=uuid4)
    pattern: str = Field(..., min_length=1, max_length=256)
    kind: ScopeEntryKind
    included: bool = True
    note: str | None = Field(None, max_length=512)
    added_by: UUID | None = None
    added_at: datetime = Field(default_factory=_now_utc)


class Scope(_BaseEntity):
    id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    entries: list[ScopeEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)


# ---------------------------------------------------------------------------
# Target — a concrete asset
# ---------------------------------------------------------------------------


class TargetKind(str, Enum):
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    HOSTNAME = "hostname"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    URL = "url"
    EMAIL = "email"
    PERSON = "person"
    ORGANIZATION = "organization"
    APPLICATION = "application"
    NETWORK = "network"


class Target(_BaseEntity):
    id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    kind: TargetKind
    value: str = Field(..., min_length=1, max_length=512)
    parent_id: UUID | None = None

    discovered_by_tool: str | None = None
    discovered_at: datetime = Field(default_factory=_now_utc)

    open_ports: list[int] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    hostnames: list[str] = Field(default_factory=list)
    organization: str | None = None
    country: str | None = None

    last_scanned_at: datetime | None = None
    notes: str = ""
    tags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Credential — captured secret, always encrypted at rest
# ---------------------------------------------------------------------------


class CredentialKind(str, Enum):
    PASSWORD_PLAINTEXT = "password"
    NTLM_HASH = "ntlm_hash"
    NETNTLMV2_HASH = "netntlmv2_hash"
    KERBEROS_TGT = "krb_tgt"
    KERBEROS_TGS = "krb_tgs"
    KERBEROS_AS_REP = "krb_as_rep"
    JWT = "jwt"
    SESSION_COOKIE = "session_cookie"
    API_KEY = "api_key"
    SSH_PRIVATE_KEY = "ssh_private_key"
    CLOUD_ACCESS_KEY = "cloud_access_key"
    OTHER = "other"


class Credential(_BaseEntity):
    """A captured authenticator. ``secret_ciphertext`` is opaque to this layer —
    the CredentialService handles seal/unseal via a pluggable KMS backend.
    """

    id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    kind: CredentialKind

    target_id: UUID | None = None
    obtained_from_tool: str
    obtained_at: datetime = Field(default_factory=_now_utc)

    identity: str = Field(..., min_length=1, max_length=256)
    secret_ciphertext: bytes
    secret_kdf: str = Field(..., description="Algorithm name: 'age-x25519-v1', 'kc-macos', 'vault-v1', ...")
    secret_metadata: dict[str, str] = Field(default_factory=dict)

    validated: bool = False
    validated_at: datetime | None = None
    revoked: bool = False

    tags: list[str] = Field(default_factory=list)
    notes: str = ""

    def reference(self) -> str:
        """Stable cross-layer reference form: ``cred://<engagement>/<id>``."""

        return f"cred://{self.engagement_id}/{self.id}"


# ---------------------------------------------------------------------------
# Finding — a vulnerability or noteworthy observation
# ---------------------------------------------------------------------------


class FindingSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Confidence(str, Enum):
    SUSPECTED = "suspected"
    LIKELY = "likely"
    CONFIRMED = "confirmed"


class FindingStatus(str, Enum):
    NEW = "new"
    TRIAGED = "triaged"
    CONFIRMED = "confirmed"
    FIXED = "fixed"
    CLOSED_WONTFIX = "closed_wontfix"
    FALSE_POSITIVE = "false_positive"


class FindingCategory(str, Enum):
    INJECTION = "injection"
    BROKEN_AUTH = "broken_auth"
    SENSITIVE_DATA = "sensitive_data"
    MISCONFIGURATION = "misconfiguration"
    VULNERABLE_COMPONENT = "vulnerable_component"
    ACCESS_CONTROL = "access_control"
    CRYPTOGRAPHY = "cryptography"
    LOGIC_FLAW = "logic_flaw"
    INFORMATION_DISCLOSURE = "information_disclosure"
    SOCIAL_ENGINEERING = "social_engineering"
    SUPPLY_CHAIN = "supply_chain"
    OTHER = "other"


class EvidenceKind(str, Enum):
    REQUEST_RESPONSE = "request_response"
    SCREENSHOT = "screenshot"
    LOG = "log"
    TOOL_OUTPUT = "tool_output"
    FILE = "file"


class FindingEvidence(_BaseEntity):
    kind: EvidenceKind
    content_ref: UUID  # points to an Artifact
    sanitized: bool = False


class Finding(_BaseEntity):
    id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    target_id: UUID

    title: str = Field(..., min_length=1, max_length=256)
    severity: FindingSeverity
    confidence: Confidence = Confidence.SUSPECTED
    category: FindingCategory = FindingCategory.OTHER

    cwe: list[str] = Field(default_factory=list)
    cve: list[str] = Field(default_factory=list)
    owasp_top10: list[str] = Field(default_factory=list)
    mitre_attack: list[str] = Field(default_factory=list)
    cvss_vector: str | None = None
    cvss_score: float | None = Field(None, ge=0.0, le=10.0)

    description: str = ""
    impact: str = ""
    remediation: str = ""
    references: list[str] = Field(default_factory=list)

    evidence: list[FindingEvidence] = Field(default_factory=list)

    discovered_by_tool: str
    discovered_at: datetime = Field(default_factory=_now_utc)
    verified: bool = False
    verified_by: UUID | None = None
    verified_at: datetime | None = None

    status: FindingStatus = FindingStatus.NEW
    triage_notes: str = ""
    fixed_at: datetime | None = None

    group_id: UUID | None = None


# ---------------------------------------------------------------------------
# Artifact — any blob produced by a tool
# ---------------------------------------------------------------------------


class ArtifactKind(str, Enum):
    PAYLOAD = "payload"
    CRED_DUMP = "cred_dump"
    PACKET_CAPTURE = "pcap"
    SCREENSHOT = "screenshot"
    LOG = "log"
    REPORT = "report"
    BLOODHOUND_DATA = "bloodhound_data"
    HTTP_REQUEST_RESPONSE = "http_rr"
    SHELLCODE = "shellcode"
    MALWARE_SAMPLE = "malware_sample"
    OTHER = "other"


class Artifact(_BaseEntity):
    id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    kind: ArtifactKind

    storage_path: Path
    size_bytes: int = Field(..., ge=0)
    sha256: str = Field(..., min_length=64, max_length=64)
    encrypted: bool = False

    produced_by_tool: str
    produced_at: datetime = Field(default_factory=_now_utc)
    source_target_id: UUID | None = None

    mime_type: str = "application/octet-stream"
    original_filename: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# Session — active C2 / shell / tunnel
# ---------------------------------------------------------------------------


class SessionKind(str, Enum):
    SLIVER = "sliver"
    HAVOC = "havoc"
    MSF = "msf"
    COBALT_STRIKE = "cobalt_strike"
    SSH = "ssh"
    RDP = "rdp"
    LIGOLO_TUNNEL = "ligolo_tunnel"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    STALE = "stale"
    LOST = "lost"
    CLOSED = "closed"


class Session(_BaseEntity):
    id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    target_id: UUID | None = None

    kind: SessionKind
    external_id: str = Field(..., min_length=1, max_length=128)
    protocol: str = "https"
    callback_addr: str

    status: SessionStatus = SessionStatus.ACTIVE
    first_seen_at: datetime = Field(default_factory=_now_utc)
    last_check_in_at: datetime = Field(default_factory=_now_utc)
    closed_at: datetime | None = None

    remote_hostname: str | None = None
    remote_user: str | None = None
    remote_os: str | None = None
    remote_pid: int | None = None
    remote_integrity: str | None = None

    credentials_used: list[UUID] = Field(default_factory=list)
    findings_produced: list[UUID] = Field(default_factory=list)
    artifacts_produced: list[UUID] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# ToolInvocation — audit-layer record
# ---------------------------------------------------------------------------


class ToolInvocation(_BaseEntity):
    id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    actor_id: UUID

    tool_name: str
    arguments_sanitized: dict[str, Any] = Field(default_factory=dict)
    arguments_hash: str = Field(..., min_length=64, max_length=64)

    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(..., ge=0)
    exit_code: int | None = None
    truncated: bool = False
    timed_out: bool = False

    findings_created: list[UUID] = Field(default_factory=list)
    credentials_created: list[UUID] = Field(default_factory=list)
    artifacts_created: list[UUID] = Field(default_factory=list)
    targets_created: list[UUID] = Field(default_factory=list)

    error_code: str | None = None
    error_message: str | None = None

    # Hash chain: this_hash = sha256(prev_hash || serialize(self_minus_this_hash))
    prev_hash: str = Field(..., min_length=64, max_length=64)
    this_hash: str = Field(..., min_length=64, max_length=64)


__all__ = [
    "Actor",
    "ActorKind",
    "Artifact",
    "ArtifactKind",
    "Confidence",
    "Credential",
    "CredentialKind",
    "Engagement",
    "EngagementStatus",
    "EngagementType",
    "EvidenceKind",
    "Finding",
    "FindingCategory",
    "FindingEvidence",
    "FindingSeverity",
    "FindingStatus",
    "Scope",
    "ScopeEntry",
    "ScopeEntryKind",
    "Session",
    "SessionKind",
    "SessionStatus",
    "Target",
    "TargetKind",
    "ToolInvocation",
]


# ---------------------------------------------------------------------------
# Re-export the Literal alias used elsewhere (kept here so tests import from
# a single domain.entities)
# ---------------------------------------------------------------------------

EngagementStatusLiteral = Literal[
    "planning", "active", "paused", "closed",
]
"""Convenience Literal for APIs that take a status string."""
