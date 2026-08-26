"""Stripe webhook HMAC (DEV-842). No Postgres required."""

from __future__ import annotations

import asyncio
import json
import time

import pytest
import stripe
from httpx import ASGITransport, AsyncClient

from app.main import app

_SECRET = "whsec_test_dev_842"


def signed_header(payload: bytes, secret: str = _SECRET) -> str:
    ts = int(time.time())
    signed = f"{ts}.{payload.decode('utf-8')}"
    digest = stripe.WebhookSignature._compute_signature(signed, secret)
    return f"t={ts},v1={digest}"


def _payload(event_type: str, object_id: str = "in_test") -> bytes:
    return json.dumps(
        {
            "id": "evt_test",
            "object": "event",
            "type": event_type,
            "data": {"object": {"id": object_id}},
        }
    ).encode()


def test_plain_secret_header_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", _SECRET)
    monkeypatch.setenv("ENV", "DEV")
    payload = _payload("invoice.paid")

    async def body() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/webhooks/stripe",
                content=payload,
                headers={
                    "Stripe-Signature": _SECRET,
                    "Content-Type": "application/json",
                },
            )
            assert response.status_code == 400
            assert response.json()["detail"] == "Invalid Stripe signature."

    asyncio.run(body())


def test_valid_hmac_unrelated_event_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", _SECRET)
    monkeypatch.setenv("ENV", "DEV")
    payload = _payload("customer.created", "cus_1")
    header = signed_header(payload)

    async def body() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/webhooks/stripe",
                content=payload,
                headers={
                    "Stripe-Signature": header,
                    "Content-Type": "application/json",
                },
            )
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "ignored"

    asyncio.run(body())


def test_missing_signature_rejected_when_secret_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", _SECRET)
    monkeypatch.setenv("ENV", "DEV")
    payload = _payload("invoice.paid")

    async def body() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/webhooks/stripe",
                content=payload,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 400

    asyncio.run(body())
