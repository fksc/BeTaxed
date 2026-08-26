"""Sales-led company create, invites, seats (DEV-852)."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.firebase import FirebaseIdentity, FirebaseUserRecord
from app.db import AsyncSessionLocal, engine
from app.main import app
from app.models import Company, CompanyInvite, CompanyMembership, UserBase
from app.settings import HEADER_COMPANY_ID
from sqlalchemy import select


@pytest.fixture
def db_session():
    return True


def _patch_verify(monkeypatch: pytest.MonkeyPatch) -> dict[str, FirebaseIdentity]:
    identities: dict[str, FirebaseIdentity] = {}

    def fake_verify(token: str) -> FirebaseIdentity:
        if token not in identities:
            raise AssertionError(f"unexpected token {token}")
        return identities[token]

    monkeypatch.setattr("app.deps.auth.verify_id_token", fake_verify)
    return identities


def _identity(
    identities: dict[str, FirebaseIdentity], prefix: str, email: str | None = None
) -> str:
    token = f"{prefix}-{uuid.uuid4().hex[:12]}"
    identities[token] = FirebaseIdentity(
        uid=token, email=email or f"{prefix}-{uuid.uuid4().hex[:8]}@example.test"
    )
    return token


def _patch_invite_externals(monkeypatch: pytest.MonkeyPatch) -> dict:
    users: dict[str, FirebaseUserRecord] = {}
    mail: list[dict] = []

    def get_user(email: str) -> FirebaseUserRecord | None:
        return users.get(email.strip().lower())

    def create_user(email: str) -> FirebaseUserRecord:
        rec = FirebaseUserRecord(
            uid=f"fb-{uuid.uuid4().hex[:12]}",
            email=email.strip().lower(),
            has_password=False,
        )
        users[rec.email] = rec
        return rec

    def set_password(uid: str, password: str) -> None:
        for email, rec in list(users.items()):
            if rec.uid == uid:
                users[email] = FirebaseUserRecord(
                    uid=uid, email=email, has_password=True
                )

    def send_mail(*, to_email: str, subject: str, body: str) -> str:
        mail.append({"to": to_email, "subject": subject, "body": body})
        return "link_only"

    monkeypatch.setattr("app.services.members.get_user_by_email", get_user)
    monkeypatch.setattr("app.services.members.create_email_user", create_user)
    monkeypatch.setattr("app.services.members.set_user_password", set_password)
    monkeypatch.setattr("app.services.members.send_invite_email", send_mail)
    return {"users": users, "mail": mail}


async def _promote_staff(user_id: str) -> None:
    async with AsyncSessionLocal() as session:
        row = await session.get(UserBase, uuid.UUID(user_id))
        assert row is not None
        row.user_type = "BETAXED_STAFF"
        await session.commit()


def test_sales_led_invite_accept_and_seat_limit(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    identities = _patch_verify(monkeypatch)
    ext = _patch_invite_externals(monkeypatch)

    async def body() -> None:
        staff_token = _identity(identities, "staff")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            me = await client.get(
                "/v1/me", headers={"Authorization": f"Bearer {staff_token}"}
            )
            assert me.status_code == 200
            await _promote_staff(me.json()["id"])

            created = await client.post(
                "/v1/ops/companies",
                headers={"Authorization": f"Bearer {staff_token}"},
                json={
                    "legal_name": "Sales Lda",
                    "trading_name": "Sales",
                    "locale": "en",
                    "admin_email": "owner@sales.test",
                    "admin_role": "ADMIN",
                },
            )
            assert created.status_code == 201, created.text
            payload = created.json()
            assert payload["legal_name"] == "Sales Lda"
            assert payload["max_members"] == 3
            assert payload["seats_used"] == 1
            assert payload["invite_url"]
            token = payload["invite_url"].rsplit("/", 1)[-1]
            company_id = payload["id"]
            assert ext["mail"][0]["to"] == "owner@sales.test"

            preview = await client.get(f"/v1/invites/{token}")
            assert preview.status_code == 200
            assert preview.json()["email"] == "owner@sales.test"
            assert preview.json()["needs_password"] is True

            accepted = await client.post(
                f"/v1/invites/{token}/accept",
                json={"password": "long-enough"},
            )
            assert accepted.status_code == 200, accepted.text
            assert accepted.json()["status"] == "ACCEPTED"

            owner_uid = None
            async with AsyncSessionLocal() as session:
                user = (
                    await session.execute(
                        select(UserBase).where(UserBase.email == "owner@sales.test")
                    )
                ).scalar_one()
                owner_uid = user.firebase_uid
            identities[owner_uid] = FirebaseIdentity(
                uid=owner_uid, email="owner@sales.test"
            )
            owner_token = owner_uid

            headers = {
                "Authorization": f"Bearer {owner_token}",
                HEADER_COMPANY_ID: company_id,
            }
            members = await client.get("/v1/members", headers=headers)
            assert members.status_code == 200, members.text
            bundle = members.json()
            assert bundle["seats_used"] == 1
            assert bundle["members"][0]["is_active"] is True
            assert bundle["members"][0]["role"] == "ADMIN"

            for i in range(2):
                invited = await client.post(
                    "/v1/members/invites",
                    headers=headers,
                    json={"email": f"hr{i}@sales.test", "role": "HR"},
                )
                assert invited.status_code == 201, invited.text

            fourth = await client.post(
                "/v1/members/invites",
                headers=headers,
                json={"email": "finance@sales.test", "role": "FINANCE"},
            )
            assert fourth.status_code == 409

            bump = await client.patch(
                f"/v1/ops/companies/{company_id}",
                headers={"Authorization": f"Bearer {staff_token}"},
                json={"max_members": 4},
            )
            assert bump.status_code == 200
            assert bump.json()["max_members"] == 4

            extra = await client.post(
                "/v1/members/invites",
                headers=headers,
                json={"email": "finance@sales.test", "role": "FINANCE"},
            )
            assert extra.status_code == 201, extra.text
            invite_id = extra.json()["id"]
            cancelled = await client.post(
                f"/v1/members/invites/{invite_id}/cancel",
                headers=headers,
            )
            assert cancelled.status_code == 200
            assert cancelled.json()["status"] == "CANCELLED"

    asyncio.run(body())
    engine.sync_engine.dispose()
