"""DEV seed for BeTaxed ops staff (BETAXED_STAFF)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.auth.firebase import FirebaseUserRecord
from app.db import AsyncSessionLocal
from app.models import UserBase
from app.services import dev_seed
from app.settings import get_firebase_auth_emulator_host


@pytest.fixture
def db_session():
    return True


def test_require_dev_emulator_refuses_non_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "STAGING")
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    get_firebase_auth_emulator_host.cache_clear()
    with pytest.raises(RuntimeError, match="ENV=DEV"):
        dev_seed.require_dev_emulator()


def test_require_dev_emulator_refuses_without_emulator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENV", "DEV")
    monkeypatch.delenv("FIREBASE_AUTH_EMULATOR_HOST", raising=False)
    get_firebase_auth_emulator_host.cache_clear()
    with pytest.raises(RuntimeError, match="FIREBASE_AUTH_EMULATOR_HOST"):
        dev_seed.require_dev_emulator()


def test_seed_betaxed_staff_creates_and_is_idempotent(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENV", "DEV")
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    get_firebase_auth_emulator_host.cache_clear()

    uid = f"seed-{uuid.uuid4().hex[:12]}"
    email = f"ops-{uuid.uuid4().hex[:8]}@betaxed.local"
    monkeypatch.setattr(
        "app.services.dev_seed.ensure_password_user",
        lambda _email, _password: FirebaseUserRecord(
            uid=uid, email=email, has_password=True
        ),
    )

    async def body() -> None:
        first = await dev_seed.seed_betaxed_staff(email, "betaxed-dev")
        assert first.user_type == "BETAXED_STAFF"
        assert first.firebase_uid == uid
        assert first.email == email
        second = await dev_seed.seed_betaxed_staff(email, "betaxed-dev")
        assert second.id == first.id
        async with AsyncSessionLocal() as session:
            rows = (
                await session.execute(select(UserBase).where(UserBase.email == email))
            ).scalars().all()
            assert len(rows) == 1
            await session.delete(rows[0])
            await session.commit()

    import asyncio

    asyncio.run(body())
