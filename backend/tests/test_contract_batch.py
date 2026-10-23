"""Batch PDF upload associates NIF, then name, then NISS (DEV-850)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import AsyncSessionLocal, engine
from app.main import app
from app.models import ContractInbox, Employee, StoredFile
from app.security.dek_store import get_or_create_pii_crypto
from app.services.contract_llm import ContractExtract
from app.settings import HEADER_COMPANY_ID, HEADER_INTAKE_SESSION, get_gcs_bucket
from tests.ss_xlsx_fixtures import EMPLOYER_NISS, PERSON_B, combined_workbook
from tests.test_contracts import _identity, _patch_verify, _purge_contract_company


@pytest.fixture
def db_session():
    return True


def _xlsx():
    return (
        f"{EMPLOYER_NISS}_vinculos_2026_08_12.xlsx",
        combined_workbook(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


async def _company(client: AsyncClient, token: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    created = await client.post("/v1/intakes")
    assert created.status_code == 201, created.text
    intake_id = uuid.UUID(created.json()["id"])
    session_token = created.json()["session_token"]
    filename, workbook, mime = _xlsx()
    uploaded = await client.post(
        f"/v1/intakes/{intake_id}/uploads",
        headers={HEADER_INTAKE_SESSION: session_token},
        data={"period_year_month": "2026-08"},
        files={"files": (filename, workbook, mime)},
    )
    assert uploaded.status_code == 201, uploaded.text
    converted = await client.post(
        f"/v1/intakes/{intake_id}/convert",
        headers={
            "Authorization": f"Bearer {token}",
            HEADER_INTAKE_SESSION: session_token,
        },
        json={"legal_name": "Batch Contracts Lda"},
    )
    assert converted.status_code == 200, converted.text
    company_id = uuid.UUID(converted.json()["company_id"])
    me = await client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    user_id = uuid.UUID(me.json()["id"])
    return intake_id, company_id, user_id


def test_batch_contracts_match_nif_then_name_then_niss(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CONTRACT_LLM", "stub")
    monkeypatch.setenv("GCS_BUCKET", "")
    get_gcs_bucket.cache_clear()

    calls: list[str] = []

    class _Scripted:
        def extract(self, data: bytes, *, mime_type: str | None, filename: str | None):
            calls.append(filename or "")
            table = {
                "alice-name.pdf": {"full_name": "Alice", "nif": "123456789", "niss": None},
                "alice-nif.pdf": {"full_name": "Bruno", "nif": "123456789", "niss": None},
                "bruno-niss.pdf": {"full_name": "Nope", "nif": None, "niss": PERSON_B},
                "nobody.pdf": {
                    "full_name": "Nobody",
                    "nif": "000000000",
                    "niss": "99999999999",
                },
                "alice-conflict.pdf": {
                    "full_name": "Alice",
                    "nif": "123456789",
                    "niss": None,
                },
            }
            fields = table[filename or ""]
            return ContractExtract(
                doc_kind="TERMO",
                signed_on=date(2022, 2, 1),
                term_end_on=date(2023, 2, 1),
                leftover={"extractor": "test"},
                full_name=fields["full_name"],
                nif=fields["nif"],
                niss=fields["niss"],
            )

    monkeypatch.setattr(
        "app.services.contract_inbox.get_contract_extractor",
        lambda: _Scripted(),
    )
    identities = _patch_verify(monkeypatch)

    async def body() -> None:
        intake_id = None
        company_id = None
        user_id = None
        try:
            company_token = _identity(identities, "co")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                intake_id, company_id, user_id = await _company(client, company_token)
                people = await client.get(
                    "/v1/people",
                    headers={
                        "Authorization": f"Bearer {company_token}",
                        HEADER_COMPANY_ID: str(company_id),
                    },
                )
                assert people.status_code == 200, people.text
                by_name = {row["display_name"]: row for row in people.json()}
                alice_id = uuid.UUID(by_name["Alice"]["id"])
                bruno_id = uuid.UUID(by_name["Bruno"]["id"])
                headers = {
                    "Authorization": f"Bearer {company_token}",
                    HEADER_COMPANY_ID: str(company_id),
                }
                posted = await client.post(
                    "/v1/contracts",
                    headers=headers,
                    files=[
                        ("files", ("alice-name.pdf", b"%PDF-1.4 alice", "application/pdf")),
                        ("files", ("alice-nif.pdf", b"%PDF-1.4 nif", "application/pdf")),
                        ("files", ("bruno-niss.pdf", b"%PDF-1.4 niss", "application/pdf")),
                        ("files", ("nobody.pdf", b"%PDF-1.4 none", "application/pdf")),
                    ],
                )
                assert posted.status_code == 201, posted.text
                blob = posted.text
                assert "123456789" not in blob
                assert PERSON_B not in blob
                items = {row["filename"]: row for row in posted.json()["items"]}
                assert items["alice-name.pdf"]["status"] == "MATCHED"
                assert items["alice-name.pdf"]["match_via"] == "NAME"
                assert items["alice-name.pdf"]["employee_id"] == str(alice_id)
                assert items["alice-nif.pdf"]["match_via"] == "NIF"
                assert items["alice-nif.pdf"]["employee_id"] == str(alice_id)
                assert items["bruno-niss.pdf"]["match_via"] == "NISS"
                assert items["bruno-niss.pdf"]["employee_id"] == str(bruno_id)
                assert items["nobody.pdf"]["status"] == "UNMATCHED"
                assert items["nobody.pdf"]["employee_id"] is None

                seen = len(calls)
                again = await client.post(
                    "/v1/contracts",
                    headers=headers,
                    files=[
                        ("files", ("alice-again.pdf", b"%PDF-1.4 alice", "application/pdf")),
                    ],
                )
                assert again.status_code == 201, again.text
                again_row = again.json()["items"][0]
                assert again_row["status"] == "MATCHED"
                assert again_row["employee_id"] == str(alice_id)
                assert again_row["document_id"] == items["alice-name.pdf"]["document_id"]
                assert len(calls) == seen

                async with AsyncSessionLocal() as session:
                    alice = await session.get(Employee, alice_id)
                    assert alice is not None and alice.nif_enc is not None
                    crypto = await get_or_create_pii_crypto(session, company_id=company_id)
                    assert crypto.decrypt_nif(alice.nif_enc) == "123456789"
                    inbox = await session.get(
                        ContractInbox, uuid.UUID(items["alice-name.pdf"]["inbox_id"])
                    )
                    assert inbox is not None
                    stored = await session.get(StoredFile, inbox.file_id)
                    assert stored is not None
                    assert f"{company_id}/contracts/" in stored.gcs_path.replace("\\", "/")
                    alice.nif_enc = crypto.encrypt_nif("999999999")
                    alice.nif_hash = crypto.nif_hash("999999999")
                    await session.commit()

                conflict = await client.post(
                    "/v1/contracts",
                    headers=headers,
                    files=[
                        (
                            "files",
                            ("alice-conflict.pdf", b"%PDF-1.4 conflict", "application/pdf"),
                        )
                    ],
                )
                assert conflict.status_code == 201, conflict.text
                conflict_row = conflict.json()["items"][0]
                assert conflict_row["match_via"] == "NAME"
                assert conflict_row["employee_id"] == str(alice_id)
                async with AsyncSessionLocal() as session:
                    alice = await session.get(Employee, alice_id)
                    assert alice is not None and alice.nif_enc is not None
                    crypto = await get_or_create_pii_crypto(session, company_id=company_id)
                    assert crypto.decrypt_nif(alice.nif_enc) == "999999999"
                    inbox = await session.get(
                        ContractInbox, uuid.UUID(conflict_row["inbox_id"])
                    )
                    assert inbox is not None
                    assert inbox.nif_conflict is True
        finally:
            await _purge_contract_company(
                company_id=company_id,
                intake_id=intake_id,
                user_id=user_id,
                staff_id=None,
            )
            await engine.dispose()

    asyncio.run(body())


def test_batch_enqueue_then_worker(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTRACT_LLM", "stub")
    monkeypatch.setenv("GCS_BUCKET", "")
    get_gcs_bucket.cache_clear()
    monkeypatch.setenv("INTERNAL_JOB_TOKEN", "test-job-token")
    enqueued: list[uuid.UUID] = []

    class _Scripted:
        def extract(self, data: bytes, *, mime_type: str | None, filename: str | None):
            return ContractExtract(
                doc_kind="TERMO",
                signed_on=date(2022, 2, 1),
                term_end_on=date(2023, 2, 1),
                leftover={"extractor": "test"},
                full_name="Alice",
            )

    monkeypatch.setattr(
        "app.services.contract_inbox.get_contract_extractor",
        lambda: _Scripted(),
    )
    monkeypatch.setattr("app.services.contract_jobs.contract_tasks_configured", lambda: True)
    monkeypatch.setattr(
        "app.services.contract_jobs.enqueue_contract_inbox",
        lambda inbox_id: enqueued.append(inbox_id),
    )
    identities = _patch_verify(monkeypatch)

    async def body() -> None:
        intake_id = None
        company_id = None
        user_id = None
        try:
            company_token = _identity(identities, "co")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                intake_id, company_id, user_id = await _company(client, company_token)
                headers = {
                    "Authorization": f"Bearer {company_token}",
                    HEADER_COMPANY_ID: str(company_id),
                }
                posted = await client.post(
                    "/v1/contracts",
                    headers=headers,
                    files=[("files", ("alice.pdf", b"%PDF-1.4 alice", "application/pdf"))],
                )
                assert posted.status_code == 201, posted.text
                item = posted.json()["items"][0]
                assert item["status"] == "PENDING"
                assert enqueued == [uuid.UUID(item["inbox_id"])]
                denied = await client.post(
                    "/internal/workers/review-contract",
                    json={"inbox_id": item["inbox_id"]},
                )
                assert denied.status_code == 401
                worked = await client.post(
                    "/internal/workers/review-contract",
                    headers={"X-Internal-Job-Token": "test-job-token"},
                    json={"inbox_id": item["inbox_id"]},
                )
                assert worked.status_code == 200, worked.text
                async with AsyncSessionLocal() as session:
                    inbox = await session.get(ContractInbox, uuid.UUID(item["inbox_id"]))
                    assert inbox is not None
                    assert inbox.status == "MATCHED"
                    assert inbox.match_via == "NAME"
        finally:
            await _purge_contract_company(
                company_id=company_id,
                intake_id=intake_id,
                user_id=user_id,
                staff_id=None,
            )
            await engine.dispose()

    asyncio.run(body())
