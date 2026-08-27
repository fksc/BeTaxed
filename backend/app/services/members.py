"""Sales-led company create, member invites, seats (DEV-852)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.firebase import (
    create_email_user,
    get_user_by_email,
    set_user_display_name,
    set_user_password,
)
from app.deps.context import CompanyContext
from app.models import Company, CompanyInvite, CompanyMembership, UserBase
from app.security.dek_store import get_or_create_pii_crypto
from app.security.session import hash_session_token, new_session_token
from app.services.billing import seed_commercial_terms
from app.services.domain_events import emit_domain_event
from app.services.mail import InviteMailError, send_invite_email
from app.settings import get_invite_ttl_hours, get_public_app_url

ROLES = frozenset({"ADMIN", "HR", "FINANCE"})
OPEN_INVITE_STATUSES = frozenset({"PENDING", "FAILED", "EXPIRED"})


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def require_company_admin(ctx: CompanyContext) -> None:
    if ctx.user.user_type == "BETAXED_STAFF":
        return
    if ctx.membership is None or ctx.membership.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required.",
        )


def invite_url_for(token: str) -> str:
    return f"{get_public_app_url()}/invite/{token}"


def _effective_status(invite: CompanyInvite, now: datetime) -> str:
    if invite.status in OPEN_INVITE_STATUSES and invite.expires_at <= now:
        return "EXPIRED"
    return invite.status


async def expire_stale_invites(session: AsyncSession, company_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    rows = (
        await session.execute(
            select(CompanyInvite).where(
                CompanyInvite.company_id == company_id,
                CompanyInvite.status.in_(tuple(OPEN_INVITE_STATUSES)),
                CompanyInvite.expires_at <= now,
            )
        )
    ).scalars().all()
    for row in rows:
        row.status = "EXPIRED"


async def seats_used(session: AsyncSession, company_id: uuid.UUID) -> int:
    await expire_stale_invites(session, company_id)
    active = (
        await session.execute(
            select(func.count())
            .select_from(CompanyMembership)
            .where(
                CompanyMembership.company_id == company_id,
                CompanyMembership.is_active.is_(True),
            )
        )
    ).scalar_one()
    open_invites = (
        await session.execute(
            select(func.count())
            .select_from(CompanyInvite)
            .where(
                CompanyInvite.company_id == company_id,
                CompanyInvite.status.in_(tuple(OPEN_INVITE_STATUSES)),
            )
        )
    ).scalar_one()
    return int(active) + int(open_invites)


async def assert_seat_available(session: AsyncSession, company: Company) -> None:
    used = await seats_used(session, company.id)
    if used >= company.max_members:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company seat limit reached.",
        )


def _invite_out(invite: CompanyInvite, *, token: str | None = None) -> dict:
    now = datetime.now(UTC)
    return {
        "id": invite.id,
        "email": invite.email,
        "role": invite.role,
        "status": _effective_status(invite, now),
        "needs_password": invite.needs_password,
        "expires_at": invite.expires_at,
        "sent_at": invite.sent_at,
        "last_error": invite.last_error,
        "created_at": invite.created_at,
        "invite_url": invite_url_for(token) if token else None,
    }


async def _member_rows(session: AsyncSession, company_id: uuid.UUID) -> list[dict]:
    rows = (
        await session.execute(
            select(CompanyMembership, UserBase)
            .join(UserBase, UserBase.id == CompanyMembership.user_id)
            .where(CompanyMembership.company_id == company_id)
            .order_by(CompanyMembership.created_at)
        )
    ).all()
    return [
        {
            "id": membership.id,
            "user_id": membership.user_id,
            "email": user.email,
            "role": membership.role,
            "is_active": membership.is_active,
            "created_at": membership.created_at,
        }
        for membership, user in rows
    ]


async def _invite_rows(
    session: AsyncSession, company_id: uuid.UUID
) -> list[dict]:
    await expire_stale_invites(session, company_id)
    rows = (
        await session.execute(
            select(CompanyInvite)
            .where(CompanyInvite.company_id == company_id)
            .order_by(CompanyInvite.created_at.desc())
        )
    ).scalars().all()
    return [_invite_out(row) for row in rows]


async def members_bundle(session: AsyncSession, company: Company) -> dict:
    used = await seats_used(session, company.id)
    return {
        "max_members": company.max_members,
        "seats_used": used,
        "members": await _member_rows(session, company.id),
        "invites": await _invite_rows(session, company.id),
    }


async def ops_company_list_item(session: AsyncSession, company: Company) -> dict:
    used = await seats_used(session, company.id)
    return {
        "id": company.id,
        "legal_name": company.legal_name,
        "trading_name": company.trading_name,
        "locale": company.locale,
        "status": company.status,
        "max_members": company.max_members,
        "seats_used": used,
        "has_nif": company.nif_enc is not None,
        "created_from_intake_id": company.created_from_intake_id,
        "created_at": company.created_at,
    }


async def list_ops_companies(session: AsyncSession) -> list[dict]:
    rows = (
        await session.execute(
            select(Company)
            .where(Company.deleted_at.is_(None))
            .order_by(Company.created_at.desc())
        )
    ).scalars().all()
    return [await ops_company_list_item(session, row) for row in rows]


async def ops_company_detail(session: AsyncSession, company: Company) -> dict:
    base = await ops_company_list_item(session, company)
    bundle = await members_bundle(session, company)
    base["members"] = bundle["members"]
    base["invites"] = bundle["invites"]
    return base


def _display_name(given_name: str | None, family_name: str | None) -> str | None:
    parts = [p.strip() for p in (given_name, family_name) if p and p.strip()]
    return " ".join(parts) or None


def _mail_copy(
    company: Company,
    role: str,
    url: str,
    locale: str,
    *,
    given_name: str | None = None,
) -> tuple[str, str]:
    greeting_en = f"Hi {given_name.strip()},\n\n" if given_name and given_name.strip() else ""
    greeting_pt = f"Olá {given_name.strip()},\n\n" if given_name and given_name.strip() else ""
    if locale.lower().startswith("en"):
        subject = f"Join {company.legal_name} on BeTaxed"
        body = (
            f"{greeting_en}"
            f"You were invited to {company.legal_name} as {role}.\n\n"
            f"Open this link to set your password and open the workspace:\n{url}\n\n"
            "If you did not expect this, ignore the message.\n"
        )
        return subject, body
    subject = f"Convite BeTaxed — {company.legal_name}"
    body = (
        f"{greeting_pt}"
        f"Foi convidado para {company.legal_name} como {role}.\n\n"
        f"Abra este link para definir a palavra-passe e entrar no espaço de trabalho:\n{url}\n\n"
        "Se não esperava este convite, ignore a mensagem.\n"
    )
    return subject, body


async def _deliver(invite: CompanyInvite, company: Company, token: str) -> str:
    url = invite_url_for(token)
    subject, body = _mail_copy(
        company, invite.role, url, company.locale, given_name=invite.given_name
    )
    try:
        delivery = send_invite_email(to_email=invite.email, subject=subject, body=body)
    except InviteMailError as exc:
        invite.status = "FAILED"
        invite.last_error = str(exc)[:500]
        return "failed"
    invite.status = "PENDING"
    invite.last_error = None
    invite.sent_at = datetime.now(UTC)
    return delivery


async def _ensure_invitee_user(
    session: AsyncSession, email: str, display_name: str | None = None
) -> tuple[UserBase, bool]:
    """Return user_base and whether Firebase still needs a password."""
    existing = (
        await session.execute(select(UserBase).where(UserBase.email == email))
    ).scalar_one_or_none()
    record = get_user_by_email(email)
    if existing is not None:
        needs_password = True
        if record is not None:
            needs_password = not record.has_password
            if display_name:
                set_user_display_name(record.uid, display_name)
        elif existing.last_login_at is not None:
            needs_password = False
        return existing, needs_password

    if record is None:
        record = create_email_user(email, display_name=display_name)
        needs_password = True
    else:
        needs_password = not record.has_password
        if display_name:
            set_user_display_name(record.uid, display_name)

    user = UserBase(
        firebase_uid=record.uid,
        email=email,
        user_type="COMPANY_STAFF",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user, needs_password


async def create_invite(
    session: AsyncSession,
    *,
    company: Company,
    actor: UserBase,
    email: str,
    role: str,
    given_name: str | None = None,
    family_name: str | None = None,
) -> tuple[CompanyInvite, str | None]:
    if role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="role must be ADMIN, HR, or FINANCE.",
        )
    normalized = _normalize_email(email)
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A valid email is required.",
        )

    await expire_stale_invites(session, company.id)

    member = (
        await session.execute(
            select(CompanyMembership)
            .join(UserBase, UserBase.id == CompanyMembership.user_id)
            .where(
                CompanyMembership.company_id == company.id,
                UserBase.email == normalized,
                CompanyMembership.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if member is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email is already a member of this company.",
        )

    open_existing = (
        await session.execute(
            select(CompanyInvite).where(
                CompanyInvite.company_id == company.id,
                CompanyInvite.email == normalized,
                CompanyInvite.status.in_(tuple(OPEN_INVITE_STATUSES)),
            )
        )
    ).scalar_one_or_none()
    if open_existing is not None:
        return await resend_invite(session, invite=open_existing, actor=actor)

    await assert_seat_available(session, company)

    given = given_name.strip() if given_name and given_name.strip() else None
    family = family_name.strip() if family_name and family_name.strip() else None
    user, needs_password = await _ensure_invitee_user(
        session, normalized, display_name=_display_name(given, family)
    )
    if user.user_type == "BETAXED_STAFF":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="BeTaxed staff are not company members.",
        )

    membership = (
        await session.execute(
            select(CompanyMembership).where(
                CompanyMembership.company_id == company.id,
                CompanyMembership.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        membership = CompanyMembership(
            user_id=user.id,
            company_id=company.id,
            role=role,
            is_active=False,
        )
        session.add(membership)
        await session.flush()
    else:
        membership.role = role
        membership.is_active = False

    token = new_session_token()
    now = datetime.now(UTC)
    invite = CompanyInvite(
        company_id=company.id,
        email=normalized,
        given_name=given,
        family_name=family,
        role=role,
        token_hash=hash_session_token(token),
        invited_by_id=actor.id,
        user_id=user.id,
        membership_id=membership.id,
        status="PENDING",
        needs_password=needs_password,
        expires_at=now + timedelta(hours=get_invite_ttl_hours()),
    )
    session.add(invite)
    await session.flush()
    delivery = await _deliver(invite, company, token)
    await emit_domain_event(
        session,
        event_type="COMPANY_MEMBER_INVITED",
        source_entity_type="company_invite",
        source_entity_id=invite.id,
        actor_id=actor.id,
        company_id=company.id,
        payload={"email": normalized, "role": role, "delivery": delivery},
    )
    return invite, invite_url_for(token)


async def resend_invite(
    session: AsyncSession,
    *,
    invite: CompanyInvite,
    actor: UserBase,
) -> tuple[CompanyInvite, str | None]:
    await expire_stale_invites(session, invite.company_id)
    await session.refresh(invite)
    if invite.status in {"ACCEPTED", "CANCELLED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This invite can no longer be resent.",
        )
    company = await session.get(Company, invite.company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
    token = new_session_token()
    invite.token_hash = hash_session_token(token)
    invite.expires_at = datetime.now(UTC) + timedelta(hours=get_invite_ttl_hours())
    invite.invited_by_id = actor.id
    delivery = await _deliver(invite, company, token)
    await emit_domain_event(
        session,
        event_type="COMPANY_MEMBER_INVITED",
        source_entity_type="company_invite",
        source_entity_id=invite.id,
        actor_id=actor.id,
        company_id=company.id,
        payload={"email": invite.email, "role": invite.role, "resent": True, "delivery": delivery},
    )
    return invite, invite_url_for(token)


async def cancel_invite(session: AsyncSession, invite: CompanyInvite) -> CompanyInvite:
    if invite.status in {"ACCEPTED", "CANCELLED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This invite can no longer be cancelled.",
        )
    invite.status = "CANCELLED"
    if invite.membership_id is not None:
        membership = await session.get(CompanyMembership, invite.membership_id)
        if membership is not None and not membership.is_active:
            await session.delete(membership)
            invite.membership_id = None
    return invite


async def get_invite_by_token(
    session: AsyncSession, token: str
) -> CompanyInvite:
    digest = hash_session_token(token)
    matched = (
        await session.execute(
            select(CompanyInvite).where(CompanyInvite.token_hash == digest)
        )
    ).scalar_one_or_none()
    if matched is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found.")
    await expire_stale_invites(session, matched.company_id)
    await session.refresh(matched)
    return matched


async def public_invite(session: AsyncSession, token: str) -> dict:
    invite = await get_invite_by_token(session, token)
    company = await session.get(Company, invite.company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found.")
    now = datetime.now(UTC)
    return {
        "company_name": company.legal_name,
        "email": invite.email,
        "given_name": invite.given_name,
        "family_name": invite.family_name,
        "role": invite.role,
        "status": _effective_status(invite, now),
        "needs_password": invite.needs_password,
        "expires_at": invite.expires_at,
    }


async def accept_invite(
    session: AsyncSession,
    *,
    token: str,
    password: str | None,
    actor: UserBase | None,
) -> CompanyInvite:
    invite = await get_invite_by_token(session, token)
    now = datetime.now(UTC)
    status_now = _effective_status(invite, now)
    if status_now == "EXPIRED":
        invite.status = "EXPIRED"
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This invite has expired. Ask an admin to resend it.",
        )
    if invite.status in {"CANCELLED"}:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This invite was cancelled.",
        )
    if invite.status == "ACCEPTED":
        return invite
    if invite.status == "FAILED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This invite failed to send. Ask an admin to resend it.",
        )

    user = await session.get(UserBase, invite.user_id) if invite.user_id else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invite is missing a user.",
        )

    if invite.needs_password:
        if not password or len(password) < 8:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password must be at least 8 characters.",
            )
        set_user_password(user.firebase_uid, password)
    else:
        if actor is None or actor.email != invite.email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sign in with the invited email to accept.",
            )

    membership = None
    if invite.membership_id is not None:
        membership = await session.get(CompanyMembership, invite.membership_id)
    if membership is None:
        membership = CompanyMembership(
            user_id=user.id,
            company_id=invite.company_id,
            role=invite.role,
            is_active=True,
        )
        session.add(membership)
        await session.flush()
        invite.membership_id = membership.id
    else:
        membership.is_active = True
        membership.role = invite.role

    invite.status = "ACCEPTED"
    invite.accepted_at = now
    invite.last_error = None
    return invite


async def create_sales_company(
    session: AsyncSession,
    *,
    actor: UserBase,
    legal_name: str,
    trading_name: str | None,
    locale: str,
    nif: str | None,
    admin_email: str,
    admin_given_name: str,
    admin_family_name: str,
    admin_role: str,
) -> tuple[Company, CompanyInvite, str | None]:
    name = legal_name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="legal_name is required.",
        )
    role = admin_role.strip().upper() or "ADMIN"
    given = admin_given_name.strip()
    family = admin_family_name.strip()
    if not given or not family:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="admin given name and family name are required.",
        )
    if role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="role must be ADMIN, HR, or FINANCE.",
        )
    company = Company(
        legal_name=name,
        trading_name=trading_name.strip() if trading_name else None,
        locale=(locale or "pt").strip() or "pt",
        max_members=3,
    )
    session.add(company)
    await session.flush()
    if nif and nif.strip():
        crypto = await get_or_create_pii_crypto(session, company_id=company.id)
        company.nif_enc = crypto.encrypt_nif(nif.strip())
    await seed_commercial_terms(session, company.id, datetime.now(UTC).date())
    invite, url = await create_invite(
        session,
        company=company,
        actor=actor,
        email=admin_email,
        role=role,
        given_name=given,
        family_name=family,
    )
    return company, invite, url


async def patch_ops_company(
    session: AsyncSession,
    company: Company,
    *,
    legal_name: str | None,
    trading_name: str | None,
    locale: str | None,
    max_members: int | None,
) -> Company:
    if legal_name is not None:
        name = legal_name.strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="legal_name is required.",
            )
        company.legal_name = name
    if trading_name is not None:
        company.trading_name = trading_name.strip() or None
    if locale is not None:
        company.locale = locale.strip() or company.locale
    if max_members is not None:
        used = await seats_used(session, company.id)
        if max_members < used:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="max_members cannot be below seats already in use.",
            )
        company.max_members = max_members
    return company


async def get_company_or_404(
    session: AsyncSession, company_id: uuid.UUID
) -> Company:
    company = await session.get(Company, company_id)
    if company is None or company.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
    return company


async def get_company_invite(
    session: AsyncSession, company_id: uuid.UUID, invite_id: uuid.UUID
) -> CompanyInvite:
    invite = await session.get(CompanyInvite, invite_id)
    if invite is None or invite.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found.")
    return invite
