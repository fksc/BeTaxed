"""SS declaration ingest: batch, files, raw sheets (KB/03, DEV-831)."""

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
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SsBatch(Base):
    __tablename__ = "ss_batch"
    __table_args__ = (
        CheckConstraint(
            "company_id IS NOT NULL OR intake_id IS NOT NULL",
            name="ck_ss_batch_scope",
        ),
        CheckConstraint(
            "parse_status IN ('PENDING', 'PARSED', 'FAILED', 'APPLIED', 'DISCARDED')",
            name="ck_ss_batch_parse_status",
        ),
        CheckConstraint(
            "EXTRACT(DAY FROM period_year_month) = 1",
            name="ck_ss_batch_period_first_of_month",
        ),
        Index("idx_ss_batch_company_period", "company_id", "period_year_month"),
        Index("idx_ss_batch_intake", "intake_id"),
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
    period_year_month: Mapped[date] = mapped_column(Date, nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_base.id"),
        nullable=True,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    employer_niss_hash: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    employer_niss_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    parse_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'PENDING'")
    )
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    export_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    leave_declared: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    files: Mapped[list[SsBatchFile]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )
    vinculos: Mapped[list[SsRawVinculo]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )
    contratos: Mapped[list[SsRawContrato]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )
    leaves: Mapped[list[SsRawLeave]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class SsBatchFile(Base):
    __tablename__ = "ss_batch_file"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('COMBINED_XLSX', 'VINCULOS', 'CONTRATOS', 'REMUNERACOES', 'OTHER')",
            name="ck_ss_batch_file_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ss_batch.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stored_file.id"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)

    batch: Mapped[SsBatch] = relationship(back_populates="files")


class SsRawVinculo(Base):
    __tablename__ = "ss_raw_vinculo"
    __table_args__ = (
        Index("idx_ss_raw_vinculo_batch_niss", "batch_id", "niss_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ss_batch.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    niss_hash: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    niss_enc: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    name_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    dob_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    vinculo_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    communicated_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    rate_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    rate_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    taxa_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    workplace_ss_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    leftover: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    batch: Mapped[SsBatch] = relationship(back_populates="vinculos")


class SsRawContrato(Base):
    __tablename__ = "ss_raw_contrato"
    __table_args__ = (
        Index("idx_ss_raw_contrato_batch_niss", "batch_id", "niss_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ss_batch.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    niss_hash: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    niss_enc: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    name_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    modality_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_mode_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    contract_started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    profession_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    percent_work: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    hours_work: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    days_work: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    motivo_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    rendimento_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    rendimento_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    base_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    leftover: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    batch: Mapped[SsBatch] = relationship(back_populates="contratos")


class SsRawLeave(Base):
    """BeTaxed remunerações leave sheet. Not official SS DR headers (KB/03)."""

    __tablename__ = "ss_raw_leave"
    __table_args__ = (
        CheckConstraint(
            "leave_type IN ('PARENTAL', 'SICKNESS', 'UNPAID', 'OTHER')",
            name="ck_ss_raw_leave_type",
        ),
        Index("idx_ss_raw_leave_batch_niss", "batch_id", "niss_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ss_batch.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    niss_hash: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    niss_enc: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    leave_type: Mapped[str] = mapped_column(String(24), nullable=False)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    leftover: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    batch: Mapped[SsBatch] = relationship(back_populates="leaves")


class CompanyHeadcountMonth(Base):
    __tablename__ = "company_headcount_month"
    __table_args__ = (
        CheckConstraint(
            "source IN ('SS_BATCH', 'USER')",
            name="ck_company_headcount_month_source",
        ),
        CheckConstraint(
            "EXTRACT(DAY FROM year_month) = 1",
            name="ck_company_headcount_month_first_of_month",
        ),
        CheckConstraint(
            "headcount >= 0",
            name="ck_company_headcount_month_nonneg",
        ),
        UniqueConstraint(
            "company_id",
            "year_month",
            "source",
            name="uq_company_headcount_month_company_year_source",
        ),
        Index("idx_company_headcount_month_company", "company_id", "year_month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("company.id"),
        nullable=False,
    )
    year_month: Mapped[date] = mapped_column(Date, nullable=False)
    headcount: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    source_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ss_batch.id", ondelete="SET NULL"),
        nullable=True,
    )
