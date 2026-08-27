"""Employee status override API (DEV-837, SL-005)."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, or_, select

from app.auth.firebase import FirebaseIdentity
from app.db import AsyncSessionLocal, engine
from app.main import app
from app.models import (
    Company,
    CompanyMembership,
    DomainEvent,
    EmploymentEvent,
    Intake,
    Notification,
    SsBatch,
    StoredFile,
    TenantCryptoKey,
    UserBase,
)
from app.services.ss_apply import delete_company_employment_spine, delete_intake_employment_spine
from app.settings import HEADER_COMPANY_ID, HEADER_INTAKE_SESSION
from tests.ss_xlsx_fixtures import EMPLOYER_NISS, combined_workbook


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


def test_status_override_leave_events_conflict_and_finance(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    identities = _patch_verify(monkeypatch)

    async def body() -> None:
        intake_id = None
        company_id = None
        user_id = None
        finance_id = None
        try:
            admin_token = _identity(identities, "ad")
            finance_token = _identity(identities, "fi")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                created = await client.post("/v1/intakes")
                assert created.status_code == 201, created.text
                intake_id = uuid.UUID(created.json()["id"])
                session_token = created.json()["session_token"]

                filename = f"{EMPLOYER_NISS}_vinculos_2026_08_12.xlsx"
                uploaded = await client.post(
                    f"/v1/intakes/{intake_id}/uploads",
                    headers={HEADER_INTAKE_SESSION: session_token},
                    data={"period_year_month": "2026-08"},
                    files={
                        "files": (
                            filename,
                            combined_workbook(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                )
                assert uploaded.status_code == 201, uploaded.text

                converted = await client.post(
                    f"/v1/intakes/{intake_id}/convert",
                    headers={
                        "Authorization": f"Bearer {admin_token}",
                        HEADER_INTAKE_SESSION: session_token,
                    },
                    json={"legal_name": "Status Lda"},
                )
                assert converted.status_code == 200, converted.text
                company_id = uuid.UUID(converted.json()["company_id"])

                me = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {admin_token}"}
                )
                user_id = uuid.UUID(me.json()["id"])

                finance_me = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {finance_token}"}
                )
                finance_id = uuid.UUID(finance_me.json()["id"])
                async with AsyncSessionLocal() as session:
                    session.add(
                        CompanyMembership(
                            user_id=finance_id,
                            company_id=company_id,
                            role="FINANCE",
                        )
                    )
                    await session.commit()

                auth = {
                    "Authorization": f"Bearer {admin_token}",
                    HEADER_COMPANY_ID: str(company_id),
                }
                finance_auth = {
                    "Authorization": f"Bearer {finance_token}",
                    HEADER_COMPANY_ID: str(company_id),
                }

                people = await client.get("/v1/people", headers=auth)
                assert people.status_code == 200, people.text
                rows = people.json()
                assert len(rows) >= 1
                employee_id = rows[0]["id"]
                assert rows[0]["status"] == "ACTIVE"
                assert rows[0]["status_source"] == "SS"
                assert rows[0]["has_source_conflict"] is False
                assert "contract_modality" in rows[0]

                forbidden = await client.patch(
                    f"/v1/people/{employee_id}",
                    headers=finance_auth,
                    json={"status": "ON_LEAVE", "leave_type": "PARENTAL"},
                )
                assert forbidden.status_code == 403

                on_leave = await client.patch(
                    f"/v1/people/{employee_id}",
                    headers=auth,
                    json={"status": "ON_LEAVE", "leave_type": "PARENTAL"},
                )
                assert on_leave.status_code == 200, on_leave.text
                body_json = on_leave.json()
                assert body_json["status"] == "ON_LEAVE"
                assert body_json["status_source"] == "USER"
                assert body_json["leave_type"] == "PARENTAL"
                assert "remaining_months" not in str(body_json)

                same = await client.patch(
                    f"/v1/people/{employee_id}",
                    headers=auth,
                    json={"status": "ON_LEAVE"},
                )
                assert same.status_code == 200

                active = await client.patch(
                    f"/v1/people/{employee_id}",
                    headers=auth,
                    json={"status": "ACTIVE"},
                )
                assert active.status_code == 200
                assert active.json()["status"] == "ACTIVE"

                terminated = await client.patch(
                    f"/v1/people/{employee_id}",
                    headers=auth,
                    json={"status": "TERMINATED"},
                )
                assert terminated.status_code == 200
                assert terminated.json()["status"] == "TERMINATED"

                later = await client.post(
                    "/v1/ss-batches",
                    headers=auth,
                    data={"period_year_month": "2026-09"},
                    files={
                        "files": (
                            f"{EMPLOYER_NISS}_vinculos_2026_09_12.xlsx",
                            combined_workbook(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                )
                assert later.status_code == 201, later.text

                listed = await client.get("/v1/people", headers=auth)
                match = next(row for row in listed.json() if row["id"] == employee_id)
                assert match["status"] == "TERMINATED"
                assert match["status_source"] == "USER"
                assert match["has_source_conflict"] is True

                keep = await client.patch(
                    f"/v1/people/{employee_id}",
                    headers=auth,
                    json={"status": "ON_LEAVE", "leave_type": "SICKNESS"},
                )
                assert keep.status_code == 200
                assert keep.json()["has_source_conflict"] is True
                assert keep.json()["status"] == "ON_LEAVE"

                async with AsyncSessionLocal() as session:
                    events = (
                        await session.execute(
                            select(EmploymentEvent)
                            .where(EmploymentEvent.employee_id == uuid.UUID(employee_id))
                            .order_by(EmploymentEvent.created_at)
                        )
                    ).scalars().all()
                    types = [event.event_type for event in events]
                    assert types.count("STATUS_OVERRIDE") == 4
                    assert "LEAVE_STARTED" in types
                    assert "LEAVE_ENDED" in types
                    assert "SOURCE_CONFLICT" in types
                    leave = next(
                        event for event in events if event.event_type == "LEAVE_STARTED"
                    )
                    assert leave.leave_type == "PARENTAL"
                    assert leave.source == "USER"
                    override = next(
                        event
                        for event in events
                        if event.event_type == "STATUS_OVERRIDE"
                        and event.new_status == "TERMINATED"
                    )
                    assert override.initiator is None
                    assert override.reason is None
                    notes = (
                        await session.execute(
                            select(DomainEvent).where(
                                DomainEvent.company_id == company_id,
                                DomainEvent.event_type == "EMPLOYEE_STATUS_OVERRIDE",
                            )
                        )
                    ).scalars().all()
                    assert notes
        finally:
            async with AsyncSessionLocal() as session:
                if company_id is not None:
                    await session.execute(
                        delete(Notification).where(
                            Notification.domain_event_id.in_(
                                select(DomainEvent.id).where(
                                    DomainEvent.company_id == company_id
                                )
                            )
                        )
                    )
                    await session.execute(
                        delete(DomainEvent).where(DomainEvent.company_id == company_id)
                    )
                    await session.execute(
                        delete(CompanyMembership).where(
                            CompanyMembership.company_id == company_id
                        )
                    )
                    await delete_company_employment_spine(session, company_id)
                    await session.execute(
                        delete(SsBatch).where(SsBatch.company_id == company_id)
                    )
                    if intake_id is not None:
                        await session.execute(
                            delete(SsBatch).where(SsBatch.intake_id == intake_id)
                        )
                    await session.execute(
                        delete(StoredFile).where(
                            or_(
                                StoredFile.company_id == company_id,
                                StoredFile.intake_id == intake_id if intake_id else False,
                            )
                        )
                    )
                    await session.execute(
                        delete(TenantCryptoKey).where(
                            TenantCryptoKey.company_id == company_id
                        )
                    )
                if intake_id is not None:
                    await delete_intake_employment_spine(session, intake_id)
                    await session.execute(
                        delete(TenantCryptoKey).where(
                            TenantCryptoKey.intake_id == intake_id
                        )
                    )
                    intake = await session.get(Intake, intake_id)
                    if intake is not None:
                        intake.converted_company_id = None
                if company_id is not None:
                    company = await session.get(Company, company_id)
                    if company is not None:
                        company.created_from_intake_id = None
                await session.flush()
                if company_id is not None:
                    company = await session.get(Company, company_id)
                    if company is not None:
                        await session.delete(company)
                if intake_id is not None:
                    intake = await session.get(Intake, intake_id)
                    if intake is not None:
                        await session.delete(intake)
                if user_id is not None:
                    user = await session.get(UserBase, user_id)
                    if user is not None:
                        await session.delete(user)
                if finance_id is not None:
                    finance = await session.get(UserBase, finance_id)
                    if finance is not None:
                        await session.delete(finance)
                await session.commit()
            await engine.dispose()

    asyncio.run(body())
