"""Sales-call contact on pass-1 intake (DEV-896).

Revision ID: 20261108_01_intake_sales_call
Revises: 20261028_02_ss_subconta
Create Date: 2026-11-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261108_01_intake_sales_call"
down_revision: Union[str, None] = "20261028_02_ss_subconta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("intake", sa.Column("sales_call_name", sa.String(length=255), nullable=True))
    op.add_column("intake", sa.Column("sales_call_email", sa.String(length=255), nullable=True))
    op.add_column("intake", sa.Column("sales_call_phone", sa.String(length=40), nullable=True))
    op.add_column(
        "intake",
        sa.Column("sales_call_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("intake", "sales_call_at")
    op.drop_column("intake", "sales_call_phone")
    op.drop_column("intake", "sales_call_email")
    op.drop_column("intake", "sales_call_name")
