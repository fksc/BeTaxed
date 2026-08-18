"""Firebase auth → user_base and explicit company/intake context (DEV-829)."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.firebase import FirebaseIdentity
from app.db import AsyncSessionLocal, engine
from app.main import app
from app.models import Company, CompanyMembership, Intake, UserBase
from app.settings import HEADER_COMPANY_ID, HEADER_INTAKE_ID


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


def _identity(identities: dict[str, FirebaseIdentity], prefix: str) -> str:
    token = f"{prefix}-{uuid.uuid4().hex[:12]}"
    identities[token] = FirebaseIdentity(
        uid=token, email=f"{prefix}-{uuid.uuid4().hex[:8]}@example.test"
    )
    return token


def test_auth_context_company_and_intake(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    identities = _patch_verify(monkeypatch)

    async def body() -> None:
        try:
            staff_token = _identity(identities, "staff")
            hr_token = _identity(identities, "hr")

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                unauth = await client.get("/v1/me")
                assert unauth.status_code == 401

                created = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {hr_token}"}
                )
                assert created.status_code == 200, created.text
                hr = created.json()
                assert hr["user_type"] == "COMPANY_STAFF"
                assert hr["email"] == identities[hr_token].email
                assert hr["is_active"] is True
                assert hr["memberships"] == []

                staff_me = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {staff_token}"}
                )
                assert staff_me.status_code == 200
                async with AsyncSessionLocal() as session:
                    staff_row = await session.get(
                        UserBase, uuid.UUID(staff_me.json()["id"])
                    )
                    assert staff_row is not None
                    staff_row.user_type = "BETAXED_STAFF"
                    company = Company(legal_name="Acme Lda")
                    other_company = Company(legal_name="Other Lda")
                    session.add(company)
                    session.add(other_company)
                    await session.flush()
                    membership = CompanyMembership(
                        user_id=uuid.UUID(hr["id"]),
                        company_id=company.id,
                        role="HR",
                    )
                    session.add(membership)
                    owned = Intake(user_id=uuid.UUID(hr["id"]), status="OPEN")
                    unbound = Intake(user_id=None, status="OPEN")
                    other = Intake(user_id=staff_row.id, status="OPEN")
                    session.add_all([owned, unbound, other])
                    await session.commit()
                    company_id = str(company.id)
                    other_company_id = str(other_company.id)
                    owned_id = str(owned.id)
                    unbound_id = str(unbound.id)
                    other_id = str(other.id)
                    membership_id = membership.id
                    hr_user_id = uuid.UUID(hr["id"])
                    staff_user_id = staff_row.id

                missing = await client.get(
                    "/v1/me/company",
                    headers={"Authorization": f"Bearer {hr_token}"},
                )
                assert missing.status_code == 400

                bad_uuid = await client.get(
                    "/v1/me/company",
                    headers={
                        "Authorization": f"Bearer {hr_token}",
                        HEADER_COMPANY_ID: "not-a-uuid",
                    },
                )
                assert bad_uuid.status_code == 400

                ok = await client.get(
                    "/v1/me/company",
                    headers={
                        "Authorization": f"Bearer {hr_token}",
                        HEADER_COMPANY_ID: company_id,
                    },
                )
                assert ok.status_code == 200, ok.text
                assert ok.json()["role"] == "HR"
                assert ok.json()["actor"] == "COMPANY_STAFF"

                staff_ok = await client.get(
                    "/v1/me/company",
                    headers={
                        "Authorization": f"Bearer {staff_token}",
                        HEADER_COMPANY_ID: company_id,
                    },
                )
                assert staff_ok.status_code == 200, staff_ok.text
                assert staff_ok.json()["role"] is None
                assert staff_ok.json()["actor"] == "BETAXED_STAFF"

                stranger = await client.get(
                    "/v1/me/company",
                    headers={
                        "Authorization": f"Bearer {hr_token}",
                        HEADER_COMPANY_ID: other_company_id,
                    },
                )
                assert stranger.status_code == 403

                missing_company = await client.get(
                    "/v1/me/company",
                    headers={
                        "Authorization": f"Bearer {hr_token}",
                        HEADER_COMPANY_ID: str(uuid.uuid4()),
                    },
                )
                assert missing_company.status_code == 404

                intake_ok = await client.get(
                    "/v1/me/intake",
                    headers={
                        "Authorization": f"Bearer {hr_token}",
                        HEADER_INTAKE_ID: owned_id,
                    },
                )
                assert intake_ok.status_code == 200, intake_ok.text
                assert intake_ok.json()["status"] == "OPEN"

                intake_unbound = await client.get(
                    "/v1/me/intake",
                    headers={
                        "Authorization": f"Bearer {hr_token}",
                        HEADER_INTAKE_ID: unbound_id,
                    },
                )
                assert intake_unbound.status_code == 403

                intake_other = await client.get(
                    "/v1/me/intake",
                    headers={
                        "Authorization": f"Bearer {hr_token}",
                        HEADER_INTAKE_ID: other_id,
                    },
                )
                assert intake_other.status_code == 403

                staff_intake = await client.get(
                    "/v1/me/intake",
                    headers={
                        "Authorization": f"Bearer {staff_token}",
                        HEADER_INTAKE_ID: unbound_id,
                    },
                )
                assert staff_intake.status_code == 200

                async with AsyncSessionLocal() as session:
                    for model, row_id in (
                        (CompanyMembership, membership_id),
                        (Intake, uuid.UUID(owned_id)),
                        (Intake, uuid.UUID(unbound_id)),
                        (Intake, uuid.UUID(other_id)),
                        (Company, uuid.UUID(company_id)),
                        (Company, uuid.UUID(other_company_id)),
                        (UserBase, hr_user_id),
                        (UserBase, staff_user_id),
                    ):
                        row = await session.get(model, row_id)
                        if row is not None:
                            await session.delete(row)
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(body())


def test_disabled_user_is_forbidden(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    identities = _patch_verify(monkeypatch)

    async def body() -> None:
        try:
            token = _identity(identities, "disabled")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                created = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {token}"}
                )
                assert created.status_code == 200, created.text
                user_id = uuid.UUID(created.json()["id"])

                async with AsyncSessionLocal() as session:
                    row = await session.get(UserBase, user_id)
                    assert row is not None
                    row.is_active = False
                    await session.commit()

                blocked = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {token}"}
                )
                assert blocked.status_code == 403
                assert blocked.json()["detail"] == "Account is disabled."

                async with AsyncSessionLocal() as session:
                    row = await session.get(UserBase, user_id)
                    if row is not None:
                        await session.delete(row)
                        await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(body())


def test_email_conflict_returns_409(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    identities = _patch_verify(monkeypatch)

    async def body() -> None:
        try:
            first = _identity(identities, "first")
            clash = f"clash-{uuid.uuid4().hex[:12]}"
            identities[clash] = FirebaseIdentity(
                uid=clash, email=identities[first].email
            )
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                ok = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {first}"}
                )
                assert ok.status_code == 200, ok.text
                first_id = uuid.UUID(ok.json()["id"])

                conflict = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {clash}"}
                )
                assert conflict.status_code == 409

                async with AsyncSessionLocal() as session:
                    row = await session.get(UserBase, first_id)
                    if row is not None:
                        await session.delete(row)
                        await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(body())
