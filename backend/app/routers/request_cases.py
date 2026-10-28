"""Staff pipeline and company case status. DEV-882, KB/05."""

from __future__ import annotations

import uuid
from urllib.parse import quote

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps.context import CompanyContext, get_company_context
from app.models import MinutaTemplate, RejectionReason, UserBase
from app.routers.ops import require_staff
from sqlalchemy.exc import IntegrityError

from app.schemas.request_case import (
    CaseFactsIn,
    MinutaDraftIn,
    MinutaPreviewIn,
    MinutaTemplateIn,
    MinutaTemplateOut,
    MinutaTemplatePatch,
    MinutaTokenOut,
    OpenRequestCaseIn,
    OperationIn,
    PipelineStageOut,
    RejectionReasonOut,
    RequestCaseOut,
    RequestFileOut,
)
from app.services.contracts import require_hr_or_admin
from app.services.minuta_facts import catalogue
from app.services.minuta_preview import render_minuta_pdf
from app.services.request_pipeline import (
    company_attach_signed_scan,
    list_pipeline,
    list_request_cases,
    open_request_case,
    read_request_file,
    refresh_case_facts,
    run_operation,
    save_case_facts,
    save_minuta_draft,
    sent_minuta_html,
    store_request_file,
)

router = APIRouter(tags=["request-cases"])


