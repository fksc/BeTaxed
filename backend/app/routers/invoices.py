"""Company invoice list, certified PDF attach, and SEPA checkout (DEV-839–DEV-842)."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps.context import CompanyContext, get_company_context
from app.schemas.billing import BillingSettingsOut, CheckoutOut, CompanyInvoiceOut
from app.services.billing import (
    attach_legal_invoice,
    attach_proforma,
    collect_stripe_sepa,
    company_invoice_dict,
    list_company_invoices,
    require_finance_or_admin,
    start_sepa_checkout,
)

router = APIRouter(prefix="/v1", tags=["invoices"])


@router.get("/invoices", response_model=list[CompanyInvoiceOut])
async def get_invoices(
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> list[CompanyInvoiceOut]:
    require_finance_or_admin(ctx)
    rows = await list_company_invoices(db, ctx.company.id, staff=False)
    return [CompanyInvoiceOut.model_validate(row) for row in rows]


@router.post("/invoices/{invoice_id}/proforma", response_model=CompanyInvoiceOut)
async def post_proforma(
    invoice_id: uuid.UUID,
    file: UploadFile = File(...),
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> CompanyInvoiceOut:
    require_finance_or_admin(ctx)
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )
    invoice = await attach_proforma(
        db,
        invoice_id,
        ctx.company.id,
        ctx.user.id,
        filename=file.filename or "proforma.pdf",
        content=content,
        mime_type=file.content_type,
    )
    await db.commit()
    await db.refresh(invoice)
    return CompanyInvoiceOut.model_validate(await company_invoice_dict(db, invoice))


@router.post("/invoices/{invoice_id}/legal-pdf", response_model=CompanyInvoiceOut)
async def post_legal_pdf(
    invoice_id: uuid.UUID,
    file: UploadFile = File(...),
    legal_invoice_number: str | None = Form(default=None),
    atcud: str | None = Form(default=None),
    certified_external_id: str | None = Form(default=None),
    due_on: date | None = Form(default=None),
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> CompanyInvoiceOut:
    require_finance_or_admin(ctx)
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )
    invoice = await attach_legal_invoice(
        db,
        invoice_id,
        ctx.company.id,
        ctx.user.id,
        filename=file.filename or "fatura.pdf",
        content=content,
        mime_type=file.content_type,
        legal_invoice_number=legal_invoice_number,
        atcud=atcud,
        certified_external_id=certified_external_id,
        due_on=due_on,
        persist_certified_external_id=ctx.user.user_type == "BETAXED_STAFF",
    )
    await db.commit()
    await db.refresh(invoice)
    return CompanyInvoiceOut.model_validate(await company_invoice_dict(db, invoice))


@router.get("/billing", response_model=BillingSettingsOut)
async def get_billing_settings(
    ctx: CompanyContext = Depends(get_company_context),
) -> BillingSettingsOut:
    require_finance_or_admin(ctx)
    return BillingSettingsOut(
        invoicing_method=ctx.company.invoicing_method,
        has_stripe_customer=ctx.company.stripe_customer_id is not None,
    )


@router.post("/invoices/sepa-checkout", response_model=CheckoutOut)
async def post_sepa_checkout(
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> CheckoutOut:
    require_finance_or_admin(ctx)
    url = await start_sepa_checkout(db, ctx.company)
    await db.commit()
    return CheckoutOut(url=url)


@router.post("/invoices/{invoice_id}/sepa-collect", response_model=CompanyInvoiceOut)
async def post_sepa_collect(
    invoice_id: uuid.UUID,
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> CompanyInvoiceOut:
    require_finance_or_admin(ctx)
    invoice = await collect_stripe_sepa(db, invoice_id, ctx.company.id)
    await db.commit()
    await db.refresh(invoice)
    return CompanyInvoiceOut.model_validate(await company_invoice_dict(db, invoice))
