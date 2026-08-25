"""Employment and document models with encrypted PII (KB/02, KB/04, DEV-830/834)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Employee(Base):
    __tablename__ = "employee"
    __table_args__ = (
        CheckConstraint(
            "company_id IS NOT NULL OR intake_id IS NOT NULL",
            name="ck_employee_scope",
        ),
        CheckConstraint(
            "first_permanent_elsewhere IN ('UNKNOWN', 'NO', 'YES')",
            name="ck_employee_first_permanent",
        ),
        CheckConstraint(
            "first_permanent_source IN ('UNKNOWN', 'COMPANY_ONBOARDING', 'OPS')",
            name="ck_employee_first_permanent_source",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'ON_LEAVE', 'TERMINATED')",
            name="ck_employee_status",
        ),
        CheckConstraint(
            "status_source IN ('SS', 'USER', 'HRMS', 'ADMIN')",
            name="ck_employee_status_source",
        ),
        Index(
            "idx_employee_company_niss",
            "company_id",
            "niss_hash",
            unique=True,
            postgresql_where=text(
                "company_id IS NOT NULL AND deleted_at IS NULL"
            ),
        ),
        Index(
            "idx_employee_intake_niss",
            "intake_id",
            "niss_hash",
            unique=True,
            postgresql_where=text(
                "intake_id IS NOT NULL AND company_id IS NULL AND deleted_at IS NULL"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("company.id"),
        nullable=True,
    )
    intake_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intake.id"),
        nullable=True,
    )
    niss_hash: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    niss_enc: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    name_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    dob_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    first_permanent_elsewhere: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'UNKNOWN'")
    )
    first_permanent_source: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'UNKNOWN'")
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'ACTIVE'")
    )
    status_source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'SS'")
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Workplace(Base):
    __tablename__ = "workplace"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=True
    )
    intake_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intake.id"), nullable=True
    )
    ss_label: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )


class EmployeeExternalId(Base):
    __tablename__ = "employee_external_id"
    __table_args__ = (
        UniqueConstraint("employee_id", "system", name="uq_employee_external_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False
    )
    system: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)


class Employment(Base):
    __tablename__ = "employment"
    __table_args__ = (
        CheckConstraint(
            "contract_modality IN ('SEM_TERMO', 'TERMO_CERTO', 'TERMO_INCERTO', 'OTHER')",
            name="ck_employment_modality",
        ),
        Index("idx_employment_employee", "employee_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=True
    )
    intake_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intake.id"), nullable=True
    )
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    actor_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'TCO'")
    )
    actor_type_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    contract_modality: Mapped[str] = mapped_column(String(32), nullable=False)
    contract_modality_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    work_mode_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    hours_per_week: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    days_per_month: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    percent_work: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    profession_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    workplace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workplace.id"), nullable=True
    )
    tsu_rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    rate_applied_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    rate_applied_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    ss_communicated_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )


class CompensationPeriod(Base):
    __tablename__ = "compensation_period"
    __table_args__ = (
        Index("idx_comp_employment", "employment_id"),
        Index(
            "idx_comp_open",
            "employment_id",
            unique=True,
            postgresql_where=text("period_to IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    employment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employment.id"), nullable=False
    )
    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    base_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )


class EmploymentEvent(Base):
    __tablename__ = "employment_event"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'HIRED', 'TERMINATED', 'REHIRED', 'SALARY_CHANGED', "
            "'MODALITY_CHANGED', 'TSU_RATE_CHANGED', 'LEAVE_STARTED', "
            "'LEAVE_ENDED', 'MISSING_FROM_DECLARATION', 'STATUS_OVERRIDE', "
            "'SOURCE_CONFLICT')",
            name="ck_employment_event_type",
        ),
        CheckConstraint(
            "source IN ('SS_DIFF', 'USER', 'ADMIN', 'HRMS', 'CONTRACT')",
            name="ck_employment_event_source",
        ),
        Index("idx_event_employee", "employee_id", "effective_on"),
        Index("idx_event_company_type", "company_id", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=True
    )
    intake_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intake.id"), nullable=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False
    )
    employment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employment.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_on: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    old_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    new_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    old_modality: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_modality: Mapped[str | None] = mapped_column(String(32), nullable=True)
    old_rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    new_rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    leave_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    initiator: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    old_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ss_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ss_batch.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )


class StoredFile(Base):
    __tablename__ = "stored_file"
    __table_args__ = (
        CheckConstraint(
            "company_id IS NOT NULL OR intake_id IS NOT NULL",
            name="ck_stored_file_scope",
        ),
        CheckConstraint(
            "kind IN ("
            "'SS_EXPORT', 'EMPLOYMENT_CONTRACT', 'CONVERSION_DECLARATION', "
            "'AT_NO_DEBT', 'INVOICE_PDF', 'PROFORMA', 'OTHER'"
            ")",
            name="ck_stored_file_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("company.id"),
        nullable=True,
    )
    intake_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intake.id"),
        nullable=True,
    )
    gcs_path: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_base.id"),
        nullable=True,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)


class EmploymentDocument(Base):
    __tablename__ = "employment_document"
    __table_args__ = (
        CheckConstraint(
            "doc_kind IS NULL OR doc_kind IN ('SEM_TERMO', 'TERMO', 'CONVERSION')",
            name="ck_employment_document_doc_kind",
        ),
        CheckConstraint(
            "matches_ss IN ('UNKNOWN', 'MATCH', 'MISMATCH')",
            name="ck_employment_document_matches_ss",
        ),
        CheckConstraint(
            "review_status IN ('PENDING', 'REVIEWED', 'FAILED')",
            name="ck_employment_document_review_status",
        ),
        Index("idx_employment_document_employee", "employee_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False
    )
    employment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employment.id"), nullable=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stored_file.id"), nullable=False
    )
    doc_kind: Mapped[str | None] = mapped_column(String(24), nullable=True)
    signed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    term_end_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    matches_ss: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'UNKNOWN'")
    )
    review_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'PENDING'")
    )
    review_leftover: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    review_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ops_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
