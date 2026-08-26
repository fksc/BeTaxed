from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CompanyInvoiceLineOut(BaseModel):
    description: str
    fee_amount: Decimal


class CompanyInvoiceOut(BaseModel):
    """Customer payload: totals and generic lines. No employee recipe."""

    id: uuid.UUID
    company_id: uuid.UUID
    period_from: date
    period_to: date
    status: str
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    issued_on: date | None
    due_on: date | None
    paid_on: date | None
    legal_invoice_number: str | None
    lines: list[CompanyInvoiceLineOut]


class StaffInvoiceLineOut(BaseModel):
    id: uuid.UUID
    description: str
    fee_amount: Decimal
    saving_amount: Decimal | None
    employee_id: uuid.UUID | None
    benefit_case_id: uuid.UUID | None


class StaffInvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    period_from: date
    period_to: date
    status: str
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    issued_on: date | None
    due_on: date | None
    paid_on: date | None
    legal_invoice_number: str | None
    stripe_invoice_id: str | None
    lines: list[StaffInvoiceLineOut] = Field(default_factory=list)


class DraftInvoiceIn(BaseModel):
    year_month: date


class ResolveInvoiceIn(BaseModel):
    reason: str = Field(min_length=1)


class CommercialTermsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    fee_percent: Decimal
    valid_from: date
    valid_to: date | None


class CommercialTermsIn(BaseModel):
    fee_percent: Decimal
    valid_from: date
    valid_to: date | None = None


class InvoiceStatusEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_status: str | None
    to_status: str
    actor_user_id: uuid.UUID | None
    reason: str | None
    created_at: datetime
