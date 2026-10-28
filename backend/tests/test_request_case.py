"""Request-case path, minuta tokens, and decision destinations. DEV-882."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.auth.firebase import FirebaseIdentity
from app.db import AsyncSessionLocal
from app.main import app
from app.models import (
    Company,
    Employee,
    Employment,
    MinutaTemplate,
    PipelineStage,
    PipelineStageOperation,
    RejectionReason,
    RequestCase,
    RequestCaseFile,
    RequestCaseMinuta,
    StoredFile,
    TenantCryptoKey,
    UserBase,
)
from app.security.dek_store import get_or_create_pii_crypto
from app.services.request_pipeline import (
    decision_stage_id,
    earlier_stage_code,
    list_request_cases,
    open_request_case,
    path_for_modality,
    render_minuta,
    run_operation,
    store_request_file,
)
from app.settings import HEADER_COMPANY_ID, get_gcs_bucket


def test_earlier_stage_follows_the_path() -> None:
    assert earlier_stage_code("OPEN_CONTRACT", "ready") == "probation"
    assert earlier_stage_code("FIXED_TERM", "ready") == "signature"
    assert earlier_stage_code("FIXED_TERM", "signature") == "minuta"
    assert earlier_stage_code("FIXED_TERM", "minuta") is None
    assert earlier_stage_code("OPEN_CONTRACT", "probation") is None
    assert earlier_stage_code("FIXED_TERM", "claim") == "awaiting_decision"
    assert earlier_stage_code("OPEN_CONTRACT", "closed_approved") == "awaiting_decision"


def test_path_for_modality() -> None:
    assert path_for_modality("TERMO_CERTO") == "FIXED_TERM"
    assert path_for_modality("TERMO_INCERTO") == "FIXED_TERM"
    assert path_for_modality("SEM_TERMO") == "OPEN_CONTRACT"
    assert path_for_modality(None) == "OPEN_CONTRACT"


def test_preview_pdf_uses_more_than_one_a4_page() -> None:
    from weasyprint import HTML

    from app.services.minuta_preview import _fetch_local, render_minuta_pdf, wrap_minuta_html

    short = HTML(string=wrap_minuta_html("<p>Olá</p>"), url_fetcher=_fetch_local).render()
    long_body = "".join(
        f"<p>Linha {index} da declaração para ocupar a folha A4.</p>" for index in range(80)
    )
    long = HTML(string=wrap_minuta_html(long_body), url_fetcher=_fetch_local).render()
    assert len(short.pages) == 1
    assert len(long.pages) > 1
    assert render_minuta_pdf("<p>{{ company_name }}</p>").startswith(b"%PDF")


def test_render_minuta_fills_tokens() -> None:
    body = render_minuta(
        "<p>{{ person_name }} at {{company_name}} from {{ contract_started_on }}</p>",
        {
            "person_name": "Rita",
            "company_name": "Oficina Norte",
            "contract_started_on": "2024-01-01",
        },
    )
    assert body == "<p>Rita at Oficina Norte from 2024-01-01</p>"


def test_claim_is_blocked_when_the_reason_says_so() -> None:
    won = uuid.uuid4()
    lost = uuid.uuid4()
    claim = uuid.uuid4()
    assignment = PipelineStageOperation(
        stage_id=uuid.uuid4(),
        operation_id=uuid.uuid4(),
        next_won_stage_id=won,
        next_lost_stage_id=lost,
        next_claim_stage_id=claim,
    )
    assert decision_stage_id(assignment, "favorable", blocks_claim=True) == won
    assert decision_stage_id(assignment, "unfavorable", blocks_claim=False) == lost
    assert decision_stage_id(assignment, "claim", blocks_claim=False) == claim
    with pytest.raises(HTTPException) as blocked:
        decision_stage_id(assignment, "claim", blocks_claim=True)
    assert blocked.value.status_code == 400


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


def test_open_case_follows_the_contract_and_company_omits_months(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GCS_BUCKET", "")
    get_gcs_bucket.cache_clear()
    identities = _patch_verify(monkeypatch)

    async def body() -> None:
        company_id = None
        staff_id = None
        member_id = None
        try:
            async with AsyncSessionLocal() as session:
                staff = UserBase(
                    firebase_uid=f"staff-{uuid.uuid4().hex}",
                    email=f"staff-{uuid.uuid4().hex[:8]}@example.test",
                    user_type="BETAXED_STAFF",
                )
                member = UserBase(
                    firebase_uid=f"co-{uuid.uuid4().hex}",
                    email=f"co-{uuid.uuid4().hex[:8]}@example.test",
                    user_type="COMPANY_STAFF",
                )
                company = Company(legal_name="Oficina Norte")
                session.add_all([staff, member, company])
                await session.flush()
                crypto = await get_or_create_pii_crypto(session, company_id=company.id)
                fixed = Employee(
                    company_id=company.id,
                    niss_hash=crypto.niss_hash("11111111111"),
                    niss_enc=crypto.encrypt_niss("11111111111"),
                    name_enc=crypto.encrypt_name("Rita Costa"),
                )
                opened = Employee(
                    company_id=company.id,
                    niss_hash=crypto.niss_hash("22222222222"),
                    niss_enc=crypto.encrypt_niss("22222222222"),
                    name_enc=crypto.encrypt_name("Pedro Alves"),
                )
                session.add_all([fixed, opened])
                await session.flush()
                session.add_all(
                    [
                        Employment(
                            employee_id=fixed.id,
                            company_id=company.id,
                            started_on=date(2024, 1, 1),
                            contract_modality="TERMO_CERTO",
                        ),
                        Employment(
                            employee_id=opened.id,
                            company_id=company.id,
                            started_on=date(2024, 3, 1),
                            contract_modality="SEM_TERMO",
                        ),
                    ]
                )
                await session.commit()
                company_id = company.id
                staff_id = staff.id
                member_id = member.id
                fixed_id = fixed.id
                opened_id = opened.id

            async with AsyncSessionLocal() as session:
                actor = await session.get(UserBase, staff_id)
                assert actor is not None
                fixed_case = await open_request_case(
                    session, employee_id=fixed_id, actor=actor
                )
                open_case = await open_request_case(
                    session, employee_id=opened_id, actor=actor
                )
                await session.commit()
                fixed_stage = await session.get(PipelineStage, fixed_case.stage_id)
                open_stage = await session.get(PipelineStage, open_case.stage_id)
                assert fixed_case.path == "FIXED_TERM"
                assert open_case.path == "OPEN_CONTRACT"
                assert fixed_stage is not None and fixed_stage.code == "minuta"
                assert open_stage is not None and open_stage.code == "probation"

                template = MinutaTemplate(
                    code=f"conv-{uuid.uuid4().hex[:8]}",
                    title="Conversion",
                    body_html="<p>{{ person_name }} / {{ company_name }}</p>",
                )
                session.add(template)
                await session.flush()
                await run_operation(
                    session,
                    case_id=fixed_case.id,
                    actor=actor,
                    code="GENERATE_MINUTA",
                    payload={"template_id": str(template.id)},
                )
                await run_operation(
                    session,
                    case_id=fixed_case.id,
                    actor=actor,
                    code="SEND_MINUTA",
                    payload={},
                )
                await run_operation(
                    session,
                    case_id=open_case.id,
                    actor=actor,
                    code="RECORD_PROBATION",
                    payload={"no_probation": True},
                )
                await session.commit()

                staff_rows = await list_request_cases(
                    session, company_id=company_id, staff=True
                )
                company_rows = await list_request_cases(
                    session, company_id=company_id, staff=False
                )
                by_path = {row["path"]: row for row in staff_rows}
                assert by_path["FIXED_TERM"]["stage_code"] == "signature"
                assert by_path["OPEN_CONTRACT"]["stage_code"] == "ready"
                assert "remaining_months" not in company_rows[0]
                assert "person_nif" not in company_rows[0]
                assert "draft_html" not in company_rows[0]
                assert "operations" not in company_rows[0]
                assert "moves" not in company_rows[0]
                assert any(
                    move["operation"] == "ATTACH_SIGNED_SCAN"
                    for move in by_path["FIXED_TERM"]["moves"]
                )
                assert [event["to_stage_code"] for event in by_path["FIXED_TERM"]["events"]] == [
                    "minuta",
                    "signature",
                ]
                assert by_path["FIXED_TERM"]["events"][0]["from_stage_id"] is None
                assert by_path["FIXED_TERM"]["events"][1]["operation"] == "SEND_MINUTA"
                assert company_rows[0]["events"]
                reverted = await run_operation(
                    session,
                    case_id=open_case.id,
                    actor=actor,
                    code="REVERT",
                    payload={},
                )
                await session.flush()
                back = await session.get(PipelineStage, reverted.stage_id)
                assert back is not None and back.code == "probation"
                trailed = await list_request_cases(session, company_id=company_id, staff=True)
                open_events = next(row["events"] for row in trailed if row["id"] == open_case.id)
                assert open_events[-1]["operation"] == "REVERT"
                assert open_events[-1]["to_stage_code"] == "probation"
                assert open_events[-1]["from_stage_code"] == "ready"
                await run_operation(
                    session,
                    case_id=open_case.id,
                    actor=actor,
                    code="RECORD_PROBATION",
                    payload={"no_probation": True},
                )
                await session.commit()
                minuta = (
                    await session.execute(
                        select(RequestCaseMinuta).where(
                            RequestCaseMinuta.request_case_id == fixed_case.id
                        )
                    )
                ).scalar_one()
                assert "Rita Costa" in minuta.body_html
                assert "Oficina Norte" in minuta.body_html

                reason = (
                    await session.execute(
                        select(RejectionReason).where(
                            RejectionReason.code == "PRIOR_SEM_TERMO"
                        )
                    )
                ).scalar_one()
                notice = await store_request_file(
                    session,
                    company_id=company_id,
                    actor_id=actor.id,
                    kind="UNFAVORABLE_NOTICE",
                    filename="notice.pdf",
                    content=b"%PDF-notice",
                    mime_type="application/pdf",
                )
                await run_operation(
                    session,
                    case_id=open_case.id,
                    actor=actor,
                    code="RECORD_FILING",
                    payload={"applied_on": "2026-10-01"},
                )
                with pytest.raises(HTTPException):
                    await run_operation(
                        session,
                        case_id=open_case.id,
                        actor=actor,
                        code="RECORD_DECISION",
                        payload={
                            "outcome": "claim",
                            "rejection_reason_id": str(reason.id),
                            "file_id": str(notice.id),
                        },
                    )
                await session.rollback()

            staff_token = f"st-{uuid.uuid4().hex[:12]}"
            identities[staff_token] = FirebaseIdentity(
                uid=(await _uid(staff_id)),
                email=f"http-{uuid.uuid4().hex[:8]}@example.test",
            )
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                listed = await client.get(
                    "/v1/request-cases",
                    headers={
                        "Authorization": f"Bearer {staff_token}",
                        HEADER_COMPANY_ID: str(company_id),
                    },
                )
                assert listed.status_code == 200, listed.text
                payload = listed.json()
                assert payload
                assert all("remaining_months" not in row for row in payload)
        finally:
            if company_id is not None:
                await _cleanup(company_id, staff_id, member_id)

    import asyncio

    asyncio.run(body())


async def _uid(user_id: uuid.UUID) -> str:
    async with AsyncSessionLocal() as session:
        user = await session.get(UserBase, user_id)
        assert user is not None
        return user.firebase_uid


async def _cleanup(
    company_id: uuid.UUID,
    staff_id: uuid.UUID | None,
    member_id: uuid.UUID | None,
) -> None:
    async with AsyncSessionLocal() as session:
        case_ids = list(
            (
                await session.execute(
                    select(RequestCase.id).where(RequestCase.company_id == company_id)
                )
            )
            .scalars()
            .all()
        )
        template_ids: list[uuid.UUID] = []
        if case_ids:
            template_ids = list(
                (
                    await session.execute(
                        select(RequestCaseMinuta.template_id).where(
                            RequestCaseMinuta.request_case_id.in_(case_ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
            await session.execute(
                delete(RequestCaseMinuta).where(
                    RequestCaseMinuta.request_case_id.in_(case_ids)
                )
            )
        if template_ids:
            await session.execute(
                delete(MinutaTemplate).where(MinutaTemplate.id.in_(template_ids))
            )
        await session.execute(
            delete(RequestCaseFile).where(RequestCaseFile.company_id == company_id)
        )
        await session.execute(
            delete(StoredFile).where(StoredFile.company_id == company_id)
        )
        await session.execute(
            delete(RequestCase).where(RequestCase.company_id == company_id)
        )
        await session.execute(
            delete(Employment).where(Employment.company_id == company_id)
        )
        await session.execute(delete(Employee).where(Employee.company_id == company_id))
        await session.execute(
            delete(TenantCryptoKey).where(TenantCryptoKey.company_id == company_id)
        )
        await session.execute(delete(Company).where(Company.id == company_id))
        user_ids = [item for item in (staff_id, member_id) if item is not None]
        if user_ids:
            await session.execute(delete(UserBase).where(UserBase.id.in_(user_ids)))
        await session.commit()
