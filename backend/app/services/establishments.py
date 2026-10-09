"""Company establishments — SS ESTABEE, not the vínculo workplace label (DEV-857)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps.context import CompanyContext
from app.models import Establishment
from app.services.members import require_company_admin

_DUPLICATE = "An establishment with this Segurança Social code already exists."
_MISSING = "Establishment not found."
_EMPTY_PATCH = "Nothing to update."


async def list_establishments(
    session: AsyncSession, company_id: uuid.UUID
) -> list[Establishment]:
    rows = (
        (
            await session.execute(
                select(Establishment)
                .where(Establishment.company_id == company_id)
                .order_by(Establishment.ss_code)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def create_establishment(
    session: AsyncSession,
    ctx: CompanyContext,
    *,
    name: str,
    ss_code: str,
) -> Establishment:
    require_company_admin(ctx)
    cleaned = name.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name is required.",
        )
    row = Establishment(
        company_id=ctx.company.id,
        name=cleaned,
        ss_code=ss_code,
        status="OPEN",
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_DUPLICATE,
        ) from exc
    return row


async def update_establishment(
    session: AsyncSession,
    ctx: CompanyContext,
    establishment_id: uuid.UUID,
    *,
    name: str | None,
    status_value: str | None,
) -> Establishment:
    require_company_admin(ctx)
    if name is None and status_value is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_EMPTY_PATCH,
        )
    row = await session.get(Establishment, establishment_id)
    if row is None or row.company_id != ctx.company.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_MISSING,
        )
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Name is required.",
            )
        row.name = cleaned
    if status_value is not None:
        row.status = status_value
    await session.flush()
    return row
