"""Core spine: user_base, company, company_membership, intake.

Revision ID: 20260818_01_core
Revises:
Create Date: 2026-08-18

Closes DEV-828. Circular FK company.created_from_intake_id is added after
both company and intake exist. Duplicate UNIQUE indexes on user_base are
omitted (UNIQUE already indexes firebase_uid and email).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260818_01_core"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_base",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("firebase_uid", sa.String(128), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("user_type", sa.String(20), nullable=False),
        sa.Column(
            "preferred_language",
            sa.String(10),
            server_default=sa.text("'pt'"),
            nullable=False,
        ),
        sa.Column(
            "timezone",
            sa.String(64),
            server_default=sa.text("'Europe/Lisbon'"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
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
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "user_type IN ('BETAXED_STAFF', 'COMPANY_STAFF')",
            name="ck_user_base_user_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("firebase_uid"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "company",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("trading_name", sa.String(255), nullable=True),
        sa.Column("nif_enc", postgresql.BYTEA(), nullable=True),
        sa.Column("employer_niss_hash", postgresql.BYTEA(), nullable=True),
        sa.Column("employer_niss_enc", postgresql.BYTEA(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.Column(
            "locale",
            sa.String(10),
            server_default=sa.text("'pt'"),
            nullable=False,
        ),
        sa.Column("ss_regularized", sa.Boolean(), nullable=True),
        sa.Column("at_regularized", sa.Boolean(), nullable=True),
        sa.Column("payroll_not_in_arrears", sa.Boolean(), nullable=True),
        sa.Column("stripe_customer_id", sa.String(128), nullable=True),
        sa.Column("invoicing_method", sa.String(32), nullable=True),
        sa.Column("certified_vendor_name", sa.String(128), nullable=True),
        sa.Column("created_from_intake_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'CHURNED')",
            name="ck_company_status",
        ),
        sa.CheckConstraint(
            "invoicing_method IS NULL OR invoicing_method IN "
            "('STRIPE_SEPA', 'CERTIFIED_SOFTWARE')",
            name="ck_company_invoicing_method",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_company_employer_niss_hash",
        "company",
        ["employer_niss_hash"],
        unique=True,
        postgresql_where=sa.text(
            "employer_niss_hash IS NOT NULL AND deleted_at IS NULL"
        ),
    )

    op.create_table(
        "intake",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("session_token_hash", postgresql.BYTEA(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'OPEN'"),
            nullable=False,
        ),
        sa.Column("teaser_now_monthly", sa.Numeric(14, 2), nullable=True),
        sa.Column("teaser_now_window", sa.Numeric(14, 2), nullable=True),
        sa.Column("teaser_potential_monthly", sa.Numeric(14, 2), nullable=True),
        sa.Column("teaser_potential_window", sa.Numeric(14, 2), nullable=True),
        sa.Column(
            "teaser_currency",
            sa.CHAR(3),
            server_default=sa.text("'EUR'"),
            nullable=False,
        ),
        sa.Column("teaser_regime_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "converted_company_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('OPEN', 'CONVERTED', 'DECLINED', 'PURGED')",
            name="ck_intake_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user_base.id"]),
        sa.ForeignKeyConstraint(["converted_company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_intake_user", "intake", ["user_id"])
    op.create_index("idx_intake_status", "intake", ["status"])

    op.create_foreign_key(
        "fk_company_created_from_intake_id",
        "company",
        "intake",
        ["created_from_intake_id"],
        ["id"],
    )

    op.create_table(
        "company_membership",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column(
            "is_active",
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
        sa.CheckConstraint(
            "role IN ('ADMIN', 'HR', 'FINANCE')",
            name="ck_company_membership_role",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user_base.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "company_id", name="uq_company_membership_user_company"),
    )
    op.create_index(
        "idx_membership_company", "company_membership", ["company_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_membership_company", table_name="company_membership")
    op.drop_table("company_membership")
    op.drop_constraint("fk_company_created_from_intake_id", "company", type_="foreignkey")
    op.drop_index("idx_intake_status", table_name="intake")
    op.drop_index("idx_intake_user", table_name="intake")
    op.drop_table("intake")
    op.drop_index("idx_company_employer_niss_hash", table_name="company")
    op.drop_table("company")
    op.drop_table("user_base")
