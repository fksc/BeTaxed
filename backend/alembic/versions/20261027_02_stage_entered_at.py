"""When the request case entered its current stage.

Revision ID: 20261027_02_stage_entered_at
Revises: 20261027_01_minuta_facts
Create Date: 2026-10-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261027_02_stage_entered_at"
down_revision: Union[str, None] = "20261027_01_minuta_facts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "request_case",
        sa.Column("stage_entered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE request_case SET stage_entered_at = opened_at")
    op.alter_column("request_case", "stage_entered_at", nullable=False)


def downgrade() -> None:
    op.drop_column("request_case", "stage_entered_at")
