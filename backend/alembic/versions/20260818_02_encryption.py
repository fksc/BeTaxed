"""Tenant crypto keys, employee PII columns, stored_file (DEV-830).

Revision ID: 20260818_02_encryption
Revises: 20260818_01_core
Create Date: 2026-08-18

Closes DEV-830.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260818_02_encryption"
down_revision: Union[str, None] = "20260818_01_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_crypto_key",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intake_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("wrapped_dek", postgresql.BYTEA(), nullable=False),
        sa.Column(
            "key_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(company_id IS NOT NULL AND intake_id IS NULL) OR "
            "(company_id IS NULL AND intake_id IS NOT NULL)",
            name="ck_tenant_crypto_key_scope",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["intake_id"], ["intake.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_tenant_crypto_key_company",
        "tenant_crypto_key",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("company_id IS NOT NULL"),
    )
    op.create_index(
        "idx_tenant_crypto_key_intake",
        "tenant_crypto_key",
        ["intake_id"],
        unique=True,
        postgresql_where=sa.text("intake_id IS NOT NULL"),
    )

    op.create_table(
        "employee",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intake_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("niss_hash", postgresql.BYTEA(), nullable=False),
        sa.Column("niss_enc", postgresql.BYTEA(), nullable=False),
        sa.Column("name_enc", postgresql.BYTEA(), nullable=True),
        sa.Column("dob_enc", postgresql.BYTEA(), nullable=True),
        sa.Column(
            "first_permanent_elsewhere",
            sa.String(16),
            server_default=sa.text("'UNKNOWN'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(16),
            server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.Column(
            "status_source",
            sa.String(16),
            server_default=sa.text("'SS'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "company_id IS NOT NULL OR intake_id IS NOT NULL",
            name="ck_employee_scope",
        ),
        sa.CheckConstraint(
            "first_permanent_elsewhere IN ('UNKNOWN', 'NO', 'YES')",
            name="ck_employee_first_permanent",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'ON_LEAVE', 'TERMINATED')",
            name="ck_employee_status",
        ),
        sa.CheckConstraint(
            "status_source IN ('SS', 'USER', 'HRMS', 'ADMIN')",
            name="ck_employee_status_source",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["intake_id"], ["intake.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_employee_company_niss",
        "employee",
        ["company_id", "niss_hash"],
        unique=True,
        postgresql_where=sa.text(
            "company_id IS NOT NULL AND deleted_at IS NULL"
        ),
    )
    op.create_index(
        "idx_employee_intake_niss",
        "employee",
        ["intake_id", "niss_hash"],
        unique=True,
        postgresql_where=sa.text(
            "intake_id IS NOT NULL AND company_id IS NULL AND deleted_at IS NULL"
        ),
    )

    op.create_table(
        "stored_file",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intake_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("gcs_path", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("original_filename", sa.String(), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "company_id IS NOT NULL OR intake_id IS NOT NULL",
            name="ck_stored_file_scope",
        ),
        sa.CheckConstraint(
            "kind IN ("
            "'SS_EXPORT', 'EMPLOYMENT_CONTRACT', 'CONVERSION_DECLARATION', "
            "'AT_NO_DEBT', 'INVOICE_PDF', 'PROFORMA', 'OTHER'"
            ")",
            name="ck_stored_file_kind",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["intake_id"], ["intake.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["user_base.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("stored_file")
    op.drop_index("idx_employee_intake_niss", table_name="employee")
    op.drop_index("idx_employee_company_niss", table_name="employee")
    op.drop_table("employee")
    op.drop_index("idx_tenant_crypto_key_intake", table_name="tenant_crypto_key")
    op.drop_index("idx_tenant_crypto_key_company", table_name="tenant_crypto_key")
    op.drop_table("tenant_crypto_key")
