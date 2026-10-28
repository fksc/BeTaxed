"""Rename close stages to approved and rejected.

Revision ID: 20261026_03_close_stage_names
Revises: 20261026_02_request_case_stage_stack
Create Date: 2026-10-26
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20261026_03_close_stage_names"
down_revision: Union[str, None] = "20261026_02_request_case_stage_stack"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE pipeline_stage
            SET code = 'closed_approved', name = 'Closed approved'
            WHERE code = 'closed_won'
        """
    )
    op.execute(
        """
        UPDATE pipeline_stage
            SET code = 'closed_rejected', name = 'Closed rejected'
            WHERE code = 'closed_lost'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE pipeline_stage
            SET code = 'closed_won', name = 'Closed won'
            WHERE code = 'closed_approved'
        """
    )
    op.execute(
        """
        UPDATE pipeline_stage
            SET code = 'closed_lost', name = 'Closed lost'
            WHERE code = 'closed_rejected'
        """
    )
