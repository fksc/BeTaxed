"""Store the Cal.com time booked from a public intake.

Revision ID: 20261109_02_intake_meeting
Revises: 20261109_01_company_pending
Create Date: 2026-11-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261109_02_intake_meeting"
down_revision: Union[str, None] = "20261109_01_company_pending"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "intake",
        sa.Column("meeting_starts_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("intake", "meeting_starts_at")
