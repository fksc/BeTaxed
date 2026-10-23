"""Employee NIF and contract inbox for batch PDF association (DEV-850).

Revision ID: 20261009_01_contract_inbox
Revises: 20261008_01_establishment
Create Date: 2026-10-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261009_01_contract_inbox"
down_revision: Union[str, None] = "20261008_01_establishment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("employee", sa.Column("nif_enc", postgresql.BYTEA(), nullable=True))
    op.add_column("employee", sa.Column("nif_hash", postgresql.BYTEA(), nullable=True))
    op.create_index(
        "idx_employee_company_nif",
        "employee",
        ["company_id", "nif_hash"],
        unique=True,
        postgresql_where=sa.text(
            "company_id IS NOT NULL AND nif_hash IS NOT NULL AND deleted_at IS NULL"
        ),
    )
    op.create_table(
        "contract_inbox",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column("match_via", sa.String(length=8), nullable=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "employment_document_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("nif_enc", postgresql.BYTEA(), nullable=True),
        sa.Column("name_enc", postgresql.BYTEA(), nullable=True),
        sa.Column("niss_enc", postgresql.BYTEA(), nullable=True),
        sa.Column("employer_nif_mismatch", sa.Boolean(), nullable=True),
        sa.Column(
            "nif_conflict",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'MATCHED', 'UNMATCHED', 'FAILED')",
            name="ck_contract_inbox_status",
        ),
        sa.CheckConstraint(
            "match_via IS NULL OR match_via IN ('NIF', 'NAME', 'NISS')",
            name="ck_contract_inbox_match_via",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["file_id"], ["stored_file.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["user_base.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
        sa.ForeignKeyConstraint(
            ["employment_document_id"], ["employment_document.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_contract_inbox_company_status",
        "contract_inbox",
        ["company_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_contract_inbox_company_status", table_name="contract_inbox")
    op.drop_table("contract_inbox")
    op.drop_index("idx_employee_company_nif", table_name="employee")
    op.drop_column("employee", "nif_hash")
    op.drop_column("employee", "nif_enc")
