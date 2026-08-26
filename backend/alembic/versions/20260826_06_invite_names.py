"""Invite given/family name on company_invite (sales-led admin).

Revision ID: 20260826_06_invite_names
Revises: 20260826_05_company_invite
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260826_06_invite_names"
down_revision: Union[str, None] = "20260826_05_company_invite"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company_invite",
        sa.Column("given_name", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "company_invite",
        sa.Column("family_name", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("company_invite", "family_name")
    op.drop_column("company_invite", "given_name")
