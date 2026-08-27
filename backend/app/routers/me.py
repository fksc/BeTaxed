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
from app.services.benefit_ops import latest_certificate
from app.services.teaser import company_ss_estimate

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
async def me_company(
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> CompanyScopeOut:
    role = ctx.membership.role if ctx.membership is not None else None
    actor = "BETAXED_STAFF" if ctx.user.user_type == "BETAXED_STAFF" else "COMPANY_STAFF"
    ss_cert = await latest_certificate(db, ctx.company.id, "SS_NO_DEBT")
    at_cert = await latest_certificate(db, ctx.company.id, "AT_NO_DEBT")
    estimate = await company_ss_estimate(db, ctx.company.id)
    figures = estimate.figures
    return CompanyScopeOut(
        company_id=ctx.company.id,
        legal_name=ctx.company.legal_name,
        role=role,
        actor=actor,
        ss_no_debt_valid_until=ss_cert.valid_until if ss_cert else None,
        at_no_debt_valid_until=at_cert.valid_until if at_cert else None,
        estimate_now_monthly=figures.now_monthly if figures else None,
        estimate_now_window=figures.now_window if figures else None,
        estimate_potential_monthly=figures.potential_monthly if figures else None,
        estimate_potential_window=figures.potential_window if figures else None,
        estimate_unconfirmed=estimate.contracts_missing > 0,
        contracts_missing=estimate.contracts_missing,
    )


@router.get("/me/intake", response_model=IntakeScopeOut)
async def me_intake(ctx: IntakeContext = Depends(get_intake_context)) -> IntakeScopeOut:
    actor = "BETAXED_STAFF" if ctx.user.user_type == "BETAXED_STAFF" else "COMPANY_STAFF"
    return IntakeScopeOut(
        intake_id=ctx.intake.id,
        status=ctx.intake.status,
        actor=actor,
    )