@router.get("/v1/ops/pipeline", response_model=list[PipelineStageOut])
async def get_pipeline(
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_pipeline(db)


@router.get(
    "/v1/ops/request-cases",
    response_model=list[RequestCaseOut],
    response_model_exclude_none=True,
)
async def get_ops_request_cases(
    company_id: uuid.UUID | None = Query(default=None),
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_request_cases(db, company_id=company_id, staff=True)


@router.post(
    "/v1/ops/request-cases",
    response_model=RequestCaseOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
async def post_request_case(
    body: OpenRequestCaseIn,
    user: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> dict:
    case = await open_request_case(db, employee_id=body.employee_id, actor=user)
    await db.commit()
    rows = await list_request_cases(db, company_id=case.company_id, staff=True)
    match = next((row for row in rows if row["id"] == case.id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return match


@router.post(
    "/v1/ops/request-cases/{case_id}/operations",
    response_model=RequestCaseOut,
    response_model_exclude_none=True,
)
async def post_operation(
    case_id: uuid.UUID,
    body: OperationIn,
    user: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> dict:
    case = await run_operation(
        db, case_id=case_id, actor=user, code=body.code, payload=body.payload
    )
    await db.commit()
    rows = await list_request_cases(db, company_id=case.company_id, staff=True)
    match = next((row for row in rows if row["id"] == case.id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return match


@router.get("/v1/ops/rejection-reasons", response_model=list[RejectionReasonOut])
async def get_rejection_reasons(
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[RejectionReason]:
    rows = (await db.execute(select(RejectionReason).order_by(RejectionReason.label))).scalars()
    return list(rows.all())


@router.get("/v1/ops/minuta-tokens", response_model=list[MinutaTokenOut])
async def get_minuta_tokens(_: UserBase = Depends(require_staff)) -> list[dict[str, str]]:
    return catalogue()


@router.get("/v1/ops/minuta-templates", response_model=list[MinutaTemplateOut])
async def get_minuta_templates(
    include_inactive: bool = Query(default=False),
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[MinutaTemplate]:
    query = select(MinutaTemplate).order_by(MinutaTemplate.title)
    if not include_inactive:
        query = query.where(MinutaTemplate.is_active.is_(True))
    rows = (await db.execute(query)).scalars()
    return list(rows.all())


@router.post(
    "/v1/ops/minuta-templates",
    response_model=MinutaTemplateOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_minuta_template(
    body: MinutaTemplateIn,
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> MinutaTemplate:
    row = MinutaTemplate(code=body.code.strip(), title=body.title.strip(), body_html=body.body_html)
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A template with that code already exists.")
    await db.refresh(row)
    return row


@router.post("/v1/ops/minuta-templates/preview")
async def preview_minuta_template(
    body: MinutaPreviewIn,
    _: UserBase = Depends(require_staff),
) -> Response:
    pdf = render_minuta_pdf(body.body_html)
    return Response(content=pdf, media_type="application/pdf")


@router.patch("/v1/ops/minuta-templates/{template_id}", response_model=MinutaTemplateOut)
async def patch_minuta_template(
    template_id: uuid.UUID,
    body: MinutaTemplatePatch,
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> MinutaTemplate:
    row = await db.get(MinutaTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Minuta not found.")
    if body.title is not None:
        title = body.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Title is required.")
        row.title = title
    if body.body_html is not None:
        row.body_html = body.body_html
    if body.is_active is not None:
        row.is_active = body.is_active
    row.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return row


async def _staff_case(db: AsyncSession, case_id: uuid.UUID) -> dict:
    from app.models import RequestCase

    case = await db.get(RequestCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    rows = await list_request_cases(db, company_id=case.company_id, staff=True)
    match = next((row for row in rows if row["id"] == case.id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return match


@router.patch(
    "/v1/ops/request-cases/{case_id}/facts",
    response_model=RequestCaseOut,
    response_model_exclude_none=True,
)
async def patch_case_facts(
    case_id: uuid.UUID,
    body: CaseFactsIn,
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await save_case_facts(db, case_id, body.model_dump(exclude_unset=True))
    await db.commit()
    return await _staff_case(db, case_id)


@router.post(
    "/v1/ops/request-cases/{case_id}/refresh-facts",
    response_model=RequestCaseOut,
    response_model_exclude_none=True,
)
async def post_refresh_facts(
    case_id: uuid.UUID,
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await refresh_case_facts(db, case_id)
    await db.commit()
    return await _staff_case(db, case_id)


@router.put(
    "/v1/ops/request-cases/{case_id}/minuta-draft",
    response_model=RequestCaseOut,
    response_model_exclude_none=True,
)
async def put_minuta_draft(
    case_id: uuid.UUID,
    body: MinutaDraftIn,
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await save_minuta_draft(db, case_id, body.body_html)
    await db.commit()
    return await _staff_case(db, case_id)


@router.post(
    "/v1/ops/request-files",
    response_model=RequestFileOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_ops_request_file(
    kind: str = Form(...),
    company_id: uuid.UUID = Form(...),
    request_case_id: uuid.UUID | None = Form(default=None),
    file: UploadFile = File(...),
    user: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> RequestFileOut:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    row = await store_request_file(
        db,
        company_id=company_id,
        actor_id=user.id,
        kind=kind,
        filename=file.filename or "document.pdf",
        content=content,
        mime_type=file.content_type,
        request_case_id=request_case_id,
    )
    await db.commit()
    return RequestFileOut(id=row.id, kind=row.kind, request_case_id=row.request_case_id)


@router.get(
    "/v1/request-cases",
    response_model=list[RequestCaseOut],
    response_model_exclude_none=True,
)
async def get_company_request_cases(
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_request_cases(db, company_id=ctx.company.id, staff=False)


@router.get("/v1/request-cases/{case_id}/minuta")
async def get_sent_minuta(
    case_id: uuid.UUID,
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    html = await sent_minuta_html(db, case_id=case_id, company_id=ctx.company.id)
    return Response(content=html, media_type="text/html")


@router.get("/v1/request-cases/files/{file_id}")
async def get_request_file(
    file_id: uuid.UUID,
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    data, filename, mime_type = await read_request_file(
        db, file_row_id=file_id, company_id=ctx.company.id
    )
    quoted = quote(filename)
    return Response(
        content=data,
        media_type=mime_type or "application/octet-stream",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quoted}"},
    )


@router.post(
    "/v1/request-cases/{case_id}/signed-scan",
    response_model=RequestCaseOut,
    response_model_exclude_none=True,
)
async def post_signed_scan(
    case_id: uuid.UUID,
    file: UploadFile = File(...),
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    require_hr_or_admin(ctx)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    case = await company_attach_signed_scan(
        db,
        case_id=case_id,
        company_id=ctx.company.id,
        actor=ctx.user,
        filename=file.filename or "signed.pdf",
        content=content,
        mime_type=file.content_type,
    )
    await db.commit()
    rows = await list_request_cases(db, company_id=ctx.company.id, staff=False)
    match = next((row for row in rows if row["id"] == case.id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return match


@router.post(
    "/v1/request-cases/signed-scans",
    response_model=list[RequestFileOut],
    status_code=status.HTTP_201_CREATED,
)
async def post_signed_scans(
    files: list[UploadFile] = File(...),
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> list[RequestFileOut]:
    require_hr_or_admin(ctx)
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one file.")
    out: list[RequestFileOut] = []
    for upload in files:
        content = await upload.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        row = await store_request_file(
            db,
            company_id=ctx.company.id,
            actor_id=ctx.user.id,
            kind="SIGNED_MINUTA",
            filename=upload.filename or "signed.pdf",
            content=content,
            mime_type=upload.content_type,
        )
        out.append(RequestFileOut(id=row.id, kind=row.kind, request_case_id=None))
    await db.commit()
    return out
