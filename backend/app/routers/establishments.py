"""Company establishments (DEV-857)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps.context import CompanyContext, get_company_context
from app.schemas.establishments import EstablishmentIn, EstablishmentOut, EstablishmentPatch
from app.services.establishments import (
    create_establishment,
    list_establishments,
    update_establishment,
)

router = APIRouter(prefix="/v1", tags=["establishments"])


@router.get("/establishments", response_model=list[EstablishmentOut])
async def get_establishments(
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> list[EstablishmentOut]:
    rows = await list_establishments(db, ctx.company.id)
    return [EstablishmentOut.model_validate(row) for row in rows]


@router.post(
    "/establishments",
    response_model=EstablishmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_establishment(
    body: EstablishmentIn,
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> EstablishmentOut:
    row = await create_establishment(
        db, ctx, name=body.name, ss_code=body.ss_code
    )
    await db.commit()
    await db.refresh(row)
    return EstablishmentOut.model_validate(row)


@router.patch("/establishments/{establishment_id}", response_model=EstablishmentOut)
async def patch_establishment(
    establishment_id: uuid.UUID,
    body: EstablishmentPatch,
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> EstablishmentOut:
    row = await update_establishment(
        db,
        ctx,
        establishment_id,
        name=body.name,
        status_value=body.status,
    )
    await db.commit()
    await db.refresh(row)
    return EstablishmentOut.model_validate(row)
