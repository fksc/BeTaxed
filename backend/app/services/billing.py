"""Invoices, commercial_terms, and status ledger (KB/06, DEV-839, DEV-841).

Company serializers omit saving_amount, employee_id, remaining months, and
certified_external_id. Stripe SEPA collection is DEV-842.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps.context import CompanyContext
from app.models import Company, SavingMonth, StoredFile
from app.models.billing import (
    CommercialTerms,
    Invoice,
    InvoiceLine,
    InvoiceStatusEvent,
    Payment,
)
from app.settings import get_default_fee_percent
from app.storage import build_object_name, get_object_storage, sha256_hex


def first_of_month(value: date) -> date:
    return date(value.year, value.month, 1)


def require_finance_or_admin(ctx: CompanyContext) -> None:
    if ctx.user.user_type == "BETAXED_STAFF":
        return
    if ctx.membership is None or ctx.membership.role not in {"ADMIN", "FINANCE"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Finance role required.",
        )


def _default_fee() -> Decimal:
    raw = get_default_fee_percent()
    if not raw:
        return Decimal("0")
    return Decimal(raw)


def month_label(month: date) -> str:
    return f"Success fee — {month.strftime('%b %Y')}"


def last_of_month(value: date) -> date:
    return date(value.year, value.month, calendar.monthrange(value.year, value.month)[1])


async def seed_commercial_terms(
    session: AsyncSession, company_id: uuid.UUID, as_of: date
) -> CommercialTerms:
    existing = (
        await session.execute(
            select(CommercialTerms).where(CommercialTerms.company_id == company_id)
        )
    ).scalars().first()
    if existing is not None:
        return existing
    row = CommercialTerms(
        company_id=company_id,
        fee_percent=_default_fee(),
        valid_from=as_of,
    )
    session.add(row)
    await session.flush()
    return row


async def fee_percent_for(
    session: AsyncSession, company_id: uuid.UUID, as_of: date
) -> Decimal:
    row = (
        await session.execute(
            select(CommercialTerms)
            .where(
                CommercialTerms.company_id == company_id,
                CommercialTerms.valid_from <= as_of,
                or_(
                    CommercialTerms.valid_to.is_(None),
                    CommercialTerms.valid_to >= as_of,
                ),
            )
            .order_by(CommercialTerms.valid_from.desc())
        )
    ).scalars().first()
    if row is None:
        return _default_fee()
    return Decimal(row.fee_percent)


async def add_commercial_terms(
    session: AsyncSession,
    company_id: uuid.UUID,
    *,
    fee_percent: Decimal,
    valid_from: date,
    valid_to: date | None,
) -> CommercialTerms:
    if fee_percent < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="fee_percent must be >= 0.",
        )
    row = CommercialTerms(
        company_id=company_id,
        fee_percent=fee_percent,
        valid_from=valid_from,
        valid_to=valid_to,
    )
    session.add(row)
    await session.flush()
    return row


async def list_commercial_terms(
    session: AsyncSession, company_id: uuid.UUID
) -> list[CommercialTerms]:
    return (
        (
            await session.execute(
                select(CommercialTerms)
                .where(CommercialTerms.company_id == company_id)
                .order_by(CommercialTerms.valid_from.desc())
            )
        )
        .scalars()
        .all()
    )


async def delete_company_billing_spine(
    session: AsyncSession, company_id: uuid.UUID
) -> None:
    invoice_ids = select(Invoice.id).where(Invoice.company_id == company_id)
    line_ids = select(InvoiceLine.id).where(InvoiceLine.invoice_id.in_(invoice_ids))
    await session.execute(
        update(SavingMonth)
        .where(SavingMonth.invoice_line_id.in_(line_ids))
        .values(invoice_line_id=None, locked_at=None)
    )
    await session.execute(
        delete(Payment).where(Payment.invoice_id.in_(invoice_ids))
    )
    await session.execute(
        delete(InvoiceStatusEvent).where(
            InvoiceStatusEvent.invoice_id.in_(invoice_ids)
        )
    )
    await session.execute(
        delete(InvoiceLine).where(InvoiceLine.invoice_id.in_(invoice_ids))
    )
    await session.execute(delete(Invoice).where(Invoice.company_id == company_id))
    await session.execute(
        delete(CommercialTerms).where(CommercialTerms.company_id == company_id)
    )


async def _append_event(
    session: AsyncSession,
    invoice: Invoice,
    to_status: str,
    *,
    actor_id: uuid.UUID | None,
    reason: str | None,
) -> None:
    session.add(
        InvoiceStatusEvent(
            invoice_id=invoice.id,
            from_status=invoice.status,
            to_status=to_status,
            actor_user_id=actor_id,
            reason=reason,
        )
    )
    invoice.status = to_status


def _company_payload(invoice: Invoice, lines: list[InvoiceLine]) -> dict:
    description = lines[0].description if lines else month_label(invoice.period_from)
    return {
        "id": invoice.id,
        "company_id": invoice.company_id,
        "period_from": invoice.period_from,
        "period_to": invoice.period_to,
        "status": invoice.status,
        "currency": invoice.currency,
        "subtotal": invoice.subtotal,
        "tax_amount": invoice.tax_amount,
        "total": invoice.total,
        "issued_on": invoice.issued_on,
        "due_on": invoice.due_on,
        "paid_on": invoice.paid_on,
        "legal_invoice_number": invoice.legal_invoice_number,
        "atcud": invoice.atcud,
        "has_proforma": invoice.proforma_file_id is not None,
        "has_legal_pdf": invoice.legal_invoice_file_id is not None,
        "lines": [{"description": description, "fee_amount": invoice.subtotal}],
    }


def _staff_payload(invoice: Invoice, lines: list[InvoiceLine]) -> dict:
    return {
        "id": invoice.id,
        "company_id": invoice.company_id,
        "period_from": invoice.period_from,
        "period_to": invoice.period_to,
        "status": invoice.status,
        "currency": invoice.currency,
        "subtotal": invoice.subtotal,
        "tax_amount": invoice.tax_amount,
        "total": invoice.total,
        "issued_on": invoice.issued_on,
        "due_on": invoice.due_on,
        "paid_on": invoice.paid_on,
        "legal_invoice_number": invoice.legal_invoice_number,
        "atcud": invoice.atcud,
        "certified_external_id": invoice.certified_external_id,
        "stripe_invoice_id": invoice.stripe_invoice_id,
        "has_proforma": invoice.proforma_file_id is not None,
        "has_legal_pdf": invoice.legal_invoice_file_id is not None,
        "lines": [
            {
                "id": row.id,
                "description": row.description,
                "fee_amount": row.fee_amount,
                "saving_amount": row.saving_amount,
                "employee_id": row.employee_id,
                "benefit_case_id": row.benefit_case_id,
            }
            for row in lines
        ],
    }


async def _lines_for(
    session: AsyncSession, invoice_id: uuid.UUID
) -> list[InvoiceLine]:
    return (
        (
            await session.execute(
                select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id)
            )
        )
        .scalars()
        .all()
    )


async def list_company_invoices(
    session: AsyncSession, company_id: uuid.UUID, *, staff: bool
) -> list[dict]:
    invoices = (
        (
            await session.execute(
                select(Invoice)
                .where(Invoice.company_id == company_id)
                .order_by(Invoice.period_from.desc(), Invoice.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    out: list[dict] = []
    for invoice in invoices:
        lines = await _lines_for(session, invoice.id)
        payload = (
            _staff_payload(invoice, lines) if staff else _company_payload(invoice, lines)
        )
        out.append(payload)
    return out


async def list_all_invoices(session: AsyncSession) -> list[dict]:
    invoices = (
        (
            await session.execute(
                select(Invoice).order_by(Invoice.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    out: list[dict] = []
    for invoice in invoices:
        lines = await _lines_for(session, invoice.id)
        out.append(_staff_payload(invoice, lines))
    return out


async def staff_invoice_dict(session: AsyncSession, invoice: Invoice) -> dict:
    return _staff_payload(invoice, await _lines_for(session, invoice.id))


async def company_invoice_dict(session: AsyncSession, invoice: Invoice) -> dict:
    return _company_payload(invoice, await _lines_for(session, invoice.id))


async def create_draft_invoice(
    session: AsyncSession, company_id: uuid.UUID, year_month: date
) -> Invoice:
    company = await session.get(Company, company_id)
    if company is None or company.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
    month = first_of_month(year_month)
    rows = (
        (
            await session.execute(
                select(SavingMonth)
                .where(
                    SavingMonth.company_id == company_id,
                    SavingMonth.year_month == month,
                    SavingMonth.billable.is_(True),
                    SavingMonth.locked_at.is_(None),
                )
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No unlocked billable saving months for that period.",
        )
    invoice = Invoice(
        company_id=company_id,
        period_from=month,
        period_to=last_of_month(month),
        status="DRAFT",
        currency="EUR",
        tax_amount=Decimal("0"),
    )
    session.add(invoice)
    await session.flush()
    description = month_label(month)
    subtotal = Decimal("0")
    now = datetime.now(UTC)
    for row in rows:
        line = InvoiceLine(
            invoice_id=invoice.id,
            employee_id=row.employee_id,
            benefit_case_id=row.benefit_case_id,
            description=description,
            fee_amount=row.fee_amount,
            saving_amount=row.saving_amount,
        )
        session.add(line)
        await session.flush()
        row.invoice_line_id = line.id
        row.locked_at = now
        subtotal += Decimal(row.fee_amount)
    invoice.subtotal = subtotal
    invoice.total = subtotal
    session.add(
        InvoiceStatusEvent(
            invoice_id=invoice.id,
            from_status=None,
            to_status="DRAFT",
            actor_user_id=None,
            reason="draft",
        )
    )
    await session.flush()
    return invoice


async def issue_invoice(
    session: AsyncSession, invoice_id: uuid.UUID, actor_id: uuid.UUID
) -> Invoice:
    invoice = await session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    if invoice.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only DRAFT invoices can be issued.",
        )
    today = date.today()
    invoice.issued_on = today
    invoice.due_on = today + timedelta(days=30)
    await _append_event(session, invoice, "ISSUED", actor_id=actor_id, reason=None)
    await session.flush()
    return invoice


async def resolve_invoice(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    actor_id: uuid.UUID,
    reason: str,
) -> Invoice:
    invoice = await session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    if invoice.status in {"PAID", "VOID", "MANUALLY_RESOLVED", "CONSOLIDATED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invoice cannot be resolved in its current status.",
        )
    today = date.today()
    invoice.paid_on = today
    company = await session.get(Company, invoice.company_id)
    method = (
        "CERTIFIED"
        if company is not None and company.invoicing_method == "CERTIFIED_SOFTWARE"
        else "MANUAL"
    )
    session.add(
        Payment(
            invoice_id=invoice.id,
            method=method,
            amount=invoice.total,
            paid_at=datetime.now(UTC),
            external_ref=invoice.certified_external_id,
            raw_payload=None,
        )
    )
    await _append_event(
        session, invoice, "MANUALLY_RESOLVED", actor_id=actor_id, reason=reason
    )
    await session.flush()
    return invoice


async def void_invoice(
    session: AsyncSession, invoice_id: uuid.UUID, actor_id: uuid.UUID, reason: str
) -> Invoice:
    invoice = await session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    if invoice.status not in {"DRAFT", "ISSUED", "DUE"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only DRAFT, ISSUED, or DUE invoices can be voided.",
        )
    line_ids = select(InvoiceLine.id).where(InvoiceLine.invoice_id == invoice.id)
    await session.execute(
        update(SavingMonth)
        .where(SavingMonth.invoice_line_id.in_(line_ids))
        .values(invoice_line_id=None, locked_at=None)
    )
    await _append_event(session, invoice, "VOID", actor_id=actor_id, reason=reason)
    await session.flush()
    return invoice


async def apply_stripe_paid(
    session: AsyncSession, stripe_invoice_id: str, payload: dict
) -> Invoice | None:
    invoice = (
        await session.execute(
            select(Invoice).where(Invoice.stripe_invoice_id == stripe_invoice_id)
        )
    ).scalar_one_or_none()
    if invoice is None:
        return None
    if invoice.status == "PAID":
        return invoice
    if invoice.status not in {"ISSUED", "DUE", "LATE"}:
        return None
    invoice.paid_on = date.today()
    session.add(
        Payment(
            invoice_id=invoice.id,
            method="STRIPE_OTHER",
            amount=invoice.total,
            paid_at=datetime.now(UTC),
            external_ref=stripe_invoice_id,
            raw_payload=payload,
        )
    )
    await _append_event(
        session, invoice, "PAID", actor_id=None, reason="stripe_webhook"
    )
    await session.flush()
    return invoice


async def _require_invoice_for_company(
    session: AsyncSession, invoice_id: uuid.UUID, company_id: uuid.UUID
) -> Invoice:
    invoice = await session.get(Invoice, invoice_id)
    if invoice is None or invoice.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    return invoice


async def _store_invoice_pdf(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    actor_id: uuid.UUID,
    filename: str,
    content: bytes,
    mime_type: str | None,
    kind: str,
) -> StoredFile:
    storage = get_object_storage()
    object_name = build_object_name(
        company_id=company_id, intake_id=None, filename=filename
    )
    path = storage.put_bytes(content, object_name=object_name, content_type=mime_type)
    stored = StoredFile(
        company_id=company_id,
        intake_id=None,
        gcs_path=path,
        sha256=sha256_hex(content),
        mime_type=mime_type,
        original_filename=filename,
        kind=kind,
        uploaded_by=actor_id,
    )
    session.add(stored)
    await session.flush()
    return stored


async def attach_proforma(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    company_id: uuid.UUID,
    actor_id: uuid.UUID,
    *,
    filename: str,
    content: bytes,
    mime_type: str | None,
) -> Invoice:
    invoice = await _require_invoice_for_company(session, invoice_id, company_id)
    stored = await _store_invoice_pdf(
        session,
        company_id=company_id,
        actor_id=actor_id,
        filename=filename,
        content=content,
        mime_type=mime_type,
        kind="PROFORMA",
    )
    invoice.proforma_file_id = stored.id
    await session.flush()
    return invoice


async def attach_legal_invoice(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    company_id: uuid.UUID,
    actor_id: uuid.UUID,
    *,
    filename: str,
    content: bytes,
    mime_type: str | None,
    legal_invoice_number: str | None,
    atcud: str | None,
    certified_external_id: str | None,
    due_on: date | None,
    persist_certified_external_id: bool,
) -> Invoice:
    invoice = await _require_invoice_for_company(session, invoice_id, company_id)
    stored = await _store_invoice_pdf(
        session,
        company_id=company_id,
        actor_id=actor_id,
        filename=filename,
        content=content,
        mime_type=mime_type,
        kind="INVOICE_PDF",
    )
    invoice.legal_invoice_file_id = stored.id
    if legal_invoice_number:
        invoice.legal_invoice_number = legal_invoice_number
    if atcud:
        invoice.atcud = atcud
    if persist_certified_external_id and certified_external_id:
        invoice.certified_external_id = certified_external_id
    if due_on is not None:
        invoice.due_on = due_on
    company = await session.get(Company, company_id)
    if company is not None and company.invoicing_method is None:
        company.invoicing_method = "CERTIFIED_SOFTWARE"
    await session.flush()
    return invoice


async def set_invoicing_method(
    session: AsyncSession,
    company_id: uuid.UUID,
    *,
    invoicing_method: str,
    certified_vendor_name: str | None,
) -> Company:
    if invoicing_method not in {"STRIPE_SEPA", "CERTIFIED_SOFTWARE"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invoicing_method must be STRIPE_SEPA or CERTIFIED_SOFTWARE.",
        )
    company = await session.get(Company, company_id)
    if company is None or company.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
    company.invoicing_method = invoicing_method
    company.certified_vendor_name = certified_vendor_name
    await session.flush()
    return company
