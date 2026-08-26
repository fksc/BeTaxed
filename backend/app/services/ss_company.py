"""Company monthly SS upload, list, and USER headcount (DEV-835, SL-002/SL-003)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps.context import CompanyContext
from app.models import (
    Company,
    CompanyHeadcountMonth,
    EmploymentEvent,
    SsBatch,
)
from app.services.contracts import require_hr_or_admin
from app.services.ss_apply import apply_ss_batch, upsert_user_headcount
from app.services.ss_ingest import SsIngestResult, ingest_ss_export
from app.services.ss_parser import SsSourceFile


_NISS_MISMATCH = "Employer NISS does not match this company."


async def ingest_and_apply_company_ss(
    session: AsyncSession,
    ctx: CompanyContext,
    *,
    files: list[SsSourceFile],
    period_year_month: date,
) -> SsIngestResult:
    require_hr_or_admin(ctx)
    result = await ingest_ss_export(
        session,
        files=files,
        period_year_month=period_year_month,
        company_id=ctx.company.id,
        uploaded_by=ctx.user.id,
    )
    if result.batch.parse_status != "PARSED":
        return result
    _fail_closed_niss(ctx.company, result.batch)
    await apply_ss_batch(session, result.batch.id)
    await session.refresh(result.batch)
    return result


def _fail_closed_niss(company: Company, batch: SsBatch) -> None:
    if company.employer_niss_hash is None:
        return
    if batch.employer_niss_hash == company.employer_niss_hash:
        return
    batch.parse_status = "FAILED"
    batch.parse_error = _NISS_MISMATCH
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=_NISS_MISMATCH,
    )


async def list_company_ss_batches(
    session: AsyncSession, company_id: uuid.UUID
) -> list[dict]:
    batches = (
        (
            await session.execute(
                select(SsBatch)
                .where(SsBatch.company_id == company_id)
                .order_by(
                    SsBatch.period_year_month.desc(), SsBatch.uploaded_at.desc()
                )
            )
        )
        .scalars()
        .all()
    )
    counts = await _event_counts_by_batch(
        session, [batch.id for batch in batches]
    )
    return [
        {
            "id": batch.id,
            "period_year_month": batch.period_year_month,
            "parse_status": batch.parse_status,
            "parse_error": batch.parse_error,
            "uploaded_at": batch.uploaded_at,
            "event_counts": counts.get(batch.id, {}),
        }
        for batch in batches
    ]


async def batch_out(session: AsyncSession, batch: SsBatch) -> dict:
    counts = await _event_counts_by_batch(session, [batch.id])
    return {
        "id": batch.id,
        "period_year_month": batch.period_year_month,
        "parse_status": batch.parse_status,
        "parse_error": batch.parse_error,
        "uploaded_at": batch.uploaded_at,
        "event_counts": counts.get(batch.id, {}),
    }


async def list_company_headcount(
    session: AsyncSession, company_id: uuid.UUID
) -> list[CompanyHeadcountMonth]:
    rows = (
        (
            await session.execute(
                select(CompanyHeadcountMonth)
                .where(CompanyHeadcountMonth.company_id == company_id)
                .order_by(
                    CompanyHeadcountMonth.year_month.desc(),
                    CompanyHeadcountMonth.source,
                )
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def put_user_headcount(
    session: AsyncSession,
    ctx: CompanyContext,
    *,
    year_month: date,
    headcount: int,
) -> CompanyHeadcountMonth:
    require_hr_or_admin(ctx)
    return await upsert_user_headcount(
        session, ctx.company.id, year_month, headcount
    )


async def _event_counts_by_batch(
    session: AsyncSession, batch_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, int]]:
    if not batch_ids:
        return {}
    rows = (
        await session.execute(
            select(
                EmploymentEvent.ss_batch_id,
                EmploymentEvent.event_type,
                func.count(),
            )
            .where(EmploymentEvent.ss_batch_id.in_(batch_ids))
            .group_by(EmploymentEvent.ss_batch_id, EmploymentEvent.event_type)
        )
    ).all()
    out: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
    for batch_id, event_type, count in rows:
        if batch_id is None:
            continue
        out[batch_id][event_type] = int(count)
    return dict(out)
