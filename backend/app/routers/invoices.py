"""Company invoice list (DEV-839). Admin/Finance/staff. No per-employee recipe."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps.context import CompanyContext, get_company_context
from app.schemas.billing import CompanyInvoiceOut
from app.services.billing import list_company_invoices, require_finance_or_admin

router = APIRouter(prefix="/v1", tags=["invoices"])


@router.get("/invoices", response_model=list[CompanyInvoiceOut])
async def get_invoices(
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> list[CompanyInvoiceOut]:
    require_finance_or_admin(ctx)
    rows = await list_company_invoices(db, ctx.company.id, staff=False)
    return [CompanyInvoiceOut.model_validate(row) for row in rows]
