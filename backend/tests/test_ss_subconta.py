"""Staff-only encrypted Segurança Social sub-conta (DEV-858)."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.auth.firebase import FirebaseIdentity, FirebaseUserRecord
from app.db import AsyncSessionLocal, engine
from app.main import app
from app.models import Company, UserBase
from app.settings import HEADER_COMPANY_ID


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


def _patch_invite_externals(monkeypatch: pytest.MonkeyPatch) -> None:
    users: dict[str, FirebaseUserRecord] = {}

    def get_user(email: str) -> FirebaseUserRecord | None:
        return users.get(email.strip().lower())

    def create_user(email: str, display_name: str | None = None) -> FirebaseUserRecord:
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

    monkeypatch.setattr("app.services.members.get_user_by_email", get_user)
    monkeypatch.setattr("app.services.members.create_email_user", create_user)
    monkeypatch.setattr("app.services.members.set_user_password", set_password)
    monkeypatch.setattr("app.services.members.set_user_display_name", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "app.services.members.send_invite_email",
        lambda **_k: "link_only",
    )


async def _promote_staff(user_id: str) -> None:
    async with AsyncSessionLocal() as session:
        row = await session.get(UserBase, uuid.UUID(user_id))
        assert row is not None
        row.user_type = "BETAXED_STAFF"
        await session.commit()


def test_staff_subconta_is_encrypted_and_hidden_from_company(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    identities = _patch_verify(monkeypatch)
    _patch_invite_externals(monkeypatch)
    username = f"sub.conta.{uuid.uuid4().hex[:8]}@firma.pt"
    password = f"p@ss w0rd! {uuid.uuid4().hex}"
    replacement = f"other-secret-{uuid.uuid4().hex}"

    async def body() -> None:
        staff_token = _identity(identities, "staff")
        outsider_token = _identity(identities, "outsider")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            me = await client.get(
                "/v1/me", headers={"Authorization": f"Bearer {staff_token}"}
            )
            assert me.status_code == 200
            await _promote_staff(me.json()["id"])
            outsider = await client.get(
                "/v1/me", headers={"Authorization": f"Bearer {outsider_token}"}
            )
            assert outsider.status_code == 200

            created = await client.post(
                "/v1/ops/companies",
                headers={"Authorization": f"Bearer {staff_token}"},
                json={
                    "legal_name": "Subconta Lda",
                    "locale": "pt",
                    "admin_email": f"owner-{uuid.uuid4().hex[:8]}@subconta.test",
                    "admin_given_name": "Ana",
                    "admin_family_name": "Silva",
                },
            )
            assert created.status_code == 201, created.text
            company_id = created.json()["id"]
            assert created.json()["ss_subconta_username"] is None
            assert created.json()["has_ss_subconta_password"] is False
            assert created.json()["ss_subconta_available_on"] is None
            assert "password" not in created.json()

            missing = await client.patch(
                f"/v1/ops/companies/{company_id}",
                headers={"Authorization": f"Bearer {staff_token}"},
                json={"ss_subconta_username": username},
            )
            assert missing.status_code == 422

            saved = await client.patch(
                f"/v1/ops/companies/{company_id}",
                headers={"Authorization": f"Bearer {staff_token}"},
                json={
                    "ss_subconta_username": username,
                    "ss_subconta_password": password,
                },
            )
            assert saved.status_code == 200, saved.text
            detail = saved.json()
            assert detail["ss_subconta_username"] == username
            assert detail["has_ss_subconta_password"] is True
            assert detail["ss_subconta_available_on"] is None
            assert password not in saved.text
            assert "ss_subconta_password" not in detail

            async with AsyncSessionLocal() as session:
                row = await session.get(Company, uuid.UUID(company_id))
                assert row is not None
                assert row.ss_subconta_username_enc is not None
                assert row.ss_subconta_password_enc is not None
                assert username.encode() not in row.ss_subconta_username_enc
                assert password.encode() not in row.ss_subconta_password_enc
                assert row.ss_subconta_available_on is None

            listed = await client.get(
                "/v1/ops/companies",
                headers={"Authorization": f"Bearer {staff_token}"},
            )
            assert listed.status_code == 200
            assert password not in listed.text
            assert username not in listed.text

            kept = await client.patch(
                f"/v1/ops/companies/{company_id}",
                headers={"Authorization": f"Bearer {staff_token}"},
                json={
                    "ss_subconta_username": username,
                    "ss_subconta_available_on": "2026-11-02",
                },
            )
            assert kept.status_code == 200, kept.text
            assert kept.json()["ss_subconta_available_on"] == "2026-11-02"
            reveal = await client.get(
                f"/v1/ops/companies/{company_id}/ss-subconta",
                headers={"Authorization": f"Bearer {staff_token}"},
            )
            assert reveal.status_code == 200, reveal.text
            assert reveal.headers["cache-control"] == "no-store"
            assert reveal.json() == {"username": username, "password": password}

            changed = await client.patch(
                f"/v1/ops/companies/{company_id}",
                headers={"Authorization": f"Bearer {staff_token}"},
                json={"ss_subconta_password": replacement},
            )
            assert changed.status_code == 200
            assert password not in changed.text
            reveal_new = await client.get(
                f"/v1/ops/companies/{company_id}/ss-subconta",
                headers={"Authorization": f"Bearer {staff_token}"},
            )
            assert reveal_new.json()["password"] == replacement
            assert reveal_new.json()["username"] == username

            token = created.json()["invite_url"].rsplit("/", 1)[-1]
            accepted = await client.post(
                f"/v1/invites/{token}/accept",
                json={"password": "long-enough"},
            )
            assert accepted.status_code == 200, accepted.text
            owner_email = created.json()["invites"][0]["email"]
            async with AsyncSessionLocal() as session:
                owner = (
                    await session.execute(
                        select(UserBase).where(UserBase.email == owner_email)
                    )
                ).scalar_one()
            identities[owner.firebase_uid] = FirebaseIdentity(
                uid=owner.firebase_uid, email=owner_email
            )
            scope = await client.get(
                "/v1/me/company",
                headers={
                    "Authorization": f"Bearer {owner.firebase_uid}",
                    HEADER_COMPANY_ID: company_id,
                },
            )
            assert scope.status_code == 200, scope.text
            assert "ss_subconta" not in scope.text
            assert replacement not in scope.text
            member_reveal = await client.get(
                f"/v1/ops/companies/{company_id}/ss-subconta",
                headers={"Authorization": f"Bearer {owner.firebase_uid}"},
            )
            assert member_reveal.status_code == 403
            assert replacement not in member_reveal.text

            forbidden = await client.get(
                f"/v1/ops/companies/{company_id}/ss-subconta",
                headers={"Authorization": f"Bearer {outsider_token}"},
            )
            assert forbidden.status_code == 403
            assert password not in forbidden.text
            assert replacement not in forbidden.text

            cleared = await client.patch(
                f"/v1/ops/companies/{company_id}",
                headers={"Authorization": f"Bearer {staff_token}"},
                json={"clear_ss_subconta": True},
            )
            assert cleared.status_code == 200, cleared.text
            assert cleared.json()["ss_subconta_username"] is None
            assert cleared.json()["has_ss_subconta_password"] is False
            assert cleared.json()["ss_subconta_available_on"] is None
            empty = await client.get(
                f"/v1/ops/companies/{company_id}/ss-subconta",
                headers={"Authorization": f"Bearer {staff_token}"},
            )
            assert empty.json() == {"username": None, "password": None}

    asyncio.run(body())
    engine.sync_engine.dispose()
