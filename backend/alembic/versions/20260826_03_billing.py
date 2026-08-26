"""Invoices, payments, commercial_terms (DEV-839, KB/06).

Revision ID: 20260826_03_billing
Revises: 20260826_02_benefit_ledger
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260826_03_billing"
down_revision: Union[str, None] = "20260826_02_benefit_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commercial_terms",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("company.id"),
            nullable=False,
        ),
        sa.Column("fee_percent", sa.Numeric(8, 6), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.UniqueConstraint("company_id", "valid_from", name="uq_commercial_terms_company_from"),
    )
    op.create_index("idx_commercial_terms_company", "commercial_terms", ["company_id"])

    op.create_table(
        "invoice",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("company.id"),
            nullable=False,
        ),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=False),
        sa.Column(
            "status", sa.String(24), nullable=False, server_default="'DRAFT'"
        ),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="'EUR'"),
        sa.Column(
            "subtotal", sa.Numeric(12, 2), nullable=False, server_default="0"
        ),
        sa.Column(
            "tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0"
        ),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("issued_on", sa.Date(), nullable=True),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("paid_on", sa.Date(), nullable=True),
        sa.Column(
            "consolidates_invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoice.id"),
            nullable=True,
        ),
        sa.Column("stripe_invoice_id", sa.String(128), nullable=True),
        sa.Column("stripe_mandate_id", sa.String(128), nullable=True),
        sa.Column("certified_external_id", sa.String(128), nullable=True),
        sa.Column("legal_invoice_number", sa.String(64), nullable=True),
        sa.Column("atcud", sa.String(64), nullable=True),
        sa.Column(
            "proforma_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stored_file.id"),
            nullable=True,
        ),
        sa.Column(
            "legal_invoice_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stored_file.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "status IN ("
            "'DRAFT', 'ISSUED', 'DUE', 'LATE', 'PAID', "
            "'CONSOLIDATED', 'VOID', 'MANUALLY_RESOLVED')",
            name="ck_invoice_status",
        ),
    )
    op.create_index("idx_invoice_company_status", "invoice", ["company_id", "status"])

    op.create_table(
        "invoice_line",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoice.id"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employee.id"),
            nullable=True,
        ),
        sa.Column(
            "benefit_case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("benefit_case.id"),
            nullable=True,
        ),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("fee_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("saving_amount", sa.Numeric(12, 2), nullable=True),
    )
    op.create_index("idx_invoice_line_invoice", "invoice_line", ["invoice_id"])

    op.create_table(
        "payment",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoice.id"),
            nullable=False,
        ),
        sa.Column("method", sa.String(24), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("external_ref", sa.String(128), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "method IN ('STRIPE_SEPA', 'STRIPE_OTHER', 'MANUAL', 'CERTIFIED')",
            name="ck_payment_method",
        ),
    )

    op.create_table(
        "invoice_status_event",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoice.id"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(24), nullable=True),
        sa.Column("to_status", sa.String(24), nullable=False),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_base.id"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "idx_invoice_status_event_invoice", "invoice_status_event", ["invoice_id"]
    )

    op.create_foreign_key(
        "fk_saving_month_invoice_line",
        "saving_month",
        "invoice_line",
        ["invoice_line_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_saving_month_invoice_line", "saving_month", type_="foreignkey")
    op.drop_index("idx_invoice_status_event_invoice", table_name="invoice_status_event")
    op.drop_table("invoice_status_event")
    op.drop_table("payment")
    op.drop_index("idx_invoice_line_invoice", table_name="invoice_line")
    op.drop_table("invoice_line")
    op.drop_index("idx_invoice_company_status", table_name="invoice")
    op.drop_table("invoice")
    op.drop_index("idx_commercial_terms_company", table_name="commercial_terms")
    op.drop_table("commercial_terms")
