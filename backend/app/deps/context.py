"""Explicit company / intake request context (KB/40). Never infer a home company."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.deps.auth import get_current_user
from app.models import Company, CompanyMembership, Intake, UserBase
from app.settings import HEADER_COMPANY_ID, HEADER_INTAKE_ID


@dataclass(frozen=True)
class CompanyContext:
    user: UserBase
    company: Company
    membership: CompanyMembership | None
    """None for BeTaxed staff (they are not members)."""


@dataclass(frozen=True)
class IntakeContext:
    user: UserBase
    intake: Intake


def _parse_uuid(raw: str | None, header: str) -> uuid.UUID | None:
    if raw is None or not raw.strip():
        return None
    try:
        return uuid.UUID(raw.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {header} UUID.",
        ) from exc


async def get_company_context(
    user: UserBase = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_company_id: str | None = Header(default=None, alias=HEADER_COMPANY_ID),
) -> CompanyContext:
    company_id = _parse_uuid(x_company_id, HEADER_COMPANY_ID)
    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{HEADER_COMPANY_ID} is required for company-scoped requests.",
        )

    company = await db.get(Company, company_id)
    if company is None or company.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found."
        )

    if user.user_type == "BETAXED_STAFF":
        return CompanyContext(user=user, company=company, membership=None)

    result = await db.execute(
        select(CompanyMembership).where(
            CompanyMembership.user_id == user.id,
            CompanyMembership.company_id == company.id,
            CompanyMembership.is_active.is_(True),
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this company.",
        )
    return CompanyContext(user=user, company=company, membership=membership)


async def get_intake_context(
    user: UserBase = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_intake_id: str | None = Header(default=None, alias=HEADER_INTAKE_ID),
) -> IntakeContext:
    intake_id = _parse_uuid(x_intake_id, HEADER_INTAKE_ID)
    if intake_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{HEADER_INTAKE_ID} is required for intake-scoped requests.",
        )

    result = await db.execute(
        select(Intake)
        .options(selectinload(Intake.user))
        .where(Intake.id == intake_id)
    )
    intake = result.scalar_one_or_none()
    if intake is None or intake.status == "PURGED":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Intake not found."
        )

    if user.user_type == "BETAXED_STAFF":
        return IntakeContext(user=user, intake=intake)

    if intake.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Intake is not bound to this account.",
        )
    if intake.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not the owner of this intake.",
        )
    return IntakeContext(user=user, intake=intake)
