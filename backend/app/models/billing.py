"""Commercial terms, invoices, payments (KB/06, DEV-839)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CommercialTerms(Base):
    __tablename__ = "commercial_terms"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "valid_from", name="uq_commercial_terms_company_from"
        ),
        Index("idx_commercial_terms_company", "company_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=False
    )
    fee_percent: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class Invoice(Base):
    __tablename__ = "invoice"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'DRAFT', 'ISSUED', 'DUE', 'LATE', 'PAID', "
            "'CONSOLIDATED', 'VOID', 'MANUALLY_RESOLVED')",
            name="ck_invoice_status",
        ),
        Index("idx_invoice_company_status", "company_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=False
    )
    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'DRAFT'")
    )
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'EUR'")
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    issued_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    consolidates_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoice.id"), nullable=True
    )
    stripe_invoice_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stripe_mandate_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    certified_external_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    legal_invoice_number: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    atcud: Mapped[str | None] = mapped_column(String(64), nullable=True)
    proforma_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stored_file.id"), nullable=True
    )
    legal_invoice_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stored_file.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_line"
    __table_args__ = (Index("idx_invoice_line_invoice", "invoice_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoice.id"), nullable=False
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id"), nullable=True
    )
    benefit_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("benefit_case.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    saving_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )


class Payment(Base):
    __tablename__ = "payment"
    __table_args__ = (
        CheckConstraint(
            "method IN ('STRIPE_SEPA', 'STRIPE_OTHER', 'MANUAL', 'CERTIFIED')",
            name="ck_payment_method",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoice.id"), nullable=False
    )
    method: Mapped[str] = mapped_column(String(24), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InvoiceStatusEvent(Base):
    __tablename__ = "invoice_status_event"
    __table_args__ = (
        Index("idx_invoice_status_event_invoice", "invoice_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoice.id"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    to_status: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_base.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
