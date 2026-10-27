"""Request pipeline. Stages are data. DEV-882, KB/05."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, BYTEA, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PipelineStage(Base):
    __tablename__ = "pipeline_stage"
    __table_args__ = (
        UniqueConstraint("code", name="uq_pipeline_stage_code"),
        CheckConstraint(
            "stage_type IN ('WORK', 'WAIT_CLIENT', 'WAIT_SS', 'CLOSE_WON', 'CLOSE_LOST')",
            name="ck_pipeline_stage_type",
        ),
        CheckConstraint(
            "entry_path IS NULL OR entry_path IN ('FIXED_TERM', 'OPEN_CONTRACT')",
            name="ck_pipeline_stage_entry_path",
        ),
        Index(
            "uq_pipeline_stage_entry_path",
            "entry_path",
            unique=True,
            postgresql_where=text("entry_path IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    stage_type: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_path: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )


class PipelineOperation(Base):
    __tablename__ = "pipeline_operation"
    __table_args__ = (UniqueConstraint("code", name="uq_pipeline_operation_code"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)


class PipelineStageOperation(Base):
    __tablename__ = "pipeline_stage_operation"
    __table_args__ = (
        UniqueConstraint(
            "stage_id", "operation_id", name="uq_pipeline_stage_operation"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_stage.id"), nullable=False
    )
    operation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_operation.id"), nullable=False
    )
    next_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_stage.id"), nullable=True
    )
    next_won_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_stage.id"), nullable=True
    )
    next_lost_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_stage.id"), nullable=True
    )
    next_claim_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_stage.id"), nullable=True
    )


class RejectionReason(Base):
    __tablename__ = "rejection_reason"
    __table_args__ = (UniqueConstraint("code", name="uq_rejection_reason_code"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    blocks_claim: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )


class MinutaTemplate(Base):
    __tablename__ = "minuta_template"
    __table_args__ = (UniqueConstraint("code", name="uq_minuta_template_code"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RequestCase(Base):
    __tablename__ = "request_case"
    __table_args__ = (
        CheckConstraint(
            "path IN ('FIXED_TERM', 'OPEN_CONTRACT')",
            name="ck_request_case_path",
        ),
        Index(
            "uq_request_case_open_employment",
            "employment_id",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
        ),
        Index("idx_request_case_company", "company_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False
    )
    employment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employment.id"), nullable=False
    )
    opened_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_base.id"), nullable=False
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    stage_entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_stage.id"), nullable=False
    )
    stage_stack: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default=text("ARRAY[]::uuid[]"),
    )
    path: Mapped[str] = mapped_column(String(16), nullable=False)
    probation_ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    benefit_starts_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    person_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    person_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    person_nif_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    person_niss_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_signatory_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_nif_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    company_niss_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    contract_started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    converted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    declared_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    signed_place: Mapped[str | None] = mapped_column(String(255), nullable=True)
    applied_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    applied_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_base.id"), nullable=True
    )
    decision_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    rejection_reason_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rejection_reason.id"), nullable=True
    )
    benefit_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("benefit_case.id"), nullable=True
    )
    ss_submission_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ss_status_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class RequestCaseMinuta(Base):
    __tablename__ = "request_case_minuta"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    request_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("request_case.id"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("minuta_template.id"), nullable=False
    )
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RequestCaseFile(Base):
    __tablename__ = "request_case_file"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('SIGNED_MINUTA', 'UNFAVORABLE_NOTICE', 'CLAIM_SUPPORT')",
            name="ck_request_case_file_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=False
    )
    request_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("request_case.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stored_file.id"), nullable=False
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_base.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
