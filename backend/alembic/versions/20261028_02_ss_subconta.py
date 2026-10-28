"""Encrypted Segurança Social sub-conta per company.

Revision ID: 20261028_02_ss_subconta
Revises: 20261028_01_request_case_event
Create Date: 2026-10-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261028_02_ss_subconta"
down_revision: Union[str, None] = "20261028_01_request_case_event"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company",
        sa.Column("ss_subconta_username_enc", postgresql.BYTEA(), nullable=True),
    )
    op.add_column(
        "company",
        sa.Column("ss_subconta_password_enc", postgresql.BYTEA(), nullable=True),
    )
    op.add_column(
        "company",
        sa.Column("ss_subconta_available_on", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("company", "ss_subconta_available_on")
    op.drop_column("company", "ss_subconta_password_enc")
    op.drop_column("company", "ss_subconta_username_enc")
