"""Employment documents, domain events, notifications (DEV-836, KB/04, KB/08).

Revision ID: 20260825_01_contracts_notifications
Revises: 20260820_02_employment_spine
Create Date: 2026-08-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260825_01_contracts_notifications"
down_revision: Union[str, None] = "20260820_02_employment_spine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employment_document",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_kind", sa.String(24), nullable=True),
        sa.Column("signed_on", sa.Date(), nullable=True),
        sa.Column("term_end_on", sa.Date(), nullable=True),
        sa.Column(
            "matches_ss",
            sa.String(16),
            server_default=sa.text("'UNKNOWN'"),
            nullable=False,
        ),
        sa.Column(
            "review_status",
            sa.String(16),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column("review_leftover", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("review_error", sa.Text(), nullable=True),
        sa.Column("ops_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
        sa.ForeignKeyConstraint(["employment_id"], ["employment.id"]),
        sa.ForeignKeyConstraint(["file_id"], ["stored_file.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "doc_kind IS NULL OR doc_kind IN ('SEM_TERMO', 'TERMO', 'CONVERSION')",
            name="ck_employment_document_doc_kind",
        ),
        sa.CheckConstraint(
            "matches_ss IN ('UNKNOWN', 'MATCH', 'MISMATCH')",
            name="ck_employment_document_matches_ss",
        ),
        sa.CheckConstraint(
            "review_status IN ('PENDING', 'REVIEWED', 'FAILED')",
            name="ck_employment_document_review_status",
        ),
    )
    op.create_index(
        "idx_employment_document_employee",
        "employment_document",
        ["employee_id"],
    )

    op.create_table(
        "domain_event",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("source_entity_type", sa.String(32), nullable=False),
        sa.Column("source_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["user_base.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_domain_event_company", "domain_event", ["company_id"])
    op.create_index("idx_domain_event_type", "domain_event", ["event_type"])

    op.create_table(
        "notification",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("domain_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "is_read",
            sa.Boolean(),
            server_default=sa.text("FALSE"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "in_app_delivered",
            sa.Boolean(),
            server_default=sa.text("TRUE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["recipient_id"], ["user_base.id"]),
        sa.ForeignKeyConstraint(["domain_event_id"], ["domain_event.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "domain_event_id",
            "recipient_id",
            name="uq_notification_event_recipient",
        ),
    )
    op.create_index(
        "idx_notification_recipient",
        "notification",
        ["recipient_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_notification_recipient", table_name="notification")
    op.drop_table("notification")
    op.drop_index("idx_domain_event_type", table_name="domain_event")
    op.drop_index("idx_domain_event_company", table_name="domain_event")
    op.drop_table("domain_event")
    op.drop_index("idx_employment_document_employee", table_name="employment_document")
    op.drop_table("employment_document")
