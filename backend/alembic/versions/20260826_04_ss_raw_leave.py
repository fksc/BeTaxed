"""Remunerações leave raw rows (DEV-849, SL-004).

Revision ID: 20260826_04_ss_raw_leave
Revises: 20260826_03_billing
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260826_04_ss_raw_leave"
down_revision: Union[str, None] = "20260826_03_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ss_batch",
        sa.Column(
            "leave_declared",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.drop_constraint("ck_ss_batch_file_kind", "ss_batch_file", type_="check")
    op.create_check_constraint(
        "ck_ss_batch_file_kind",
        "ss_batch_file",
        "kind IN ('COMBINED_XLSX', 'VINCULOS', 'CONTRATOS', 'REMUNERACOES', 'OTHER')",
    )
    op.create_table(
        "ss_raw_leave",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ss_batch.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("niss_hash", postgresql.BYTEA(), nullable=False),
        sa.Column("niss_enc", postgresql.BYTEA(), nullable=False),
        sa.Column("leave_type", sa.String(24), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column("leftover", postgresql.JSONB(), nullable=True),
        sa.CheckConstraint(
            "leave_type IN ('PARENTAL', 'SICKNESS', 'UNPAID', 'OTHER')",
            name="ck_ss_raw_leave_type",
        ),
    )
    op.create_index(
        "idx_ss_raw_leave_batch_niss",
        "ss_raw_leave",
        ["batch_id", "niss_hash"],
    )


def downgrade() -> None:
    op.drop_index("idx_ss_raw_leave_batch_niss", table_name="ss_raw_leave")
    op.drop_table("ss_raw_leave")
    op.drop_constraint("ck_ss_batch_file_kind", "ss_batch_file", type_="check")
    op.create_check_constraint(
        "ck_ss_batch_file_kind",
        "ss_batch_file",
        "kind IN ('COMBINED_XLSX', 'VINCULOS', 'CONTRATOS', 'OTHER')",
    )
    op.drop_column("ss_batch", "leave_declared")
