"""Invoices, commercial terms, and company serializer (DEV-839)."""

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
    Intake,
    Notification,
    SsBatch,
    StoredFile,
    TenantCryptoKey,
    UserBase,
)
from app.models.billing import Payment
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


def test_invoices_company_payload_hr_forbidden_staff_draft_issue_resolve(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    identities = _patch_verify(monkeypatch)

    async def body() -> None:
        intake_id = None
        company_id = None
        user_id = None
        hr_id = None
        staff_id = None
        try:
            admin_token = _identity(identities, "ad")
            hr_token = _identity(identities, "hr")
            staff_token = _identity(identities, "st")
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
                    data={"period_year_month": "2026-08"},
                    files={
                        "files": (
                            f"{EMPLOYER_NISS}_vinculos_2026_08_12.xlsx",
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
                    json={"legal_name": "Billing Lda"},
                )
                assert converted.status_code == 200, converted.text
                company_id = uuid.UUID(converted.json()["company_id"])
                me = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {admin_token}"}
                )
                user_id = uuid.UUID(me.json()["id"])
                hr_me = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {hr_token}"}
                )
                hr_id = uuid.UUID(hr_me.json()["id"])
                staff_me = await client.get(
                    "/v1/me", headers={"Authorization": f"Bearer {staff_token}"}
                )
                staff_id = uuid.UUID(staff_me.json()["id"])
                async with AsyncSessionLocal() as session:
                    session.add(
                        CompanyMembership(
                            user_id=hr_id, company_id=company_id, role="HR"
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
                hr_auth = {
                    "Authorization": f"Bearer {hr_token}",
                    HEADER_COMPANY_ID: str(company_id),
                }
                staff_headers = {"Authorization": f"Bearer {staff_token}"}

                terms = await client.post(
                    f"/v1/ops/companies/{company_id}/commercial-terms",
                    headers=staff_headers,
                    json={"fee_percent": "0.30", "valid_from": "2020-01-01"},
                )
                assert terms.status_code == 201, terms.text
                rebuilt = await client.post(
                    f"/v1/ops/companies/{company_id}/benefit-rebuild"
                    "?as_of=2026-08-26",
                    headers=staff_headers,
                )
                assert rebuilt.status_code == 200, rebuilt.text

                hr_get = await client.get("/v1/invoices", headers=hr_auth)
                assert hr_get.status_code == 403

                draft = await client.post(
                    f"/v1/ops/companies/{company_id}/invoices",
                    headers=staff_headers,
                    json={"year_month": "2026-09-01"},
                )
                assert draft.status_code == 201, draft.text
                invoice_id = draft.json()["id"]
                assert draft.json()["status"] == "DRAFT"
                assert any(line.get("saving_amount") is not None for line in draft.json()["lines"])

                listed = await client.get("/v1/invoices", headers=auth)
                assert listed.status_code == 200, listed.text
                blob = str(listed.json())
                assert "saving_amount" not in blob
                assert "employee_id" not in blob
                assert "remaining_months" not in blob
                assert "certified_external_id" not in blob
                assert listed.json()[0]["id"] == invoice_id
                assert listed.json()[0]["has_proforma"] is False
                assert listed.json()[0]["has_legal_pdf"] is False

                hr_pf = await client.post(
                    f"/v1/invoices/{invoice_id}/proforma",
                    headers=hr_auth,
                    files={"file": ("proforma.pdf", b"%PDF-1.4 p", "application/pdf")},
                )
                assert hr_pf.status_code == 403

                proforma = await client.post(
                    f"/v1/invoices/{invoice_id}/proforma",
                    headers=auth,
                    files={"file": ("proforma.pdf", b"%PDF-1.4 p", "application/pdf")},
                )
                assert proforma.status_code == 200, proforma.text
                assert proforma.json()["has_proforma"] is True
                assert "certified_external_id" not in proforma.json()

                legal = await client.post(
                    f"/v1/invoices/{invoice_id}/legal-pdf",
                    headers=auth,
                    data={
                        "legal_invoice_number": "FT 2026/183",
                        "atcud": "JSTD1234",
                        "certified_external_id": "should-not-stick",
                    },
                    files={"file": ("fatura.pdf", b"%PDF-1.4 f", "application/pdf")},
                )
                assert legal.status_code == 200, legal.text
                assert legal.json()["legal_invoice_number"] == "FT 2026/183"
                assert legal.json()["atcud"] == "JSTD1234"
                assert legal.json()["has_legal_pdf"] is True
                assert "certified_external_id" not in legal.json()
                assert "should-not-stick" not in str(legal.json())

                staff_legal = await client.post(
                    f"/v1/invoices/{invoice_id}/legal-pdf",
                    headers={**staff_headers, HEADER_COMPANY_ID: str(company_id)},
                    data={"certified_external_id": "vendor-99"},
                    files={"file": ("fatura2.pdf", b"%PDF-1.4 f2", "application/pdf")},
                )
                assert staff_legal.status_code == 200, staff_legal.text
                assert "certified_external_id" not in staff_legal.json()

                ops_listed = await client.get("/v1/ops/invoices", headers=staff_headers)
                assert ops_listed.status_code == 200, ops_listed.text
                ops_row = next(row for row in ops_listed.json() if row["id"] == invoice_id)
                assert ops_row["certified_external_id"] == "vendor-99"
                assert ops_row["atcud"] == "JSTD1234"

                company_invoicing = await client.post(
                    f"/v1/ops/companies/{company_id}/invoicing",
                    headers=auth,
                    json={"invoicing_method": "CERTIFIED_SOFTWARE"},
                )
                assert company_invoicing.status_code == 403

                invoicing = await client.post(
                    f"/v1/ops/companies/{company_id}/invoicing",
                    headers=staff_headers,
                    json={
                        "invoicing_method": "CERTIFIED_SOFTWARE",
                        "certified_vendor_name": "VendorX",
                    },
                )
                assert invoicing.status_code == 200, invoicing.text
                assert invoicing.json()["invoicing_method"] == "CERTIFIED_SOFTWARE"
                assert invoicing.json()["certified_vendor_name"] == "VendorX"

                issued = await client.post(
                    f"/v1/ops/invoices/{invoice_id}/issue",
                    headers=staff_headers,
                )
                assert issued.status_code == 200, issued.text
                assert issued.json()["status"] == "ISSUED"

                resolved = await client.post(
                    f"/v1/ops/invoices/{invoice_id}/resolve",
                    headers=staff_headers,
                    json={"reason": "Bank transfer"},
                )
                assert resolved.status_code == 200, resolved.text
                assert resolved.json()["status"] == "MANUALLY_RESOLVED"
                async with AsyncSessionLocal() as session:
                    payment = (
                        await session.execute(
                            select(Payment).where(Payment.invoice_id == invoice_id)
                        )
                    ).scalar_one()
                    assert payment.method == "CERTIFIED"
                    assert payment.external_ref == "vendor-99"
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
                for uid in (user_id, hr_id, staff_id):
                    if uid is None:
                        continue
                    user = await session.get(UserBase, uid)
                    if user is not None:
                        await session.delete(user)
                await session.commit()
            await engine.dispose()

    asyncio.run(body())
