"""Company people and contract uploads (DEV-836)."""

from __future__ import annotations

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps.context import CompanyContext, get_company_context
from app.schemas.contracts import ContractBatchOut, ContractUploadOut, PersonOut, StatusOverrideIn
from app.services.contract_inbox import upload_contract_batch
from app.services.contracts import (
    list_company_people,
    read_employee_contract,
    upload_employment_contract,
)
from app.services.employee_status import override_employee_status

router = APIRouter(prefix="/v1", tags=["people"])


@router.get("/people", response_model=list[PersonOut], response_model_exclude_none=True)
async def get_people(
    establishment_id: uuid.UUID | None = Query(default=None),
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> list[PersonOut]:
    rows = await list_company_people(db, ctx, establishment_id=establishment_id)
    return [PersonOut.model_validate(row) for row in rows]


@router.patch(
    "/people/{employee_id}",
    response_model=PersonOut,
    response_model_exclude_none=True,
)
async def patch_person_status(
    employee_id: uuid.UUID,
    body: StatusOverrideIn,
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> PersonOut:
    await override_employee_status(
        db,
        ctx,
        employee_id=employee_id,
        status_value=body.status,
        effective_on=body.effective_on,
        leave_type=body.leave_type,
    )
    await db.commit()
    rows = await list_company_people(db, ctx)
    match = next((row for row in rows if row["id"] == employee_id), None)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found."
        )
    return PersonOut.model_validate(match)


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


@router.get("/people/{employee_id}/contracts/{document_id}")
async def get_person_contract_file(
    employee_id: uuid.UUID,
    document_id: uuid.UUID,
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    data, filename, mime_type = await read_employee_contract(
        db,
        ctx,
        employee_id=employee_id,
        document_id=document_id,
    )
    quoted = quote(filename)
    return Response(
        content=data,
        media_type=mime_type or "application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quoted}"},
    )


def _is_pdf(filename: str, content_type: str | None) -> bool:
    name = filename.lower()
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    return name.endswith(".pdf") or mime == "application/pdf"


@router.post(
    "/contracts",
    response_model=ContractBatchOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_contract_batch(
    files: list[UploadFile] = File(...),
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> ContractBatchOut:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Upload at least one PDF."
        )
    payloads: list[tuple[str, bytes, str | None]] = []
    for upload in files:
        filename = upload.filename or "contract.pdf"
        if not _is_pdf(filename, upload.content_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each file must be a PDF.",
            )
        content = await upload.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
            )
        payloads.append((filename, content, upload.content_type))
    rows = await upload_contract_batch(db, ctx, payloads)
    await db.commit()
    names = {row.file_id: name for row, (name, _, _) in zip(rows, payloads, strict=True)}
    return ContractBatchOut(
        items=[
            {
                "inbox_id": row.id,
                "filename": names.get(row.file_id),
                "status": row.status,
                "match_via": row.match_via,
                "employee_id": row.employee_id,
                "document_id": row.employment_document_id,
            }
            for row in rows
        ]
    )
