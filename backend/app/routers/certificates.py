"""Company SS/AT no-debt certificates (DEV-838, KB/05). Admin/Finance/staff."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps.context import CompanyContext, get_company_context
from app.schemas.benefit import CertificateOut
from app.services.benefit_ops import list_certificates, require_admin_or_finance, upload_certificate

router = APIRouter(prefix="/v1", tags=["certificates"])


@router.get("/certificates", response_model=list[CertificateOut])
async def get_certificates(
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> list[CertificateOut]:
    require_admin_or_finance(ctx)
    rows = await list_certificates(db, ctx.company.id)
    return [CertificateOut.model_validate(row) for row in rows]


@router.post(
    "/certificates",
    response_model=CertificateOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_certificate(
    kind: str = Form(...),
    issued_on: date = Form(...),
    file: UploadFile = File(...),
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> CertificateOut:
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )
    cert = await upload_certificate(
        db,
        ctx,
        kind=kind,
        issued_on=issued_on,
        filename=file.filename or "certificate.pdf",
        content=content,
        mime_type=file.content_type,
    )
    await db.commit()
    await db.refresh(cert)
    return CertificateOut.model_validate(cert)
