"""Company monthly SS upload, headcount, and NISS fail-closed (DEV-835)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, or_, select, text

from app.auth.firebase import FirebaseIdentity
from app.db import AsyncSessionLocal, engine
from app.main import app
from app.models import (
    Company,
    CompanyHeadcountMonth,
    CompanyMembership,
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


def test_company_headcount_table_exists(db_session) -> None:
    async def body() -> None:
        try:
            async with AsyncSessionLocal() as session:
                rows = (
                    await session.execute(
                        text(
                            "SELECT tablename FROM pg_tables "
                            "WHERE schemaname = 'public' "
                            "AND tablename = 'company_headcount_month'"
                        )
                    )
                ).fetchall()
                assert rows
        finally:
            await engine.dispose()

    asyncio.run(body())


def test_company_ss_loop_headcount_events_niss_and_roles(
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
                    json={"legal_name": "Headcount Lda"},
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

                async with AsyncSessionLocal() as session:
                    intake_hc = (
                        await session.execute(
                            select(CompanyHeadcountMonth).where(
                                CompanyHeadcountMonth.company_id == company_id
                            )
                        )
                    ).scalars().all()
                    assert len(intake_hc) == 1
                    assert intake_hc[0].source == "SS_BATCH"
                    assert intake_hc[0].headcount == 2
                    assert intake_hc[0].year_month == date(2026, 8, 1)

                listed = await client.get("/v1/ss-batches", headers=auth)
                assert listed.status_code == 200, listed.text
                batches = listed.json()
                assert len(batches) >= 1
                assert batches[0]["parse_status"] == "APPLIED"
                assert "HIRED" in batches[0]["event_counts"]
                blob = str(batches)
                assert PERSON_A not in blob
                assert "remaining_months" not in blob
                assert "old_salary" not in blob

                month2 = _people_xlsx(
                    [
                        (
                            PERSON_A,
                            {
                                "name": "Alice",
                                "salary": 1800,
                                "pay_from": date(2026, 9, 1),
                            },
                        ),
                        (PERSON_B, {"name": "Bruno", "salary": 2000}),
                    ]
                )
                posted = await client.post(
                    "/v1/ss-batches",
                    headers=auth,
                    data={"period_year_month": "2026-09"},
                    files={
                        "files": (
                            f"{EMPLOYER_NISS}_vinculos_2026_09.xlsx",
                            month2,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                )
                assert posted.status_code == 201, posted.text
                body = posted.json()
                assert body["parse_status"] == "APPLIED"
                assert body["event_counts"].get("SALARY_CHANGED", 0) >= 1

                forbidden = await client.post(
                    "/v1/ss-batches",
                    headers=finance_auth,
                    data={"period_year_month": "2026-10"},
                    files={
                        "files": (
                            f"{EMPLOYER_NISS}_vinculos_2026_10.xlsx",
                            combined_workbook(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                )
                assert forbidden.status_code == 403

                mismatch = await client.post(
                    "/v1/ss-batches",
                    headers=auth,
                    data={"period_year_month": "2026-10"},
                    files={
                        "files": (
                            "99999999999_vinculos_2026_10.xlsx",
                            combined_workbook(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                )
                assert mismatch.status_code == 409, mismatch.text
                async with AsyncSessionLocal() as session:
                    failed = (
                        await session.execute(
                            select(SsBatch).where(
                                SsBatch.company_id == company_id,
                                SsBatch.period_year_month == date(2026, 10, 1),
                            )
                        )
                    ).scalars().all()
                    assert failed
                    assert all(row.parse_status == "FAILED" for row in failed)
                    assert all(row.parse_status != "APPLIED" for row in failed)

                user_put = await client.put(
                    "/v1/headcount-months",
                    headers=auth,
                    json={"year_month": "2026-07", "headcount": 12},
                )
                assert user_put.status_code == 200, user_put.text
                assert user_put.json()["source"] == "USER"
                assert user_put.json()["headcount"] == 12

                finance_put = await client.put(
                    "/v1/headcount-months",
                    headers=finance_auth,
                    json={"year_month": "2026-06", "headcount": 9},
                )
                assert finance_put.status_code == 403

                months = await client.get("/v1/headcount-months", headers=auth)
                assert months.status_code == 200, months.text
                rows = months.json()
                sources = {(row["year_month"], row["source"]): row["headcount"] for row in rows}
                assert sources[("2026-08-01", "SS_BATCH")] == 2
                assert sources[("2026-09-01", "SS_BATCH")] == 2
                assert sources[("2026-07-01", "USER")] == 12
                assert ("2026-08-01", "USER") not in sources
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


def test_intake_apply_does_not_write_headcount(db_session) -> None:
    async def body() -> None:
        intake_id = None
        try:
            async with AsyncSessionLocal() as session:
                from app.services.ss_apply import apply_ss_batch
                from app.services.ss_ingest import ingest_ss_export
                from app.services.ss_parser import SsSourceFile

                intake = Intake(status="OPEN")
                session.add(intake)
                await session.flush()
                intake_id = intake.id
                ingested = await ingest_ss_export(
                    session,
                    files=[
                        SsSourceFile(
                            f"{EMPLOYER_NISS}_vinculos.xlsx", combined_workbook()
                        )
                    ],
                    period_year_month=date(2026, 8, 1),
                    intake_id=intake.id,
                )
                await apply_ss_batch(session, ingested.batch.id)
                await session.commit()
                count = (
                    await session.execute(
                        select(CompanyHeadcountMonth).where(
                            CompanyHeadcountMonth.source_batch_id == ingested.batch.id
                        )
                    )
                ).scalars().all()
                assert count == []
        finally:
            async with AsyncSessionLocal() as session:
                if intake_id is not None:
                    await delete_intake_employment_spine(session, intake_id)
                    await session.execute(
                        delete(SsBatch).where(SsBatch.intake_id == intake_id)
                    )
                    await session.execute(
                        delete(StoredFile).where(StoredFile.intake_id == intake_id)
                    )
                    await session.execute(
                        delete(TenantCryptoKey).where(
                            TenantCryptoKey.intake_id == intake_id
                        )
                    )
                    await session.execute(delete(Intake).where(Intake.id == intake_id))
                await session.commit()
            await engine.dispose()

    asyncio.run(body())
