"""Company monthly SS batches and headcount (KB/03, DEV-835)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps.context import CompanyContext, get_company_context
from app.schemas.ss_batches import HeadcountMonthIn, HeadcountMonthOut, SsBatchOut
from app.services.ss_company import (
    batch_out,
    ingest_and_apply_company_ss,
    list_company_headcount,
    list_company_ss_batches,
    put_user_headcount,
)
from app.services.ss_upload import parse_period_year_month, read_ss_upload_files

router = APIRouter(prefix="/v1", tags=["ss-batches"])


@router.get("/ss-batches", response_model=list[SsBatchOut])
async def get_ss_batches(
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> list[SsBatchOut]:
    rows = await list_company_ss_batches(db, ctx.company.id)
    return [SsBatchOut.model_validate(row) for row in rows]


@router.post(
    "/ss-batches",
    response_model=SsBatchOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_ss_batch(
    files: list[UploadFile] = File(...),
    period_year_month: str = Form(...),
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> SsBatchOut:
    sources = await read_ss_upload_files(files)
    period = parse_period_year_month(period_year_month)
    try:
        result = await ingest_and_apply_company_ss(
            db, ctx, files=sources, period_year_month=period
        )
    except HTTPException:
        await db.commit()
        raise
    await db.commit()
    await db.refresh(result.batch)
    return SsBatchOut.model_validate(await batch_out(db, result.batch))


@router.get("/headcount-months", response_model=list[HeadcountMonthOut])
async def get_headcount_months(
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> list[HeadcountMonthOut]:
    rows = await list_company_headcount(db, ctx.company.id)
    return [HeadcountMonthOut.model_validate(row) for row in rows]


@router.put("/headcount-months", response_model=HeadcountMonthOut)
async def put_headcount_month(
    body: HeadcountMonthIn,
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> HeadcountMonthOut:
    period = parse_period_year_month(body.year_month)
    row = await put_user_headcount(
        db, ctx, year_month=period, headcount=body.headcount
    )
    await db.commit()
    await db.refresh(row)
    return HeadcountMonthOut.model_validate(row)
