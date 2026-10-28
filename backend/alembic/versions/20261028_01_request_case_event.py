"""Append-only log of request-case stage moves.

Revision ID: 20261028_01_request_case_event
Revises: 20261027_02_stage_entered_at
Create Date: 2026-10-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261028_01_request_case_event"
down_revision: Union[str, None] = "20261027_02_stage_entered_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "request_case_event",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("request_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("from_stage_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("to_stage_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["request_case_id"], ["request_case.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["user_base.id"]),
        sa.ForeignKeyConstraint(["from_stage_id"], ["pipeline_stage.id"]),
        sa.ForeignKeyConstraint(["to_stage_id"], ["pipeline_stage.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_request_case_event_case",
        "request_case_event",
        ["request_case_id", "at"],
    )
    op.execute(
        """
        INSERT INTO request_case_event (
            request_case_id, at, actor_id, from_stage_id, to_stage_id, operation, payload
        )
        SELECT id, COALESCE(stage_entered_at, opened_at), opened_by, NULL, stage_id, NULL, '{}'::jsonb
        FROM request_case
        """
    )


def downgrade() -> None:
    op.drop_index("idx_request_case_event_case", table_name="request_case_event")
    op.drop_table("request_case_event")
