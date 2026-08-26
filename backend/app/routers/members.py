"""Company members and invites (DEV-852)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import CompanyContext, get_company_context, get_optional_current_user
from app.models import UserBase
from app.schemas.members import (
    InviteAcceptIn,
    InviteOut,
    MemberInviteIn,
    MembersBundleOut,
    PublicInviteOut,
)
from app.services.members import (
    accept_invite,
    cancel_invite,
    create_invite,
    get_company_invite,
    members_bundle,
    public_invite,
    require_company_admin,
    resend_invite,
)

router = APIRouter(prefix="/v1", tags=["members"])


@router.get("/members", response_model=MembersBundleOut)
async def get_members(
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> MembersBundleOut:
    bundle = await members_bundle(db, ctx.company)
    return MembersBundleOut.model_validate(bundle)


@router.post("/members/invites", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
async def post_member_invite(
    body: MemberInviteIn,
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> InviteOut:
    require_company_admin(ctx)
    invite, url = await create_invite(
        db,
        company=ctx.company,
        actor=ctx.user,
        email=body.email,
        role=body.role.strip().upper(),
    )
    await db.commit()
    await db.refresh(invite)
    out = InviteOut.model_validate(invite)
    return out.model_copy(update={"invite_url": url, "status": invite.status})


@router.post("/members/invites/{invite_id}/resend", response_model=InviteOut)
async def post_resend_invite(
    invite_id: uuid.UUID,
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> InviteOut:
    require_company_admin(ctx)
    invite = await get_company_invite(db, ctx.company.id, invite_id)
    invite, url = await resend_invite(db, invite=invite, actor=ctx.user)
    await db.commit()
    await db.refresh(invite)
    out = InviteOut.model_validate(invite)
    return out.model_copy(update={"invite_url": url})


@router.post("/members/invites/{invite_id}/cancel", response_model=InviteOut)
async def post_cancel_invite(
    invite_id: uuid.UUID,
    ctx: CompanyContext = Depends(get_company_context),
    db: AsyncSession = Depends(get_db),
) -> InviteOut:
    require_company_admin(ctx)
    invite = await get_company_invite(db, ctx.company.id, invite_id)
    invite = await cancel_invite(db, invite)
    await db.commit()
    await db.refresh(invite)
    return InviteOut.model_validate(invite)


@router.get("/invites/{token}", response_model=PublicInviteOut)
async def get_public_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> PublicInviteOut:
    row = await public_invite(db, token)
    await db.commit()
    return PublicInviteOut.model_validate(row)


@router.post("/invites/{token}/accept")
async def post_accept_invite(
    token: str,
    body: InviteAcceptIn,
    db: AsyncSession = Depends(get_db),
    actor: UserBase | None = Depends(get_optional_current_user),
) -> dict[str, str]:
    invite = await accept_invite(
        db, token=token, password=body.password, actor=actor
    )
    await db.commit()
    return {
        "status": invite.status,
        "email": invite.email,
        "company_id": str(invite.company_id),
    }
