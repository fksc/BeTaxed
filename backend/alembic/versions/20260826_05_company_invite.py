"""Sales-led company invites and seat limit (DEV-852).

Revision ID: 20260826_05_company_invite
Revises: 20260826_04_ss_raw_leave
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260826_05_company_invite"
down_revision: Union[str, None] = "20260826_04_ss_raw_leave"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company",
        sa.Column(
            "max_members",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("3"),
        ),
    )
    op.create_check_constraint(
        "ck_company_max_members",
        "company",
        "max_members >= 1",
    )
    op.create_table(
        "company_invite",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("token_hash", postgresql.BYTEA(), nullable=False),
        sa.Column("invited_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column(
            "needs_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["invited_by_id"], ["user_base.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_base.id"]),
        sa.ForeignKeyConstraint(["membership_id"], ["company_membership.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_company_invite_token_hash"),
        sa.CheckConstraint(
            "role IN ('ADMIN', 'HR', 'FINANCE')",
            name="ck_company_invite_role",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'EXPIRED', 'FAILED', 'CANCELLED')",
            name="ck_company_invite_status",
        ),
    )
    op.create_index(
        "idx_company_invite_company", "company_invite", ["company_id"]
    )
    op.create_index(
        "idx_company_invite_email", "company_invite", ["company_id", "email"]
    )


def downgrade() -> None:
    op.drop_index("idx_company_invite_email", table_name="company_invite")
    op.drop_index("idx_company_invite_company", table_name="company_invite")
    op.drop_table("company_invite")
    op.drop_constraint("ck_company_max_members", "company", type_="check")
    op.drop_column("company", "max_members")
