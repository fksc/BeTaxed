"""Two-pass intake: both OD-1 binds, convert, purge (DEV-832)."""

from __future__ import annotations

import asyncio
import base64
import json
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, or_, select

from app.auth.firebase import FirebaseIdentity
from app.db import AsyncSessionLocal, engine
from app.main import app
from app.models import (
    Company,
    CompanyMembership,
    Employee,
    Intake,
    SsBatch,
    SsRawContrato,
    SsRawVinculo,
    StoredFile,
    TenantCryptoKey,
    UserBase,
)
from app.security.dek_store import get_or_create_pii_crypto
from app.security.session import hash_session_token, session_token_matches
from app.services.ss_apply import (
    delete_company_employment_spine,
    delete_intake_employment_spine,
)
from app.settings import HEADER_INTAKE_ID, HEADER_INTAKE_SESSION
from tests.ss_xlsx_fixtures import (
    EMPLOYER_NISS,
    PERSON_A,
    PERSON_B,
    SUBSTITUTE_NISS,
    combined_workbook,
)


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


def test_session_token_hash_is_not_reversible() -> None:
    token = "plain-session-token"
    digest = hash_session_token(token)
    assert digest != token.encode()
    assert session_token_matches(token, digest)
    assert not session_token_matches("other", digest)


