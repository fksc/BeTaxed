"""Establishment (ESTABEE) and links from employment and ss_batch (DEV-857).

Revision ID: 20261008_01_establishment
Revises: 20260826_06_invite_names
Create Date: 2026-10-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261008_01_establishment"
down_revision: Union[str, None] = "20260826_06_invite_names"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "establishment",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("ss_code", sa.String(length=4), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'OPEN'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "ss_code", name="uq_establishment_company_ss_code"
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'CLOSED')",
            name="ck_establishment_status",
        ),
        sa.CheckConstraint(
            "ss_code ~ '^[0-9]{4}$'",
            name="ck_establishment_ss_code",
        ),
    )
    op.create_index(
        "idx_establishment_company",
        "establishment",
        ["company_id"],
    )
    op.add_column(
        "employment",
        sa.Column("establishment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_employment_establishment",
        "employment",
        "establishment",
        ["establishment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "ss_batch",
        sa.Column("establishment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_ss_batch_establishment",
        "ss_batch",
        "establishment",
        ["establishment_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_ss_batch_establishment", "ss_batch", type_="foreignkey")
    op.drop_column("ss_batch", "establishment_id")
    op.drop_constraint(
        "fk_employment_establishment", "employment", type_="foreignkey"
    )
    op.drop_column("employment", "establishment_id")
    op.drop_index("idx_establishment_company", table_name="establishment")
    op.drop_table("establishment")
