"""company_headcount_month for SS and USER sources (DEV-835, SL-003).

Revision ID: 20260826_01_company_headcount_month
Revises: 20260825_01_contracts_notifications
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260826_01_company_headcount_month"
down_revision: Union[str, None] = "20260825_01_contracts_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_headcount_month",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("year_month", sa.Date(), nullable=False),
        sa.Column("headcount", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("source_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(
            ["source_batch_id"], ["ss_batch.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "year_month",
            "source",
            name="uq_company_headcount_month_company_year_source",
        ),
        sa.CheckConstraint(
            "source IN ('SS_BATCH', 'USER')",
            name="ck_company_headcount_month_source",
        ),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM year_month) = 1",
            name="ck_company_headcount_month_first_of_month",
        ),
        sa.CheckConstraint(
            "headcount >= 0",
            name="ck_company_headcount_month_nonneg",
        ),
    )
    op.create_index(
        "idx_company_headcount_month_company",
        "company_headcount_month",
        ["company_id", "year_month"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_company_headcount_month_company",
        table_name="company_headcount_month",
    )
    op.drop_table("company_headcount_month")
