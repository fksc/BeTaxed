"""Authenticated actor (Firebase → user_base)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.firebase import verify_id_token
from app.db import get_db
from app.models import UserBase

_bearer = HTTPBearer(auto_error=False)


async def _upsert_user_from_token(db: AsyncSession, token: str) -> UserBase:
    identity = verify_id_token(token)
    email = identity.email.strip().lower()

    result = await db.execute(
        select(UserBase).where(UserBase.firebase_uid == identity.uid)
    )
    user = result.scalar_one_or_none()

    if user is None:
        email_taken = await db.execute(
            select(UserBase.id).where(UserBase.email == email)
        )
        if email_taken.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already linked to another account.",
            )
        user = UserBase(
            firebase_uid=identity.uid,
            email=email,
            user_type="COMPANY_STAFF",
        )
        db.add(user)
        await db.flush()

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled.",
        )

    if user.email != email:
        user.email = email

    user.last_login_at = datetime.now(UTC)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already linked to another account.",
        ) from exc
    await db.refresh(user)
    return user


async def get_optional_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> UserBase | None:
    if creds is None or creds.scheme.lower() != "bearer":
        return None
    return await _upsert_user_from_token(db, creds.credentials)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> UserBase:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization Bearer token required.",
        )
    return await _upsert_user_from_token(db, creds.credentials)
