"""Allow a company to wait inactive until staff activates it.

Revision ID: 20261109_01_company_pending
Revises: 20261108_01_intake_sales_call
Create Date: 2026-11-09
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20261109_01_company_pending"
down_revision: Union[str, None] = "20261108_01_intake_sales_call"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_company_status", "company", type_="check")
    op.create_check_constraint(
        "ck_company_status",
        "company",
        "status IN ('PENDING', 'ACTIVE', 'SUSPENDED', 'CHURNED')",
    )


def downgrade() -> None:
    op.execute("UPDATE company SET status = 'SUSPENDED' WHERE status = 'PENDING'")
    op.drop_constraint("ck_company_status", "company", type_="check")
    op.create_check_constraint(
        "ck_company_status",
        "company",
        "status IN ('ACTIVE', 'SUSPENDED', 'CHURNED')",
    )
