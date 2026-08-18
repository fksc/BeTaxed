"""Current user and explicit tenant context (DEV-829)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import (
    CompanyContext,
    IntakeContext,
    get_company_context,
    get_current_user,
    get_intake_context,
)
from app.models import CompanyMembership, UserBase
from app.schemas import CompanyScopeOut, IntakeScopeOut, MeOut, MembershipOut

router = APIRouter(prefix="/v1", tags=["auth"])


@router.get("/me", response_model=MeOut)
async def me(
    user: UserBase = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeOut:
    result = await db.execute(
        select(CompanyMembership)
        .where(CompanyMembership.user_id == user.id)
        .order_by(CompanyMembership.created_at)
    )
    memberships = result.scalars().all()
    return MeOut(
        id=user.id,
        email=user.email,
        user_type=user.user_type,
        preferred_language=user.preferred_language,
        timezone=user.timezone,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        memberships=[
            MembershipOut(
                company_id=m.company_id, role=m.role, is_active=m.is_active
            )
            for m in memberships
        ],
    )


@router.get("/me/company", response_model=CompanyScopeOut)
async def me_company(ctx: CompanyContext = Depends(get_company_context)) -> CompanyScopeOut:
    role = ctx.membership.role if ctx.membership is not None else None
    actor = "BETAXED_STAFF" if ctx.user.user_type == "BETAXED_STAFF" else "COMPANY_STAFF"
    return CompanyScopeOut(
        company_id=ctx.company.id,
        legal_name=ctx.company.legal_name,
        role=role,
        actor=actor,
    )


@router.get("/me/intake", response_model=IntakeScopeOut)
async def me_intake(ctx: IntakeContext = Depends(get_intake_context)) -> IntakeScopeOut:
    actor = "BETAXED_STAFF" if ctx.user.user_type == "BETAXED_STAFF" else "COMPANY_STAFF"
    return IntakeScopeOut(
        intake_id=ctx.intake.id,
        status=ctx.intake.status,
        actor=actor,
    )
