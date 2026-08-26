"""DEV + Auth emulator only: seed BeTaxed ops staff (BETAXED_STAFF)."""

from __future__ import annotations

from sqlalchemy import or_, select

from app.auth.firebase import FirebaseUserRecord, ensure_password_user
from app.db import AsyncSessionLocal
from app.models import UserBase
from app.settings import get_env_name, get_firebase_auth_emulator_host

DEFAULT_STAFF_EMAIL = "ops@betaxed.local"
DEFAULT_STAFF_PASSWORD = "betaxed-dev"


def require_dev_emulator() -> None:
    if get_env_name().upper() != "DEV":
        raise RuntimeError("Seed refuses to run unless ENV=DEV.")
    if not get_firebase_auth_emulator_host():
        raise RuntimeError(
            "Seed refuses to run unless FIREBASE_AUTH_EMULATOR_HOST is set."
        )


async def seed_betaxed_staff(email: str, password: str) -> UserBase:
    require_dev_emulator()
    normalized = email.strip().lower()
    if len(password) < 8:
        raise RuntimeError("SEED_STAFF_PASSWORD must be at least 8 characters.")
    record: FirebaseUserRecord = ensure_password_user(normalized, password)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserBase).where(
                or_(
                    UserBase.email == normalized,
                    UserBase.firebase_uid == record.uid,
                )
            )
        )
        user = result.scalars().first()
        if user is None:
            user = UserBase(
                firebase_uid=record.uid,
                email=normalized,
                user_type="BETAXED_STAFF",
            )
            session.add(user)
        else:
            user.firebase_uid = record.uid
            user.email = normalized
            user.user_type = "BETAXED_STAFF"
            user.is_active = True
        await session.commit()
        await session.refresh(user)
        return user
