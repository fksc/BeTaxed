"""BeTaxed staff ops APIs (DEV-836)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps.auth import get_current_user
from app.models import UserBase
from app.schemas.contracts import MismatchFlagOut
from app.services.contracts import apply_contract_to_employment, list_mismatch_flags

router = APIRouter(prefix="/v1/ops", tags=["ops"])


async def require_staff(user: UserBase = Depends(get_current_user)) -> UserBase:
    if user.user_type != "BETAXED_STAFF":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff only.")
    return user


@router.get("/contract-flags", response_model=list[MismatchFlagOut])
async def get_contract_flags(
    _: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[MismatchFlagOut]:
    rows = await list_mismatch_flags(db)
    return [MismatchFlagOut.model_validate(row) for row in rows]


@router.post("/employment-documents/{document_id}/apply")
async def post_apply_contract(
    document_id: uuid.UUID,
    user: UserBase = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await apply_contract_to_employment(db, document_id=document_id, actor_id=user.id)
    await db.commit()
    return {"status": "ok"}
