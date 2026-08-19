"""SS batch employer NISS envelope for convert re-hash (DEV-832).

Revision ID: 20260820_01_intake_flow
Revises: 20260818_03_ss_ingest
Create Date: 2026-08-20

HMAC of employer NISS is per-tenant. Convert moves intake-scoped hashes to
company scope; plaintext must be recoverable via employer_niss_enc.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260820_01_intake_flow"
down_revision: Union[str, None] = "20260818_03_ss_ingest"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ss_batch",
        sa.Column("employer_niss_enc", postgresql.BYTEA(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ss_batch", "employer_niss_enc")
