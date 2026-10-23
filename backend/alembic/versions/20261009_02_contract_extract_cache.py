"""Remember contract extract fields so the same file hash skips Gemini.

Revision ID: 20261009_02_contract_extract_cache
Revises: 20261009_01_contract_inbox
Create Date: 2026-10-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261009_02_contract_extract_cache"
down_revision: Union[str, None] = "20261009_01_contract_inbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contract_inbox", sa.Column("doc_kind", sa.String(length=24), nullable=True))
    op.add_column("contract_inbox", sa.Column("signed_on", sa.Date(), nullable=True))
    op.add_column("contract_inbox", sa.Column("term_end_on", sa.Date(), nullable=True))
    op.create_check_constraint(
        "ck_contract_inbox_doc_kind",
        "contract_inbox",
        "doc_kind IS NULL OR doc_kind IN ('SEM_TERMO', 'TERMO', 'CONVERSION')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_contract_inbox_doc_kind", "contract_inbox", type_="check")
    op.drop_column("contract_inbox", "term_end_on")
    op.drop_column("contract_inbox", "signed_on")
    op.drop_column("contract_inbox", "doc_kind")
