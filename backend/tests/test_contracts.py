"""Contract upload, LLM stub review, staff mismatch flags (DEV-836)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.auth.firebase import FirebaseIdentity
from app.db import AsyncSessionLocal, engine
from app.main import app
from app.models import (
    Company,
    CompanyMembership,
    DomainEvent,
    Employment,
    EmploymentDocument,
    Intake,
    Notification,
    SsBatch,
    StoredFile,
    TenantCryptoKey,
    UserBase,
)
from app.services.contract_review import compute_matches_ss
from app.services.ss_apply import delete_company_employment_spine, delete_intake_employment_spine
from app.settings import HEADER_COMPANY_ID, HEADER_INTAKE_SESSION
from tests.ss_xlsx_fixtures import EMPLOYER_NISS, combined_workbook


@pytest.fixture
def db_session():
    return True


def test_compute_matches_ss_termo_vs_ss_sem_termo() -> None:
    assert (
        compute_matches_ss(
            ss_modality="SEM_TERMO",
            ss_started_on=date(2021, 1, 1),
            ss_ended_on=None,
            doc_kind="TERMO",
            signed_on=date(2022, 2, 1),
            term_end_on=date(2023, 2, 1),
        )
        == "MISMATCH"
    )
    assert (
        compute_matches_ss(
            ss_modality="SEM_TERMO",
            ss_started_on=date(2022, 2, 1),
            ss_ended_on=None,
            doc_kind="SEM_TERMO",
            signed_on=date(2022, 2, 1),
            term_end_on=None,
        )
        == "MATCH"
    )


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


def test_contract_upload_stub_mismatch_and_staff_apply(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CONTRACT_LLM", "stub")
    identities = _patch_verify(monkeypatch)

    async def body() -> None:
        intake_id = None
        company_id = None
        user_id = None
        staff_id = None
        try:
            company_token = _identity(identities, "co")
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
                    files={"files": (filename, combined_workbook(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                )
                assert uploaded.status_code == 201, uploaded.text

                converted = await client.post(
                    f"/v1/intakes/{intake_id}/convert",
                    headers={
                        "Authorization": f"Bearer {company_token}",
                        HEADER_INTAKE_SESSION: session_token,
                    },
                    json={"legal_name": "Contracts Lda"},
                )
                assert converted.status_code == 200, converted.text
                company_id = uuid.UUID(converted.json()["company_id"])

                me = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {company_token}"}
                )
                user_id = uuid.UUID(me.json()["id"])

                staff_me = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {staff_token}"}
                )
                staff_id = uuid.UUID(staff_me.json()["id"])
                async with AsyncSessionLocal() as session:
                    staff = await session.get(UserBase, staff_id)
                    assert staff is not None
                    staff.user_type = "BETAXED_STAFF"
                    await session.commit()

                people = await client.get(
                    "/v1/people",
                    headers={
                        "Authorization": f"Bearer {company_token}",
                        HEADER_COMPANY_ID: str(company_id),
                    },
                )
                assert people.status_code == 200, people.text
                rows = people.json()
                assert len(rows) >= 1
                blob = str(rows)
                assert "11111111111" not in blob
                assert "remaining_months" not in blob
                employee_id = rows[0]["id"]

                posted = await client.post(
                    f"/v1/people/{employee_id}/contracts",
                    headers={
                        "Authorization": f"Bearer {company_token}",
                        HEADER_COMPANY_ID: str(company_id),
                    },
                    files={"file": ("contrato.pdf", b"%PDF-1.4 stub", "application/pdf")},
                )
                assert posted.status_code == 201, posted.text
                body_json = posted.json()
                assert body_json["matches_ss"] is None
                assert body_json["review_status"] in {"REVIEWED", "PENDING", "FAILED"}

                flags = await client.get(
                    "/v1/ops/contract-flags",
                    headers={"Authorization": f"Bearer {company_token}"},
                )
                assert flags.status_code == 403

                flags = await client.get(
                    "/v1/ops/contract-flags",
                    headers={"Authorization": f"Bearer {staff_token}"},
                )
                assert flags.status_code == 200, flags.text
                flag_rows = flags.json()
                assert len(flag_rows) >= 1
                assert flag_rows[0]["doc_kind"] == "TERMO"
                assert flag_rows[0]["ss_modality"] == "SEM_TERMO"
                doc_id = flag_rows[0]["id"]

                applied = await client.post(
                    f"/v1/ops/employment-documents/{doc_id}/apply",
                    headers={"Authorization": f"Bearer {staff_token}"},
                )
                assert applied.status_code == 200, applied.text

                async with AsyncSessionLocal() as session:
                    doc = await session.get(EmploymentDocument, uuid.UUID(doc_id))
                    assert doc is not None
                    assert doc.ops_confirmed_at is not None
                    emp = await session.get(Employment, doc.employment_id)
                    assert emp is not None
                    assert emp.contract_modality == "TERMO_CERTO"
                    notes = (
                        await session.execute(
                            select(Notification).where(
                                Notification.recipient_id == staff_id
                            )
                        )
                    ).scalars().all()
                    assert notes
                    events = (
                        await session.execute(
                            select(DomainEvent).where(
                                DomainEvent.company_id == company_id
                            )
                        )
                    ).scalars().all()
                    types = {e.event_type for e in events}
                    assert "CONTRACT_UPLOADED" in types
                    assert "CONTRACT_SS_MISMATCH" in types
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
                    await session.execute(delete(SsBatch).where(SsBatch.company_id == company_id))
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
                if staff_id is not None:
                    staff = await session.get(UserBase, staff_id)
                    if staff is not None:
                        await session.delete(staff)
                await session.commit()
            await engine.dispose()

    asyncio.run(body())
