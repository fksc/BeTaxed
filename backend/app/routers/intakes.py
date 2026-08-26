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
    VerbosePersonOut,
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
from app.services.ss_upload import parse_period_year_month, read_ss_upload_files
from app.services.teaser import compute_verbose_people, persist_intake_teaser
from app.settings import HEADER_INTAKE_SESSION, verbose_people_enabled

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
    return await _created_out(db, intake, plaintext, latest=None)


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
    return await _intake_out(db, intake, latest)


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
    sources = await read_ss_upload_files(files)
    period = parse_period_year_month(period_year_month)
    result = await ingest_ss_export(
        db,
        files=sources,
        period_year_month=period,
        intake_id=intake.id,
        uploaded_by=user.id if user is not None else None,
    )
    if result.batch.parse_status == "PARSED":
        await apply_ss_batch(db, result.batch.id)
        await persist_intake_teaser(
            db, intake.id, result.batch.period_year_month
        )
    await db.commit()
    await db.refresh(intake)
    latest = await latest_batch_summary(db, intake.id)
    return await _intake_out(db, intake, latest)


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
    out = await _intake_out(db, intake, latest)
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
    return await _intake_out(db, intake, None)


async def _intake_out(
    db: AsyncSession,
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
    people = None
    if verbose_people_enabled() and intake.status != "PURGED":
        as_of = summary.period_year_month if summary is not None else date.today()
        rows = await compute_verbose_people(db, intake.id, as_of)
        people = [VerbosePersonOut.model_validate(row, from_attributes=True) for row in rows]
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
        verbose_people=people,
    )


async def _created_out(
    db: AsyncSession,
    intake: Intake,
    plaintext: str | None,
    latest: tuple | None,
) -> IntakeCreatedOut:
    base = await _intake_out(db, intake, latest)
    return IntakeCreatedOut(**base.model_dump(), session_token=plaintext)
