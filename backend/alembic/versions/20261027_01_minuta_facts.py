"""Company, employee, and request-case facts for minuta tokens.

Revision ID: 20261027_01_minuta_facts
Revises: 20261026_03_close_stage_names
Create Date: 2026-10-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261027_01_minuta_facts"
down_revision: Union[str, None] = "20261026_03_close_stage_names"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("company", sa.Column("registered_address", sa.Text(), nullable=True))
    op.add_column("company", sa.Column("signatory_name", sa.String(length=255), nullable=True))
    op.add_column("employee", sa.Column("address_enc", postgresql.BYTEA(), nullable=True))
    op.add_column(
        "minuta_template",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    for table in ("employment_document", "contract_inbox"):
        op.add_column(table, sa.Column("employer_legal_name", sa.String(length=255), nullable=True))
        op.add_column(table, sa.Column("employer_address", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("employer_niss_enc", postgresql.BYTEA(), nullable=True))
        op.add_column(table, sa.Column("signatory_name", sa.String(length=255), nullable=True))
        op.add_column(table, sa.Column("employee_address_enc", postgresql.BYTEA(), nullable=True))
        op.add_column(table, sa.Column("term_started_on", sa.Date(), nullable=True))
        op.add_column(table, sa.Column("converted_on", sa.Date(), nullable=True))
        op.add_column(table, sa.Column("declared_on", sa.Date(), nullable=True))
        op.add_column(table, sa.Column("signing_place", sa.String(length=255), nullable=True))
    op.add_column("contract_inbox", sa.Column("legal_name_mismatch", sa.Boolean(), nullable=True))
    op.add_column("request_case", sa.Column("person_name", sa.String(length=255), nullable=True))
    op.add_column("request_case", sa.Column("person_address", sa.Text(), nullable=True))
    op.add_column("request_case", sa.Column("person_nif_enc", postgresql.BYTEA(), nullable=True))
    op.add_column("request_case", sa.Column("person_niss_enc", postgresql.BYTEA(), nullable=True))
    op.add_column("request_case", sa.Column("company_name", sa.String(length=255), nullable=True))
    op.add_column("request_case", sa.Column("company_address", sa.Text(), nullable=True))
    op.add_column(
        "request_case", sa.Column("company_signatory_name", sa.String(length=255), nullable=True)
    )
    op.add_column("request_case", sa.Column("company_nif_enc", postgresql.BYTEA(), nullable=True))
    op.add_column("request_case", sa.Column("company_niss_enc", postgresql.BYTEA(), nullable=True))
    op.add_column("request_case", sa.Column("contract_started_on", sa.Date(), nullable=True))
    op.add_column("request_case", sa.Column("converted_on", sa.Date(), nullable=True))
    op.add_column("request_case", sa.Column("declared_on", sa.Date(), nullable=True))
    op.add_column("request_case", sa.Column("signed_place", sa.String(length=255), nullable=True))


def downgrade() -> None:
    for column in (
        "signed_place",
        "declared_on",
        "converted_on",
        "contract_started_on",
        "company_niss_enc",
        "company_nif_enc",
        "company_signatory_name",
        "company_address",
        "company_name",
        "person_niss_enc",
        "person_nif_enc",
        "person_address",
        "person_name",
    ):
        op.drop_column("request_case", column)
    op.drop_column("contract_inbox", "legal_name_mismatch")
    for table in ("contract_inbox", "employment_document"):
        for column in (
            "signing_place",
            "declared_on",
            "converted_on",
            "term_started_on",
            "employee_address_enc",
            "signatory_name",
            "employer_niss_enc",
            "employer_address",
            "employer_legal_name",
        ):
            op.drop_column(table, column)
    op.drop_column("minuta_template", "updated_at")
    op.drop_column("employee", "address_enc")
    op.drop_column("company", "signatory_name")
    op.drop_column("company", "registered_address")
