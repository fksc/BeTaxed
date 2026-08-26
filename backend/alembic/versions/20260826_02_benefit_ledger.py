"""Internal benefit ledger (DEV-838, KB/05).

Revision ID: 20260826_02_benefit_ledger
Revises: 20260826_01_company_headcount_month
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260826_02_benefit_ledger"
down_revision: Union[str, None] = "20260826_01_company_headcount_month"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_stored_file_kind", "stored_file", type_="check")
    op.create_check_constraint(
        "ck_stored_file_kind",
        "stored_file",
        "kind IN ("
        "'SS_EXPORT', 'EMPLOYMENT_CONTRACT', 'CONVERSION_DECLARATION', "
        "'SS_NO_DEBT', 'AT_NO_DEBT', 'INVOICE_PDF', 'PROFORMA', 'OTHER')",
    )

    op.create_table(
        "incentive_regime",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("max_age_inclusive", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("window_months", sa.Integer(), nullable=False, server_default="60"),
        sa.Column(
            "employer_rate", sa.Numeric(8, 6), nullable=False, server_default="0.2375"
        ),
        sa.Column(
            "reduction_factor", sa.Numeric(8, 6), nullable=False, server_default="0.5"
        ),
        sa.Column("apply_within_days", sa.Integer(), nullable=False, server_default="10"),
        sa.Column(
            "late_start", sa.String(24), nullable=False, server_default="'NEXT_MONTH'"
        ),
        sa.Column(
            "clawback_after_end_months",
            sa.Integer(),
            nullable=False,
            server_default="24",
        ),
        sa.Column(
            "no_debt_valid_months", sa.Integer(), nullable=False, server_default="4"
        ),
        sa.UniqueConstraint("code", "valid_from", name="uq_incentive_regime_code_from"),
        sa.CheckConstraint(
            "late_start IN ('NEXT_MONTH', 'PRORATA', 'FULL_MONTH')",
            name="ck_incentive_regime_late_start",
        ),
    )
    op.execute(
        """
        INSERT INTO incentive_regime (
            code, valid_from, max_age_inclusive, window_months,
            employer_rate, reduction_factor, apply_within_days, late_start,
            clawback_after_end_months, no_debt_valid_months
        ) VALUES (
            'PT_SS_YOUNG_FIRST_PERMANENT', DATE '2023-01-01', 30, 60,
            0.2375, 0.5, 10, 'NEXT_MONTH', 24, 4
        )
        """
    )

    op.create_table(
        "company_application",
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
        sa.Column(
            "regime_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incentive_regime.id"),
            nullable=False,
        ),
        sa.Column("submitted_on", sa.Date(), nullable=True),
        sa.Column(
            "decision", sa.String(16), nullable=False, server_default="'NOT_SUBMITTED'"
        ),
        sa.Column("decision_on", sa.Date(), nullable=True),
        sa.Column("headcount_current", sa.Integer(), nullable=True),
        sa.Column("headcount_trailing_12_avg", sa.Numeric(10, 2), nullable=True),
        sa.Column("headcount_test_pass", sa.Boolean(), nullable=True),
        sa.Column("ss_regularized_at_submit", sa.Boolean(), nullable=True),
        sa.Column("at_regularized_at_submit", sa.Boolean(), nullable=True),
        sa.Column("payroll_not_in_arrears_at_submit", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "decision IN ('NOT_SUBMITTED', 'SUBMITTED', 'GRANTED', 'REJECTED', 'CEASED')",
            name="ck_company_application_decision",
        ),
    )
    op.create_index(
        "idx_company_application_company", "company_application", ["company_id"]
    )

    op.create_table(
        "company_certificate",
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
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column(
            "file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stored_file.id"),
            nullable=False,
        ),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column(
            "valid_until_overridden",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "kind IN ('SS_NO_DEBT', 'AT_NO_DEBT')",
            name="ck_company_certificate_kind",
        ),
    )
    op.create_index(
        "idx_company_certificate_company_kind",
        "company_certificate",
        ["company_id", "kind", "valid_until"],
    )

    op.create_table(
        "benefit_case",
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
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employee.id"),
            nullable=False,
        ),
        sa.Column(
            "employment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employment.id"),
            nullable=True,
        ),
        sa.Column(
            "regime_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incentive_regime.id"),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("company_application.id"),
            nullable=True,
        ),
        sa.Column("sem_termo_on", sa.Date(), nullable=True),
        sa.Column("window_ends_on", sa.Date(), nullable=True),
        sa.Column("applied_on", sa.Date(), nullable=True),
        sa.Column("benefit_starts_on", sa.Date(), nullable=True),
        sa.Column("age_at_sem_termo", sa.Numeric(6, 3), nullable=True),
        sa.Column("first_permanent_elsewhere_at_submit", sa.String(16), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("ineligibility_code", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "state IN ("
            "'DETECTED', 'NEEDS_CONVERSION', 'NEEDS_FIRST_JOB_CHECK', 'READY', "
            "'SUBMITTED', 'GRANTED', 'REJECTED', 'CEASED', 'EXPIRED', 'CLAWBACK')",
            name="ck_benefit_case_state",
        ),
        sa.UniqueConstraint(
            "employee_id",
            "regime_id",
            "employment_id",
            name="uq_benefit_case_employee_regime_employment",
        ),
    )
    op.create_index(
        "idx_benefit_case_company_state", "benefit_case", ["company_id", "state"]
    )

    op.create_table(
        "saving_month",
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
        sa.Column(
            "benefit_case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("benefit_case.id"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employee.id"),
            nullable=False,
        ),
        sa.Column("year_month", sa.Date(), nullable=False),
        sa.Column("base_salary", sa.Numeric(12, 2), nullable=False),
        sa.Column("saving_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("fee_percent", sa.Numeric(8, 6), nullable=False),
        sa.Column("fee_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("billable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invoice_line_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint(
            "benefit_case_id", "year_month", name="uq_saving_month_case_month"
        ),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM year_month) = 1",
            name="ck_saving_month_first_of_month",
        ),
    )
    op.create_index(
        "idx_saving_month_company", "saving_month", ["company_id", "year_month"]
    )

    op.create_foreign_key(
        "fk_intake_teaser_regime",
        "intake",
        "incentive_regime",
        ["teaser_regime_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_intake_teaser_regime", "intake", type_="foreignkey")
    op.drop_index("idx_saving_month_company", table_name="saving_month")
    op.drop_table("saving_month")
    op.drop_index("idx_benefit_case_company_state", table_name="benefit_case")
    op.drop_table("benefit_case")
    op.drop_index(
        "idx_company_certificate_company_kind", table_name="company_certificate"
    )
    op.drop_table("company_certificate")
    op.drop_index("idx_company_application_company", table_name="company_application")
    op.drop_table("company_application")
    op.drop_table("incentive_regime")
    op.drop_constraint("ck_stored_file_kind", "stored_file", type_="check")
    op.create_check_constraint(
        "ck_stored_file_kind",
        "stored_file",
        "kind IN ("
        "'SS_EXPORT', 'EMPLOYMENT_CONTRACT', 'CONVERSION_DECLARATION', "
        "'AT_NO_DEBT', 'INVOICE_PDF', 'PROFORMA', 'OTHER')",
    )
