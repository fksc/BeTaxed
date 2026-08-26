"""Stripe webhook → PAID / LATE (DEV-842). HMAC verified when a secret is set."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request

from app.db import AsyncSessionLocal
from app.services.billing import (
    apply_checkout_completed,
    apply_stripe_failed,
    apply_stripe_paid,
)
from app.services.stripe_billing import (
    checkout_completed_type,
    failed_event_types,
    paid_event_types,
    parse_stripe_event,
)

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def post_stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> dict[str, str]:
    payload = await request.body()
    event = parse_stripe_event(payload, stripe_signature)
    event_type = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}
    stripe_id = obj.get("id")
    if (
        event_type not in paid_event_types()
        and event_type not in failed_event_types()
        and event_type != checkout_completed_type()
    ):
        return {"status": "ignored"}
    async with AsyncSessionLocal() as db:
        if event_type in paid_event_types():
            if not stripe_id:
                return {"status": "ignored"}
            invoice = await apply_stripe_paid(db, str(stripe_id), event)
            if invoice is None:
                return {"status": "ignored"}
        elif event_type in failed_event_types():
            if not stripe_id:
                return {"status": "ignored"}
            invoice = await apply_stripe_failed(db, str(stripe_id), event)
            if invoice is None:
                return {"status": "ignored"}
        elif event_type == checkout_completed_type():
            company = await apply_checkout_completed(db, event)
            if company is None:
                return {"status": "ignored"}
        await db.commit()
    return {"status": "ok"}
