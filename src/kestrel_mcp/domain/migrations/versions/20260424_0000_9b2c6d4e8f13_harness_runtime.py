"""harness runtime state

Revision ID: 9b2c6d4e8f13
Revises: 1c61df536704
Create Date: 2026-04-24 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import kestrel_mcp.domain.storage  # noqa: F401 - referenced for UUIDString

# revision identifiers, used by Alembic.
revision: str = "9b2c6d4e8f13"
down_revision: str | Sequence[str] | None = "1c61df536704"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "harness_sessions",
        sa.Column("id", kestrel_mcp.domain.storage.UUIDString(length=36), nullable=False),
        sa.Column(
            "engagement_id",
            kestrel_mcp.domain.storage.UUIDString(length=36),
            nullable=True,
        ),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("target", sa.String(length=512), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "BLOCKED", "DONE", "CANCELLED", name="harness_session_status"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column("model_tier", sa.String(length=32), nullable=False),
        sa.Column("state_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_harness_sessions_engagement_id"),
        "harness_sessions",
        ["engagement_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_harness_sessions_status"),
        "harness_sessions",
        ["status"],
        unique=False,
    )

    op.create_table(
        "harness_steps",
        sa.Column("id", kestrel_mcp.domain.storage.UUIDString(length=36), nullable=False),
        sa.Column(
            "session_id",
            kestrel_mcp.domain.storage.UUIDString(length=36),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("arguments_json", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "RUNNING",
                "DONE",
                "FAILED",
                "SKIPPED",
                "NEEDS_CONFIRMATION",
                name="harness_step_status",
            ),
            nullable=False,
        ),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("recommended_model_tier", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column(
            "tool_invocation_id",
            kestrel_mcp.domain.storage.UUIDString(length=36),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["harness_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["tool_invocation_id"],
            ["tool_invocations.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_harness_steps_session_id"), "harness_steps", ["session_id"])
    op.create_index(op.f("ix_harness_steps_status"), "harness_steps", ["status"])
    op.create_index(op.f("ix_harness_steps_tool_name"), "harness_steps", ["tool_name"])


def downgrade() -> None:
    op.drop_index(op.f("ix_harness_steps_tool_name"), table_name="harness_steps")
    op.drop_index(op.f("ix_harness_steps_status"), table_name="harness_steps")
    op.drop_index(op.f("ix_harness_steps_session_id"), table_name="harness_steps")
    op.drop_table("harness_steps")
    op.drop_index(op.f("ix_harness_sessions_status"), table_name="harness_sessions")
    op.drop_index(op.f("ix_harness_sessions_engagement_id"), table_name="harness_sessions")
    op.drop_table("harness_sessions")
