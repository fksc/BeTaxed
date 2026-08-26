"""Internal benefit regime, cases, and saving_month (KB/05, DEV-838)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class IncentiveRegime(Base):
    __tablename__ = "incentive_regime"
    __table_args__ = (
        UniqueConstraint("code", "valid_from", name="uq_incentive_regime_code_from"),
        CheckConstraint(
            "late_start IN ('NEXT_MONTH', 'PRORATA', 'FULL_MONTH')",
            name="ck_incentive_regime_late_start",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    max_age_inclusive: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("30")
    )
    window_months: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("60")
    )
    employer_rate: Mapped[Decimal] = mapped_column(
        Numeric(8, 6), nullable=False, server_default=text("0.2375")
    )
    reduction_factor: Mapped[Decimal] = mapped_column(
        Numeric(8, 6), nullable=False, server_default=text("0.5")
    )
    apply_within_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("10")
    )
    late_start: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'NEXT_MONTH'")
    )
    clawback_after_end_months: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("24")
    )
    no_debt_valid_months: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("4")
    )


class CompanyApplication(Base):
    __tablename__ = "company_application"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('NOT_SUBMITTED', 'SUBMITTED', 'GRANTED', 'REJECTED', 'CEASED')",
            name="ck_company_application_decision",
        ),
        Index("idx_company_application_company", "company_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=False
    )
    regime_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incentive_regime.id"), nullable=False
    )
    submitted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    decision: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'NOT_SUBMITTED'")
    )
    decision_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    headcount_current: Mapped[int | None] = mapped_column(Integer, nullable=True)
    headcount_trailing_12_avg: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    headcount_test_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ss_regularized_at_submit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    at_regularized_at_submit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    payroll_not_in_arrears_at_submit: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CompanyCertificate(Base):
    __tablename__ = "company_certificate"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('SS_NO_DEBT', 'AT_NO_DEBT')",
            name="ck_company_certificate_kind",
        ),
        Index(
            "idx_company_certificate_company_kind",
            "company_id",
            "kind",
            "valid_until",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stored_file.id"), nullable=False
    )
    issued_on: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until_overridden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BenefitCase(Base):
    __tablename__ = "benefit_case"
    __table_args__ = (
        CheckConstraint(
            "state IN ("
            "'DETECTED', 'NEEDS_CONVERSION', 'NEEDS_FIRST_JOB_CHECK', 'READY', "
            "'SUBMITTED', 'GRANTED', 'REJECTED', 'CEASED', 'EXPIRED', 'CLAWBACK')",
            name="ck_benefit_case_state",
        ),
        UniqueConstraint(
            "employee_id",
            "regime_id",
            "employment_id",
            name="uq_benefit_case_employee_regime_employment",
        ),
        Index("idx_benefit_case_company_state", "company_id", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False
    )
    employment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employment.id"), nullable=True
    )
    regime_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incentive_regime.id"), nullable=False
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company_application.id"), nullable=True
    )
    sem_termo_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    window_ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    applied_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    benefit_starts_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    age_at_sem_termo: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 3), nullable=True
    )
    first_permanent_elsewhere_at_submit: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    ineligibility_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SavingMonth(Base):
    __tablename__ = "saving_month"
    __table_args__ = (
        UniqueConstraint(
            "benefit_case_id", "year_month", name="uq_saving_month_case_month"
        ),
        CheckConstraint(
            "EXTRACT(DAY FROM year_month) = 1",
            name="ck_saving_month_first_of_month",
        ),
        Index("idx_saving_month_company", "company_id", "year_month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=False
    )
    benefit_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("benefit_case.id"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False
    )
    year_month: Mapped[date] = mapped_column(Date, nullable=False)
    base_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    saving_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fee_percent: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    billable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invoice_line_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoice_line.id"), nullable=True
    )
