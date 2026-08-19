"""SS ingest tables: ss_batch, files, raw vínculos / contratos (DEV-831).

Revision ID: 20260818_03_ss_ingest
Revises: 20260818_02_encryption
Create Date: 2026-08-18

Addresses DEV-831. Parse status includes APPLIED for later apply/diff;
this revision only creates the raw ingest spine.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260818_03_ss_ingest"
down_revision: Union[str, None] = "20260818_02_encryption"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ss_batch",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intake_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("period_year_month", sa.Date(), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("employer_niss_hash", postgresql.BYTEA(), nullable=True),
        sa.Column(
            "parse_status",
            sa.String(16),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("export_label", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "company_id IS NOT NULL OR intake_id IS NOT NULL",
            name="ck_ss_batch_scope",
        ),
        sa.CheckConstraint(
            "parse_status IN ('PENDING', 'PARSED', 'FAILED', 'APPLIED', 'DISCARDED')",
            name="ck_ss_batch_parse_status",
        ),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM period_year_month) = 1",
            name="ck_ss_batch_period_first_of_month",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["intake_id"], ["intake.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["user_base.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ss_batch_company_period",
        "ss_batch",
        ["company_id", "period_year_month"],
    )
    op.create_index("idx_ss_batch_intake", "ss_batch", ["intake_id"])

    op.create_table(
        "ss_batch_file",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.CheckConstraint(
            "kind IN ('COMBINED_XLSX', 'VINCULOS', 'CONTRATOS', 'OTHER')",
            name="ck_ss_batch_file_kind",
        ),
        sa.ForeignKeyConstraint(["batch_id"], ["ss_batch.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["stored_file.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ss_raw_vinculo",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("niss_hash", postgresql.BYTEA(), nullable=False),
        sa.Column("niss_enc", postgresql.BYTEA(), nullable=False),
        sa.Column("name_enc", postgresql.BYTEA(), nullable=True),
        sa.Column("dob_enc", postgresql.BYTEA(), nullable=True),
        sa.Column("vinculo_raw", sa.Text(), nullable=True),
        sa.Column("communicated_on", sa.Date(), nullable=True),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column("rate_from", sa.Date(), nullable=True),
        sa.Column("rate_to", sa.Date(), nullable=True),
        sa.Column("taxa_pct", sa.Numeric(6, 3), nullable=True),
        sa.Column("workplace_ss_label", sa.Text(), nullable=True),
        sa.Column("leftover", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["ss_batch.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ss_raw_vinculo_batch_niss",
        "ss_raw_vinculo",
        ["batch_id", "niss_hash"],
    )

    op.create_table(
        "ss_raw_contrato",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("niss_hash", postgresql.BYTEA(), nullable=False),
        sa.Column("niss_enc", postgresql.BYTEA(), nullable=False),
        sa.Column("name_enc", postgresql.BYTEA(), nullable=True),
        sa.Column("modality_raw", sa.Text(), nullable=True),
        sa.Column("work_mode_raw", sa.Text(), nullable=True),
        sa.Column("contract_started_on", sa.Date(), nullable=True),
        sa.Column("contract_ended_on", sa.Date(), nullable=True),
        sa.Column("profession_raw", sa.Text(), nullable=True),
        sa.Column("percent_work", sa.Numeric(6, 2), nullable=True),
        sa.Column("hours_work", sa.Numeric(6, 2), nullable=True),
        sa.Column("days_work", sa.Numeric(6, 2), nullable=True),
        sa.Column("motivo_raw", sa.Text(), nullable=True),
        sa.Column("rendimento_from", sa.Date(), nullable=True),
        sa.Column("rendimento_to", sa.Date(), nullable=True),
        sa.Column("base_salary", sa.Numeric(12, 2), nullable=True),
        sa.Column("leftover", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["ss_batch.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ss_raw_contrato_batch_niss",
        "ss_raw_contrato",
        ["batch_id", "niss_hash"],
    )


def downgrade() -> None:
    op.drop_index("idx_ss_raw_contrato_batch_niss", table_name="ss_raw_contrato")
    op.drop_table("ss_raw_contrato")
    op.drop_index("idx_ss_raw_vinculo_batch_niss", table_name="ss_raw_vinculo")
    op.drop_table("ss_raw_vinculo")
    op.drop_table("ss_batch_file")
    op.drop_index("idx_ss_batch_intake", table_name="ss_batch")
    op.drop_index("idx_ss_batch_company_period", table_name="ss_batch")
    op.drop_table("ss_batch")
