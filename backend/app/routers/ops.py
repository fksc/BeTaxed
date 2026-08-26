"""BeTaxed staff ops APIs (DEV-836, DEV-838)."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps.auth import get_current_user
from app.models import UserBase
from app.schemas.benefit import BenefitCaseOut, CompanyApplicationOut
from app.schemas.billing import (
    CommercialTermsIn,
    CommercialTermsOut,
    DraftInvoiceIn,
    InvoicingMethodIn,
    ResolveInvoiceIn,
    StaffInvoiceOut,
)
from app.schemas.contracts import MismatchFlagOut
from app.services.benefit_engine import rebuild_company_ledger, submit_company_application
from app.services.benefit_ops import list_ops_benefit_cases
from app.services.billing import (
    add_commercial_terms,
    collect_stripe_sepa,
    create_draft_invoice,
    issue_invoice,
    list_all_invoices,
    list_commercial_terms,
    resolve_invoice,
    set_invoicing_method,
    staff_invoice_dict,
    void_invoice,
)
from app.services.contracts import apply_contract_to_employment, list_mismatch_flags

router = APIRouter(prefix="/v1/ops", tags=["ops"])


async def require_staff(user: UserBase = Depends(get_current_user)) -> UserBase:
    if user.user_type != "BETAXED_STAFF":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff only.")
    return user


@router.get("/contract-flags", response_model=list[MismatchFlagOut])
async def get_contract_flags(
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[MismatchFlagOut]:
    rows = await list_mismatch_flags(db)
    return [MismatchFlagOut.model_validate(row) for row in rows]


@router.post("/employment-documents/{document_id}/apply")
async def post_apply_contract(
    document_id: uuid.UUID,
    user: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await apply_contract_to_employment(db, document_id=document_id, actor_id=user.id)
    await db.commit()
    return {"status": "ok"}


@router.get("/benefit-cases", response_model=list[BenefitCaseOut])
async def get_benefit_cases(
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
    as_of: date | None = Query(default=None),
) -> list[BenefitCaseOut]:
    when = as_of or date.today()
    rows = await list_ops_benefit_cases(db, when)
    return [BenefitCaseOut.model_validate(row) for row in rows]


@router.post("/companies/{company_id}/benefit-rebuild", response_model=list[BenefitCaseOut])
async def post_rebuild_benefit(
    company_id: uuid.UUID,
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
    as_of: date | None = Query(default=None),
) -> list[BenefitCaseOut]:
    when = as_of or date.today()
    await rebuild_company_ledger(db, company_id, when)
    await db.commit()
    rows = [
        row
        for row in await list_ops_benefit_cases(db, when)
        if row["company_id"] == company_id
    ]
    return [BenefitCaseOut.model_validate(row) for row in rows]


@router.post(
    "/companies/{company_id}/applications",
    response_model=CompanyApplicationOut,
)
async def post_company_application(
    company_id: uuid.UUID,
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
    as_of: date | None = Query(default=None),
) -> CompanyApplicationOut:
    when = as_of or date.today()
    await rebuild_company_ledger(db, company_id, when)
    app = await submit_company_application(db, company_id, when)
    await db.commit()
    await db.refresh(app)
    return CompanyApplicationOut.model_validate(app)


@router.get("/invoices", response_model=list[StaffInvoiceOut])
async def get_ops_invoices(
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[StaffInvoiceOut]:
    rows = await list_all_invoices(db)
    return [StaffInvoiceOut.model_validate(row) for row in rows]


@router.post(
    "/companies/{company_id}/invoices",
    response_model=StaffInvoiceOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_draft_invoice(
    company_id: uuid.UUID,
    body: DraftInvoiceIn,
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> StaffInvoiceOut:
    invoice = await create_draft_invoice(db, company_id, body.year_month)
    await db.commit()
    await db.refresh(invoice)
    return StaffInvoiceOut.model_validate(await staff_invoice_dict(db, invoice))


@router.post("/invoices/{invoice_id}/issue", response_model=StaffInvoiceOut)
async def post_issue_invoice(
    invoice_id: uuid.UUID,
    user: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> StaffInvoiceOut:
    invoice = await issue_invoice(db, invoice_id, user.id)
    await db.commit()
    await db.refresh(invoice)
    return StaffInvoiceOut.model_validate(await staff_invoice_dict(db, invoice))


@router.post("/invoices/{invoice_id}/resolve", response_model=StaffInvoiceOut)
async def post_resolve_invoice(
    invoice_id: uuid.UUID,
    body: ResolveInvoiceIn,
    user: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> StaffInvoiceOut:
    invoice = await resolve_invoice(db, invoice_id, user.id, body.reason)
    await db.commit()
    await db.refresh(invoice)
    return StaffInvoiceOut.model_validate(await staff_invoice_dict(db, invoice))


@router.post("/invoices/{invoice_id}/void", response_model=StaffInvoiceOut)
async def post_void_invoice(
    invoice_id: uuid.UUID,
    body: ResolveInvoiceIn,
    user: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> StaffInvoiceOut:
    invoice = await void_invoice(db, invoice_id, user.id, body.reason)
    await db.commit()
    await db.refresh(invoice)
    return StaffInvoiceOut.model_validate(await staff_invoice_dict(db, invoice))


@router.post("/invoices/{invoice_id}/collect", response_model=StaffInvoiceOut)
async def post_collect_invoice(
    invoice_id: uuid.UUID,
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> StaffInvoiceOut:
    invoice = await collect_stripe_sepa(db, invoice_id)
    await db.commit()
    await db.refresh(invoice)
    return StaffInvoiceOut.model_validate(await staff_invoice_dict(db, invoice))


@router.get(
    "/companies/{company_id}/commercial-terms",
    response_model=list[CommercialTermsOut],
)
async def get_commercial_terms(
    company_id: uuid.UUID,
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[CommercialTermsOut]:
    rows = await list_commercial_terms(db, company_id)
    return [CommercialTermsOut.model_validate(row) for row in rows]


@router.post(
    "/companies/{company_id}/commercial-terms",
    response_model=CommercialTermsOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_commercial_terms(
    company_id: uuid.UUID,
    body: CommercialTermsIn,
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> CommercialTermsOut:
    row = await add_commercial_terms(
        db,
        company_id,
        fee_percent=body.fee_percent,
        valid_from=body.valid_from,
        valid_to=body.valid_to,
    )
    await db.commit()
    await db.refresh(row)
    return CommercialTermsOut.model_validate(row)


@router.post("/companies/{company_id}/invoicing")
async def post_invoicing_method(
    company_id: uuid.UUID,
    body: InvoicingMethodIn,
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str | None]:
    company = await set_invoicing_method(
        db,
        company_id,
        invoicing_method=body.invoicing_method,
        certified_vendor_name=body.certified_vendor_name,
        update_vendor_name="certified_vendor_name" in body.model_fields_set,
    )
    await db.commit()
    return {
        "invoicing_method": company.invoicing_method,
        "certified_vendor_name": company.certified_vendor_name,
    }
