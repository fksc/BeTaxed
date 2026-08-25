"""Company people and contract uploads (DEV-836)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps.context import CompanyContext, get_company_context
from app.schemas.contracts import ContractUploadOut, PersonOut
from app.services.contracts import list_company_people, upload_employment_contract

router = APIRouter(prefix="/v1", tags=["people"])


@router.get("/people", response_model=list[PersonOut])
async def get_people(
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> list[PersonOut]:
    rows = await list_company_people(db, ctx)
    return [PersonOut.model_validate(row) for row in rows]


@router.post(
    "/people/{employee_id}/contracts",
    response_model=ContractUploadOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_person_contract(
    employee_id: uuid.UUID,
    file: UploadFile = File(...),
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> ContractUploadOut:
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )
    doc = await upload_employment_contract(
        db,
        ctx,
        employee_id=employee_id,
        filename=file.filename or "contract.pdf",
        content=content,
        mime_type=file.content_type,
    )
    await db.commit()
    await db.refresh(doc)
    staff = ctx.user.user_type == "BETAXED_STAFF"
    review_status = doc.review_status
    if not staff and doc.matches_ss == "MISMATCH":
        review_status = "REVIEWED"
    return ContractUploadOut(
        id=doc.id,
        employee_id=doc.employee_id,
        employment_id=doc.employment_id,
        review_status=review_status,
        matches_ss=doc.matches_ss if staff else None,
    )
