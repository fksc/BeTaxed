"""Remember the stages a request case has entered, so staff can step back.

Revision ID: 20261026_02_request_case_stage_stack
Revises: 20261026_01_request_case
Create Date: 2026-10-26
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20261026_02_request_case_stage_stack"
down_revision: Union[str, None] = "20261026_01_request_case"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE request_case
            ADD COLUMN stage_stack UUID[] NOT NULL DEFAULT ARRAY[]::uuid[]
        """
    )
    op.execute(
        """
        UPDATE request_case
            SET stage_stack = ARRAY[stage_id]
            WHERE stage_stack = ARRAY[]::uuid[]
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE request_case DROP COLUMN IF EXISTS stage_stack")
