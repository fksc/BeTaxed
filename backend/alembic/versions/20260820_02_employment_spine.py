"""Employment spine: workplace, vínculo, pay, events (DEV-834).

Revision ID: 20260820_02_employment_spine
Revises: 20260820_01_intake_flow
Create Date: 2026-08-20

Canonical current state + event log. Apply/diff lives in app code.
employee_external_id is empty in v1 (HRMS-ready). first_permanent_source
from the OD-4 lock. Parked: company_headcount_month (SL-003).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260820_02_employment_spine"
down_revision: Union[str, None] = "20260820_01_intake_flow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "employee",
        sa.Column(
            "first_permanent_source",
            sa.String(24),
            server_default=sa.text("'UNKNOWN'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_employee_first_permanent_source",
        "employee",
        "first_permanent_source IN ('UNKNOWN', 'COMPANY_ONBOARDING', 'OPS')",
    )

    op.create_table(
        "workplace",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intake_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ss_label", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["intake_id"], ["intake.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "employee_external_id",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("system", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "system", name="uq_employee_external_id"),
    )

    op.create_table(
        "employment",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intake_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column(
            "actor_type",
            sa.String(32),
            server_default=sa.text("'TCO'"),
            nullable=False,
        ),
        sa.Column("actor_type_raw", sa.Text(), nullable=True),
        sa.Column("contract_modality", sa.String(32), nullable=False),
        sa.Column("contract_modality_raw", sa.Text(), nullable=True),
        sa.Column("work_mode", sa.String(32), nullable=True),
        sa.Column("work_mode_raw", sa.Text(), nullable=True),
        sa.Column("hours_per_week", sa.Numeric(6, 2), nullable=True),
        sa.Column("days_per_month", sa.Numeric(6, 2), nullable=True),
        sa.Column("percent_work", sa.Numeric(6, 2), nullable=True),
        sa.Column("profession_raw", sa.Text(), nullable=True),
        sa.Column("workplace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tsu_rate_pct", sa.Numeric(6, 3), nullable=True),
        sa.Column("rate_applied_from", sa.Date(), nullable=True),
        sa.Column("rate_applied_to", sa.Date(), nullable=True),
        sa.Column("ss_communicated_on", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "contract_modality IN ('SEM_TERMO', 'TERMO_CERTO', 'TERMO_INCERTO', 'OTHER')",
            name="ck_employment_modality",
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["intake_id"], ["intake.id"]),
        sa.ForeignKeyConstraint(["workplace_id"], ["workplace.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_employment_employee", "employment", ["employee_id"])

    op.create_table(
        "compensation_period",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("employment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column("base_salary", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["employment_id"], ["employment.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_comp_employment", "compensation_period", ["employment_id"])
    op.create_index(
        "idx_comp_open",
        "compensation_period",
        ["employment_id"],
        unique=True,
        postgresql_where=sa.text("period_to IS NULL"),
    )

    op.create_table(
        "employment_event",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intake_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("effective_on", sa.Date(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("old_salary", sa.Numeric(12, 2), nullable=True),
        sa.Column("new_salary", sa.Numeric(12, 2), nullable=True),
        sa.Column("old_modality", sa.String(32), nullable=True),
        sa.Column("new_modality", sa.String(32), nullable=True),
        sa.Column("old_rate_pct", sa.Numeric(6, 3), nullable=True),
        sa.Column("new_rate_pct", sa.Numeric(6, 3), nullable=True),
        sa.Column("leave_type", sa.String(24), nullable=True),
        sa.Column("initiator", sa.String(16), nullable=True),
        sa.Column("reason", sa.String(32), nullable=True),
        sa.Column("old_status", sa.String(16), nullable=True),
        sa.Column("new_status", sa.String(16), nullable=True),
        sa.Column("ss_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ("
            "'HIRED', 'TERMINATED', 'REHIRED', 'SALARY_CHANGED', "
            "'MODALITY_CHANGED', 'TSU_RATE_CHANGED', 'LEAVE_STARTED', "
            "'LEAVE_ENDED', 'MISSING_FROM_DECLARATION', 'STATUS_OVERRIDE', "
            "'SOURCE_CONFLICT')",
            name="ck_employment_event_type",
        ),
        sa.CheckConstraint(
            "source IN ('SS_DIFF', 'USER', 'ADMIN', 'HRMS', 'CONTRACT')",
            name="ck_employment_event_source",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["intake_id"], ["intake.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
        sa.ForeignKeyConstraint(["employment_id"], ["employment.id"]),
        sa.ForeignKeyConstraint(
            ["ss_batch_id"], ["ss_batch.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_event_employee", "employment_event", ["employee_id", "effective_on"]
    )
    op.create_index(
        "idx_event_company_type", "employment_event", ["company_id", "event_type"]
    )


def downgrade() -> None:
    op.drop_index("idx_event_company_type", table_name="employment_event")
    op.drop_index("idx_event_employee", table_name="employment_event")
    op.drop_table("employment_event")
    op.drop_index("idx_comp_open", table_name="compensation_period")
    op.drop_index("idx_comp_employment", table_name="compensation_period")
    op.drop_table("compensation_period")
    op.drop_index("idx_employment_employee", table_name="employment")
    op.drop_table("employment")
    op.drop_table("employee_external_id")
    op.drop_table("workplace")
    op.drop_constraint(
        "ck_employee_first_permanent_source", "employee", type_="check"
    )
    op.drop_column("employee", "first_permanent_source")
