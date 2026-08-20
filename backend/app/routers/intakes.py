"""Two-pass intake API (KB/10, DEV-832). OD-1: account-first or session bind."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps.auth import get_current_user, get_optional_current_user
from app.models import Intake, UserBase
from app.schemas.intake import (
    ConvertIntakeIn,
    ConvertIntakeOut,
    IntakeBatchSummary,
    IntakeCreatedOut,
    IntakeOut,
)
from app.services.intake import (
    convert_intake,
    create_intake,
    latest_batch_summary,
    load_intake_or_404,
    purge_intake,
    require_intake_access,
    require_open,
)
from app.services.ss_apply import apply_ss_batch
from app.services.ss_ingest import ingest_ss_export
from app.services.ss_parser import SsSourceFile
from app.settings import HEADER_INTAKE_SESSION

router = APIRouter(prefix="/v1", tags=["intake"])


def _session_header(
    x_intake_session: str | None = Header(default=None, alias=HEADER_INTAKE_SESSION),
) -> str | None:
    return x_intake_session


@router.post("/intakes", response_model=IntakeCreatedOut, status_code=status.HTTP_201_CREATED)
async def post_intake(
    user: UserBase | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> IntakeCreatedOut:
    intake, plaintext = await create_intake(db, user)
    await db.commit()
    await db.refresh(intake)
    return _created_out(intake, plaintext, latest=None)


@router.get("/intakes/{intake_id}", response_model=IntakeOut)
async def get_intake(
    intake_id: uuid.UUID,
    user: UserBase | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
    session_token: str | None = Depends(_session_header),
) -> IntakeOut:
    intake = await load_intake_or_404(db, intake_id)
    require_intake_access(intake, user, session_token)
    latest = await latest_batch_summary(db, intake.id)
    return _intake_out(intake, latest)


@router.post(
    "/intakes/{intake_id}/uploads",
    response_model=IntakeOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_intake_upload(
    intake_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    period_year_month: str = Form(...),
    user: UserBase | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
    session_token: str | None = Depends(_session_header),
) -> IntakeOut:
    intake = await load_intake_or_404(db, intake_id)
    require_intake_access(intake, user, session_token)
    require_open(intake)
    sources = await _read_sources(files)
    period = _parse_period(period_year_month)
    result = await ingest_ss_export(
        db,
        files=sources,
        period_year_month=period,
        intake_id=intake.id,
        uploaded_by=user.id if user is not None else None,
    )
    if result.batch.parse_status == "PARSED":
        await apply_ss_batch(db, result.batch.id)
    await db.commit()
    await db.refresh(intake)
    latest = await latest_batch_summary(db, intake.id)
    return _intake_out(intake, latest)


@router.post("/intakes/{intake_id}/convert", response_model=ConvertIntakeOut)
async def post_intake_convert(
    intake_id: uuid.UUID,
    body: ConvertIntakeIn,
    user: UserBase = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    session_token: str | None = Depends(_session_header),
) -> ConvertIntakeOut:
    intake = await load_intake_or_404(db, intake_id)
    intake, company, role = await convert_intake(
        db,
        intake=intake,
        user=user,
        session_token=session_token,
        legal_name=body.legal_name,
        trading_name=body.trading_name,
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employer NISS already registered to another company.",
        ) from exc
    await db.refresh(intake)
    latest = await latest_batch_summary(db, intake.id)
    out = _intake_out(intake, latest)
    return ConvertIntakeOut(
        **out.model_dump(),
        company_id=company.id,
        membership_role=role,
    )


@router.post("/intakes/{intake_id}/decline", response_model=IntakeOut)
async def post_intake_decline(
    intake_id: uuid.UUID,
    user: UserBase | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
    session_token: str | None = Depends(_session_header),
) -> IntakeOut:
    intake = await load_intake_or_404(db, intake_id)
    require_intake_access(intake, user, session_token)
    await purge_intake(db, intake)
    await db.commit()
    await db.refresh(intake)
    return _intake_out(intake, None)


def _intake_out(
    intake: Intake,
    latest: tuple | None,
) -> IntakeOut:
    summary = None
    if latest is not None:
        batch, vinculo_count, contrato_count = latest
        summary = IntakeBatchSummary(
            id=batch.id,
            parse_status=batch.parse_status,
            parse_error=batch.parse_error,
            vinculo_count=vinculo_count,
            contrato_count=contrato_count,
            period_year_month=batch.period_year_month,
        )
    return IntakeOut(
        id=intake.id,
        status=intake.status,
        user_id=intake.user_id,
        teaser_now_monthly=intake.teaser_now_monthly,
        teaser_now_window=intake.teaser_now_window,
        teaser_potential_monthly=intake.teaser_potential_monthly,
        teaser_potential_window=intake.teaser_potential_window,
        teaser_currency=intake.teaser_currency,
        converted_company_id=intake.converted_company_id,
        latest_batch=summary,
    )


def _created_out(
    intake: Intake, plaintext: str | None, latest: tuple | None
) -> IntakeCreatedOut:
    base = _intake_out(intake, latest)
    return IntakeCreatedOut(**base.model_dump(), session_token=plaintext)


async def _read_sources(files: list[UploadFile]) -> list[SsSourceFile]:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one SS export file is required.",
        )
    sources: list[SsSourceFile] = []
    for item in files:
        content = await item.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )
        sources.append(SsSourceFile(item.filename or "upload.xlsx", content))
    return sources


def _parse_period(raw: str) -> date:
    value = raw.strip()
    try:
        if len(value) == 7 and value[4] == "-":
            parsed = date(int(value[:4]), int(value[5:7]), 1)
        else:
            parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_year_month must be YYYY-MM or YYYY-MM-DD.",
        ) from exc
    if parsed.day != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_year_month must be the first of the month.",
        )
    return parsed
