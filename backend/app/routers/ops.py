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
from app.schemas.contracts import MismatchFlagOut
from app.services.benefit_engine import rebuild_company_ledger, submit_company_application
from app.services.benefit_ops import list_ops_benefit_cases
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
