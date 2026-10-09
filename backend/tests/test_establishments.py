"""Establishments: settings CRUD, people query, DMR stamp (DEV-857)."""

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
    Employment,
    Intake,
    SsBatch,
    StoredFile,
    TenantCryptoKey,
    UserBase,
)
from app.services.ss_apply import delete_company_employment_spine, delete_intake_employment_spine
from app.settings import HEADER_COMPANY_ID, HEADER_INTAKE_SESSION
from tests.ss_xlsx_fixtures import EMPLOYER_NISS, PERSON_A, PERSON_B, combined_workbook
from tests.test_ss_apply import _people_xlsx


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


def _sheet() -> bytes:
    return _people_xlsx(
        [
            (PERSON_A, {"name": "Alice", "salary": 1800}),
            (PERSON_B, {"name": "Bruno", "salary": 2000}),
        ]
    )


def test_establishments_filter_people_and_stamp_uploads(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    identities = _patch_verify(monkeypatch)

    async def body() -> None:
        intake_id = None
        company_id = None
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
                    json={"legal_name": "Sites Lda"},
                )
                assert converted.status_code == 200, converted.text
                company_id = uuid.UUID(converted.json()["company_id"])

                finance_me = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {finance_token}"}
                )
                hr_me = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {hr_token}"}
                )
                staff_me = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {staff_token}"}
                )
                async with AsyncSessionLocal() as session:
                    session.add(
                        CompanyMembership(
                            user_id=uuid.UUID(finance_me.json()["id"]),
                            company_id=company_id,
                            role="FINANCE",
                        )
                    )
                    session.add(
                        CompanyMembership(
                            user_id=uuid.UUID(hr_me.json()["id"]),
                            company_id=company_id,
                            role="HR",
                        )
                    )
                    staff = await session.get(UserBase, uuid.UUID(staff_me.json()["id"]))
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
                staff_auth = {
                    "Authorization": f"Bearer {staff_token}",
                    HEADER_COMPANY_ID: str(company_id),
                }

                denied = await client.post(
                    "/v1/establishments",
                    headers=finance_auth,
                    json={"name": "Lisboa", "ss_code": "0001"},
                )
                assert denied.status_code == 403

                empty = await client.get("/v1/establishments", headers=hr_auth)
                assert empty.status_code == 200
                assert empty.json() == []

                lisboa = await client.post(
                    "/v1/establishments",
                    headers=auth,
                    json={"name": " Lisboa ", "ss_code": "0001"},
                )
                assert lisboa.status_code == 201, lisboa.text
                assert lisboa.json()["name"] == "Lisboa"
                assert lisboa.json()["ss_code"] == "0001"
                assert lisboa.json()["status"] == "OPEN"
                lisboa_id = lisboa.json()["id"]

                porto = await client.post(
                    "/v1/establishments",
                    headers=auth,
                    json={"name": "Porto", "ss_code": "0002"},
                )
                assert porto.status_code == 201, porto.text
                porto_id = porto.json()["id"]

                duplicate = await client.post(
                    "/v1/establishments",
                    headers=auth,
                    json={"name": "Outra", "ss_code": "0001"},
                )
                assert duplicate.status_code == 409

                bad_code = await client.post(
                    "/v1/establishments",
                    headers=auth,
                    json={"name": "Faro", "ss_code": "12"},
                )
                assert bad_code.status_code == 422

                listed = await client.get("/v1/establishments", headers=hr_auth)
                assert [row["ss_code"] for row in listed.json()] == ["0001", "0002"]

                missing = await client.post(
                    "/v1/ss-batches",
                    headers=auth,
                    data={"period_year_month": "2026-09"},
                    files={
                        "files": (
                            f"{EMPLOYER_NISS}_vinculos_2026_09_01.xlsx",
                            _sheet(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                )
                assert missing.status_code == 400, missing.text

                stamped = await client.post(
                    "/v1/ss-batches",
                    headers=auth,
                    data={
                        "period_year_month": "2026-09",
                        "establishment_id": porto_id,
                    },
                    files={
                        "files": (
                            f"{EMPLOYER_NISS}_vinculos_2026_09_01.xlsx",
                            _sheet(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                )
                assert stamped.status_code == 201, stamped.text
                assert stamped.json()["parse_status"] == "APPLIED"

                everyone = await client.get("/v1/people", headers=auth)
                assert everyone.status_code == 200
                assert len(everyone.json()) == 2
                only_porto = await client.get(
                    "/v1/people",
                    headers=auth,
                    params={"establishment_id": porto_id},
                )
                assert len(only_porto.json()) == 2
                only_lisboa = await client.get(
                    "/v1/people",
                    headers=auth,
                    params={"establishment_id": lisboa_id},
                )
                assert only_lisboa.json() == []

                async with AsyncSessionLocal() as session:
                    rows = (
                        await session.execute(
                            select(Employment).where(Employment.company_id == company_id)
                        )
                    ).scalars().all()
                    assert rows
                    assert {row.establishment_id for row in rows} == {uuid.UUID(porto_id)}

                closed = await client.patch(
                    f"/v1/establishments/{porto_id}",
                    headers=auth,
                    json={"status": "CLOSED"},
                )
                assert closed.status_code == 200
                assert closed.json()["status"] == "CLOSED"
                hr_close = await client.patch(
                    f"/v1/establishments/{porto_id}",
                    headers=hr_auth,
                    json={"status": "OPEN"},
                )
                assert hr_close.status_code == 403

                closed_upload = await client.post(
                    "/v1/ss-batches",
                    headers=auth,
                    data={
                        "period_year_month": "2026-10",
                        "establishment_id": porto_id,
                    },
                    files={
                        "files": (
                            f"{EMPLOYER_NISS}_vinculos_2026_10_01.xlsx",
                            _sheet(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                )
                assert closed_upload.status_code == 409

                implied = await client.post(
                    "/v1/ss-batches",
                    headers=auth,
                    data={"period_year_month": "2026-10"},
                    files={
                        "files": (
                            f"{EMPLOYER_NISS}_vinculos_2026_10_01.xlsx",
                            _sheet(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                )
                assert implied.status_code == 201, implied.text
                moved = await client.get(
                    "/v1/people",
                    headers=hr_auth,
                    params={"establishment_id": lisboa_id},
                )
                assert len(moved.json()) == 2

                staff_site = await client.post(
                    "/v1/establishments",
                    headers=staff_auth,
                    json={"name": "Coimbra", "ss_code": "0003"},
                )
                assert staff_site.status_code == 201, staff_site.text
        finally:
            async with AsyncSessionLocal() as session:
                if company_id is not None:
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
                await session.commit()
            await engine.dispose()

    asyncio.run(body())
