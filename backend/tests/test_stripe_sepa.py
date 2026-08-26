"""SEPA checkout, collect, and failed debit → LATE (DEV-842)."""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, or_, select

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
from tests.test_billing import _identity, _patch_verify
from tests.test_stripe_hmac import _SECRET, signed_header


@pytest.fixture
def db_session():
    return True


def test_sepa_checkout_collect_failed_debit_is_late_not_paid(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    identities = _patch_verify(monkeypatch)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", _SECRET)
    monkeypatch.setenv("ENV", "DEV")
    monkeypatch.setattr(
        "app.services.billing.ensure_stripe_customer", lambda **_: "cus_test"
    )
    monkeypatch.setattr(
        "app.services.billing.create_sepa_setup_session",
        lambda **_: "https://checkout.stripe.test/session",
    )
    monkeypatch.setattr(
        "app.services.billing.create_and_finalize_stripe_invoice",
        lambda **_: ("in_sepa_1", "mandate_1"),
    )

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
                    json={"legal_name": "SEPA Lda"},
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

                hr_billing = await client.get("/v1/billing", headers=hr_auth)
                assert hr_billing.status_code == 403
                billing = await client.get("/v1/billing", headers=auth)
                assert billing.status_code == 200, billing.text
                assert billing.json()["has_stripe_customer"] is False
                assert "saving_amount" not in str(billing.json())

                hr_checkout = await client.post(
                    "/v1/invoices/sepa-checkout", headers=hr_auth
                )
                assert hr_checkout.status_code == 403

                checkout = await client.post(
                    "/v1/invoices/sepa-checkout", headers=auth
                )
                assert checkout.status_code == 200, checkout.text
                assert checkout.json()["url"].startswith("https://checkout.stripe.test/")

                completed = json.dumps(
                    {
                        "id": "evt_checkout",
                        "object": "event",
                        "type": "checkout.session.completed",
                        "data": {
                            "object": {
                                "id": "cs_test",
                                "customer": "cus_test",
                                "metadata": {"company_id": str(company_id)},
                            }
                        },
                    }
                ).encode()
                done = await client.post(
                    "/v1/webhooks/stripe",
                    content=completed,
                    headers={
                        "Stripe-Signature": signed_header(completed),
                        "Content-Type": "application/json",
                    },
                )
                assert done.status_code == 200, done.text
                assert done.json()["status"] == "ok"
                billing_after = await client.get("/v1/billing", headers=auth)
                assert billing_after.json()["has_stripe_customer"] is True
                assert billing_after.json()["invoicing_method"] == "STRIPE_SEPA"

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
                draft = await client.post(
                    f"/v1/ops/companies/{company_id}/invoices",
                    headers=staff_headers,
                    json={"year_month": "2026-09-01"},
                )
                assert draft.status_code == 201, draft.text
                invoice_id = draft.json()["id"]
                issued = await client.post(
                    f"/v1/ops/invoices/{invoice_id}/issue",
                    headers=staff_headers,
                )
                assert issued.status_code == 200, issued.text

                collected = await client.post(
                    f"/v1/invoices/{invoice_id}/sepa-collect",
                    headers=auth,
                )
                assert collected.status_code == 200, collected.text
                assert collected.json()["status"] == "DUE"
                assert "saving_amount" not in str(collected.json())

                failed = json.dumps(
                    {
                        "id": "evt_fail",
                        "object": "event",
                        "type": "invoice.payment_failed",
                        "data": {"object": {"id": "in_sepa_1"}},
                    }
                ).encode()
                failed_res = await client.post(
                    "/v1/webhooks/stripe",
                    content=failed,
                    headers={
                        "Stripe-Signature": signed_header(failed),
                        "Content-Type": "application/json",
                    },
                )
                assert failed_res.status_code == 200, failed_res.text
                listed = await client.get("/v1/invoices", headers=auth)
                assert listed.json()[0]["status"] == "LATE"
                assert listed.json()[0]["paid_on"] is None
                async with AsyncSessionLocal() as session:
                    pays = (
                        await session.execute(
                            select(Payment).where(Payment.invoice_id == invoice_id)
                        )
                    ).scalars().all()
                    assert pays == []

                paid = json.dumps(
                    {
                        "id": "evt_paid",
                        "object": "event",
                        "type": "invoice.paid",
                        "data": {"object": {"id": "in_sepa_1"}},
                    }
                ).encode()
                paid_res = await client.post(
                    "/v1/webhooks/stripe",
                    content=paid,
                    headers={
                        "Stripe-Signature": signed_header(paid),
                        "Content-Type": "application/json",
                    },
                )
                assert paid_res.status_code == 200, paid_res.text
                paid_list = await client.get("/v1/invoices", headers=auth)
                assert paid_list.json()[0]["status"] == "PAID"
                async with AsyncSessionLocal() as session:
                    payment = (
                        await session.execute(
                            select(Payment).where(Payment.invoice_id == invoice_id)
                        )
                    ).scalar_one()
                    assert payment.method == "STRIPE_SEPA"
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
