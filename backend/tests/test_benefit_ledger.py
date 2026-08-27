"""Internal benefit cases, leave months, and certificates (DEV-838)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date

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
    Intake,
    Notification,
    SavingMonth,
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


def test_benefit_cases_ops_only_leave_months_and_certs(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    identities = _patch_verify(monkeypatch)

    async def body() -> None:
        intake_id = None
        company_id = None
        user_id = None
        finance_id = None
        hr_id = None
        staff_id = None
        try:
            admin_token = _identity(identities, "ad")
            finance_token = _identity(identities, "fi")
            hr_token = _identity(identities, "hr")
            staff_token = _identity(identities, "st")
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
                    json={"legal_name": "Benefit Lda"},
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
                hr_me = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {hr_token}"}
                )
                hr_id = uuid.UUID(hr_me.json()["id"])
                staff_me = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {staff_token}"}
                )
                staff_id = uuid.UUID(staff_me.json()["id"])
                async with AsyncSessionLocal() as session:
                    intake = await session.get(Intake, intake_id)
                    assert intake is not None
                    assert intake.teaser_regime_id is not None
                    session.add(
                        CompanyMembership(
                            user_id=finance_id,
                            company_id=company_id,
                            role="FINANCE",
                        )
                    )
                    session.add(
                        CompanyMembership(
                            user_id=hr_id,
                            company_id=company_id,
                            role="HR",
                        )
                    )
                    staff = await session.get(UserBase, staff_id)
                    assert staff is not None
                    staff.user_type = "BETAXED_STAFF"
                    await session.commit()

                auth = {
                    "Authorization": f"Bearer {admin_token}",
                    HEADER_COMPANY_ID: str(company_id),
                }
                finance_auth = {
                    "Authorization": f"Bearer {finance_token}",
                    HEADER_COMPANY_ID: str(company_id),
                }
                hr_auth = {
                    "Authorization": f"Bearer {hr_token}",
                    HEADER_COMPANY_ID: str(company_id),
                }
                staff_headers = {"Authorization": f"Bearer {staff_token}"}

                forbidden_ops = await client.get(
                    "/v1/ops/benefit-cases",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert forbidden_ops.status_code == 403

                people = await client.get("/v1/people", headers=auth)
                assert people.status_code == 200, people.text
                blob = str(people.json())
                assert "remaining_months" not in blob
                assert "monthly_saving" not in blob
                assert "saving_amount" not in blob
                assert "employer_rate" not in blob
                employee_id = people.json()[0]["id"]

                listed = await client.get(
                    "/v1/ops/benefit-cases?as_of=2026-08-26",
                    headers=staff_headers,
                )
                assert listed.status_code == 200, listed.text
                ours = [
                    row
                    for row in listed.json()
                    if row["company_id"] == str(company_id)
                ]
                assert ours
                assert any(row["state"] == "DETECTED" for row in ours)
                assert any(row.get("remaining_months") is not None for row in ours)

                on_leave = await client.patch(
                    f"/v1/people/{employee_id}",
                    headers=auth,
                    json={
                        "status": "ON_LEAVE",
                        "leave_type": "PARENTAL",
                        "effective_on": "2027-03-01",
                    },
                )
                assert on_leave.status_code == 200, on_leave.text

                rebuilt = await client.post(
                    f"/v1/ops/companies/{company_id}/benefit-rebuild"
                    "?as_of=2026-08-26",
                    headers=staff_headers,
                )
                assert rebuilt.status_code == 200, rebuilt.text

                async with AsyncSessionLocal() as session:
                    months = (
                        (
                            await session.execute(
                                select(SavingMonth).where(
                                    SavingMonth.employee_id == uuid.UUID(employee_id)
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )
                    assert months
                    before = [
                        row for row in months if row.year_month < date(2027, 3, 1)
                    ]
                    leave_months = [
                        row for row in months if row.year_month >= date(2027, 3, 1)
                    ]
                    assert before
                    assert leave_months
                    assert all(row.billable for row in before)
                    assert all(not row.billable for row in leave_months)

                hr_upload = await client.post(
                    "/v1/certificates",
                    headers=hr_auth,
                    data={"kind": "SS_NO_DEBT", "issued_on": "2026-01-15"},
                    files={
                        "file": ("ss.pdf", b"%PDF-1.4 ss", "application/pdf")
                    },
                )
                assert hr_upload.status_code == 403
                hr_list = await client.get("/v1/certificates", headers=hr_auth)
                assert hr_list.status_code == 403

                ss_cert = await client.post(
                    "/v1/certificates",
                    headers=auth,
                    data={"kind": "SS_NO_DEBT", "issued_on": "2026-01-15"},
                    files={
                        "file": ("ss.pdf", b"%PDF-1.4 ss", "application/pdf")
                    },
                )
                assert ss_cert.status_code == 201, ss_cert.text
                assert ss_cert.json()["valid_until"] == "2026-05-15"
                assert ss_cert.json()["valid_until_overridden"] is False

                at_cert = await client.post(
                    "/v1/certificates",
                    headers=finance_auth,
                    data={"kind": "AT_NO_DEBT", "issued_on": "2026-01-15"},
                    files={
                        "file": ("at.pdf", b"%PDF-1.4 at", "application/pdf")
                    },
                )
                assert at_cert.status_code == 201, at_cert.text

                hr_scope = await client.get("/v1/me/company", headers=hr_auth)
                assert hr_scope.status_code == 200, hr_scope.text
                assert hr_scope.json()["ss_no_debt_valid_until"] == "2026-05-15"
                assert hr_scope.json()["at_no_debt_valid_until"] == "2026-05-15"

                submitted = await client.post(
                    f"/v1/ops/companies/{company_id}/applications"
                    "?as_of=2026-08-26",
                    headers=staff_headers,
                )
                assert submitted.status_code == 200, submitted.text
                snap = submitted.json()
                assert snap["decision"] == "SUBMITTED"
                assert snap["headcount_current"] == 2
                assert snap["headcount_test_pass"] is False
                assert snap["ss_regularized_at_submit"] is False
                again = await client.post(
                    f"/v1/ops/companies/{company_id}/applications"
                    "?as_of=2026-08-26",
                    headers=staff_headers,
                )
                assert again.status_code == 200, again.text
                assert again.json()["id"] == snap["id"]
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
                for uid in (user_id, finance_id, hr_id, staff_id):
                    if uid is None:
                        continue
                    user = await session.get(UserBase, uid)
                    if user is not None:
                        await session.delete(user)
                await session.commit()
            await engine.dispose()

    asyncio.run(body())