def test_upload_first_convert_and_session_me(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    identities = _patch_verify(monkeypatch)

    async def body() -> None:
        storage_paths: list[str] = []
        intake_id = None
        company_id = None
        user_id = None
        try:
            token = _identity(identities, "upload-first")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                created = await client.post("/v1/intakes")
                assert created.status_code == 201, created.text
                payload = created.json()
                intake_id = uuid.UUID(payload["id"])
                session_token = payload["session_token"]
                assert session_token
                assert payload["user_id"] is None
                assert payload["status"] == "OPEN"
                assert payload["teaser_now_monthly"] is None

                denied = await client.get(f"/v1/intakes/{intake_id}")
                assert denied.status_code == 401

                wrong = await client.get(
                    f"/v1/intakes/{intake_id}",
                    headers={HEADER_INTAKE_SESSION: "nope"},
                )
                assert wrong.status_code == 403

                shown = await client.get(
                    f"/v1/intakes/{intake_id}",
                    headers={HEADER_INTAKE_SESSION: session_token},
                )
                assert shown.status_code == 200, shown.text
                body_text = json.dumps(shown.json())
                assert "Alice" not in body_text
                assert PERSON_A not in body_text
                assert "session_token" not in shown.json()

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
                latest = uploaded.json()["latest_batch"]
                assert latest["parse_status"] == "APPLIED"
                assert latest["vinculo_count"] == 2
                assert latest["contrato_count"] == 3
                teaser = uploaded.json()
                assert teaser["teaser_now_monthly"] is not None
                assert teaser["teaser_now_window"] is not None
                assert teaser["teaser_potential_monthly"] is not None
                assert teaser["teaser_potential_window"] is not None
                shown = json.dumps(teaser)
                assert "Alice" not in shown
                assert "Bruno" not in shown
                assert PERSON_A not in shown
                assert "23.75" not in shown
                assert "50%" not in shown

                me_unbound = await client.get(
                    "/v1/me/intake",
                    headers={
                        "Authorization": f"Bearer {token}",
                        HEADER_INTAKE_ID: str(intake_id),
                    },
                )
                assert me_unbound.status_code == 403

                me_session = await client.get(
                    "/v1/me/intake",
                    headers={
                        "Authorization": f"Bearer {token}",
                        HEADER_INTAKE_ID: str(intake_id),
                        HEADER_INTAKE_SESSION: session_token,
                    },
                )
                assert me_session.status_code == 200, me_session.text
                me = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {token}"}
                )
                user_id = uuid.UUID(me.json()["id"])

                steal = await client.post(
                    f"/v1/intakes/{intake_id}/convert",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"legal_name": "Stolen Lda"},
                )
                assert steal.status_code == 403

                converted = await client.post(
                    f"/v1/intakes/{intake_id}/convert",
                    headers={
                        "Authorization": f"Bearer {token}",
                        HEADER_INTAKE_SESSION: session_token,
                    },
                    json={"legal_name": "Upload First Lda"},
                )
                assert converted.status_code == 200, converted.text
                out = converted.json()
                company_id = uuid.UUID(out["company_id"])
                assert out["status"] == "CONVERTED"
                assert out["membership_role"] == "ADMIN"
                assert out["user_id"] == str(user_id)
                assert out["converted_company_id"] == str(company_id)
                assert out["teaser_now_monthly"] == teaser["teaser_now_monthly"]
                assert out["teaser_now_window"] == teaser["teaser_now_window"]
                assert out["teaser_potential_monthly"] == teaser[
                    "teaser_potential_monthly"
                ]
                assert out["teaser_potential_window"] == teaser[
                    "teaser_potential_window"
                ]

                stale_session = await client.get(
                    f"/v1/intakes/{intake_id}",
                    headers={HEADER_INTAKE_SESSION: session_token},
                )
                assert stale_session.status_code in (401, 403)

                owner = await client.get(
                    f"/v1/intakes/{intake_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert owner.status_code == 200

                async with AsyncSessionLocal() as session:
                    intake = await session.get(Intake, intake_id)
                    assert intake is not None
                    assert intake.session_token_hash is None
                    company = await session.get(Company, company_id)
                    assert company is not None
                    assert company.created_from_intake_id == intake_id
                    assert company.legal_name == "Upload First Lda"

                    membership = (
                        await session.execute(
                            select(CompanyMembership).where(
                                CompanyMembership.company_id == company_id
                            )
                        )
                    ).scalar_one()
                    assert membership.role == "ADMIN"
                    assert membership.user_id == user_id

                    batch = (
                        await session.execute(
                            select(SsBatch).where(SsBatch.intake_id == intake_id)
                        )
                    ).scalar_one()
                    assert batch.company_id == company_id
                    stored = (
                        await session.execute(
                            select(StoredFile).where(StoredFile.intake_id == intake_id)
                        )
                    ).scalars().all()
                    storage_paths.extend(row.gcs_path for row in stored)
                    assert all(row.company_id == company_id for row in stored)

                    intake_keys = (
                        await session.execute(
                            select(TenantCryptoKey).where(
                                TenantCryptoKey.intake_id == intake_id
                            )
                        )
                    ).scalars().all()
                    assert intake_keys == []
                    company_crypto = await get_or_create_pii_crypto(
                        session, company_id=company_id
                    )
                    assert batch.employer_niss_hash == company_crypto.niss_hash(
                        EMPLOYER_NISS
                    )
                    assert company.employer_niss_hash == batch.employer_niss_hash
                    vinculos = (
                        await session.execute(
                            select(SsRawVinculo).where(
                                SsRawVinculo.batch_id == batch.id
                            )
                        )
                    ).scalars().all()
                    assert {company_crypto.decrypt_niss(row.niss_enc) for row in vinculos} == {
                        PERSON_A,
                        PERSON_B,
                    }
                    contratos = (
                        await session.execute(
                            select(SsRawContrato).where(
                                SsRawContrato.batch_id == batch.id
                            )
                        )
                    ).scalars().all()
                    leftover = json.dumps([row.leftover or {} for row in contratos])
                    assert SUBSTITUTE_NISS not in leftover
                    company_hex = company_crypto.niss_hash(SUBSTITUTE_NISS).hex()
                    assert company_hex in leftover
                    found_enc = False
                    for row in contratos:
                        for value in (row.leftover or {}).values():
                            if isinstance(value, dict) and value.get("niss_enc"):
                                niss = company_crypto.decrypt_niss(
                                    base64.b64decode(value["niss_enc"][0])
                                )
                                assert niss == SUBSTITUTE_NISS
                                found_enc = True
                    assert found_enc
        finally:
            async with AsyncSessionLocal() as session:
                await _cleanup_converted(
                    session,
                    intake_id=intake_id,
                    company_id=company_id,
                    user_id=user_id,
                )
            for path in storage_paths:
                Path(path).unlink(missing_ok=True)
            await engine.dispose()

    asyncio.run(body())


def test_account_first_upload_and_purge(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    identities = _patch_verify(monkeypatch)

    async def body() -> None:
        storage_paths: list[str] = []
        intake_id = None
        user_id = None
        try:
            token = _identity(identities, "account-first")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                created = await client.post(
                    "/v1/intakes",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert created.status_code == 201, created.text
                payload = created.json()
                assert payload["session_token"] is None
                assert payload["user_id"] is not None
                intake_id = uuid.UUID(payload["id"])
                user_id = uuid.UUID(payload["user_id"])

                uploaded = await client.post(
                    f"/v1/intakes/{intake_id}/uploads",
                    headers={"Authorization": f"Bearer {token}"},
                    data={"period_year_month": "2026-08-01"},
                    files={
                        "files": (
                            "ss.xlsx",
                            combined_workbook(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                )
                assert uploaded.status_code == 201, uploaded.text
                assert uploaded.json()["latest_batch"]["parse_status"] == "APPLIED"

                async with AsyncSessionLocal() as session:
                    stored = (
                        await session.execute(
                            select(StoredFile).where(StoredFile.intake_id == intake_id)
                        )
                    ).scalars().all()
                    storage_paths.extend(row.gcs_path for row in stored)
                    assert stored
                    batch_id = (
                        await session.execute(
                            select(SsBatch.id).where(SsBatch.intake_id == intake_id)
                        )
                    ).scalar_one()

                declined = await client.post(
                    f"/v1/intakes/{intake_id}/decline",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert declined.status_code == 200, declined.text
                assert declined.json()["status"] == "PURGED"
                assert declined.json()["user_id"] is None
                assert declined.json()["teaser_now_monthly"] is None

                missing = await client.get(
                    f"/v1/intakes/{intake_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert missing.status_code == 404

                async with AsyncSessionLocal() as session:
                    intake = await session.get(Intake, intake_id)
                    assert intake is not None
                    assert intake.status == "PURGED"
                    assert intake.user_id is None
                    assert intake.email is None
                    assert intake.session_token_hash is None
                    assert intake.purged_at is not None
                    batches = (
                        await session.execute(
                            select(SsBatch).where(SsBatch.id == batch_id)
                        )
                    ).scalars().all()
                    assert batches == []
                    assert (
                        await session.execute(
                            select(StoredFile).where(StoredFile.intake_id == intake_id)
                        )
                    ).scalars().all() == []
                    assert (
                        await session.execute(
                            select(TenantCryptoKey).where(
                                TenantCryptoKey.intake_id == intake_id
                            )
                        )
                    ).scalars().all() == []
                    user = await session.get(UserBase, user_id)
                    assert user is not None
                for path in storage_paths:
                    assert not Path(path).exists()
        finally:
            async with AsyncSessionLocal() as session:
                if intake_id is not None:
                    await session.execute(
                        delete(Intake).where(Intake.id == intake_id)
                    )
                if user_id is not None:
                    row = await session.get(UserBase, user_id)
                    if row is not None:
                        await session.delete(row)
                await session.commit()
            await engine.dispose()

    asyncio.run(body())


def test_upload_first_decline_keeps_no_account(db_session) -> None:
    async def body() -> None:
        storage_paths: list[str] = []
        intake_id = None
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                created = await client.post("/v1/intakes")
                assert created.status_code == 201, created.text
                intake_id = uuid.UUID(created.json()["id"])
                session_token = created.json()["session_token"]
                uploaded = await client.post(
                    f"/v1/intakes/{intake_id}/uploads",
                    headers={HEADER_INTAKE_SESSION: session_token},
                    data={"period_year_month": "2026-08-01"},
                    files={
                        "files": (
                            "ss.xlsx",
                            combined_workbook(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                )
                assert uploaded.status_code == 201, uploaded.text
                async with AsyncSessionLocal() as session:
                    stored = (
                        await session.execute(
                            select(StoredFile).where(StoredFile.intake_id == intake_id)
                        )
                    ).scalars().all()
                    storage_paths.extend(row.gcs_path for row in stored)

                declined = await client.post(
                    f"/v1/intakes/{intake_id}/decline",
                    headers={HEADER_INTAKE_SESSION: session_token},
                )
                assert declined.status_code == 200, declined.text
                assert declined.json()["status"] == "PURGED"
                for path in storage_paths:
                    assert not Path(path).exists()
        finally:
            async with AsyncSessionLocal() as session:
                if intake_id is not None:
                    await session.execute(
                        delete(Intake).where(Intake.id == intake_id)
                    )
                    await session.commit()
            await engine.dispose()

    asyncio.run(body())


async def _cleanup_converted(
    session,
    *,
    intake_id: uuid.UUID | None,
    company_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
) -> None:
    if company_id is not None:
        await session.execute(
            delete(CompanyMembership).where(
                CompanyMembership.company_id == company_id
            )
        )
        await delete_company_employment_spine(session, company_id)
    if intake_id is not None:
        await delete_intake_employment_spine(session, intake_id)
    clauses = []
    if intake_id is not None:
        clauses.append(SsBatch.intake_id == intake_id)
    if company_id is not None:
        clauses.append(SsBatch.company_id == company_id)
    if clauses:
        await session.execute(delete(SsBatch).where(or_(*clauses)))
        if intake_id is not None:
            await session.execute(
                delete(StoredFile).where(StoredFile.intake_id == intake_id)
            )
            await session.execute(
                delete(Employee).where(Employee.intake_id == intake_id)
            )
            await session.execute(
                delete(TenantCryptoKey).where(TenantCryptoKey.intake_id == intake_id)
            )
        if company_id is not None:
            await session.execute(
                delete(StoredFile).where(StoredFile.company_id == company_id)
            )
            await session.execute(
                delete(Employee).where(Employee.company_id == company_id)
            )
            await session.execute(
                delete(TenantCryptoKey).where(
                    TenantCryptoKey.company_id == company_id
                )
            )
    if intake_id is not None:
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
    await session.commit()
