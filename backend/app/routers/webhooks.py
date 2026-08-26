"""Stripe webhook → PAID (DEV-839). SEPA collection itself is DEV-842."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.billing import apply_stripe_paid
from app.settings import get_stripe_webhook_secret

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def post_stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> dict[str, str]:
    secret = get_stripe_webhook_secret()
    if secret and stripe_signature != secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Stripe signature."
        )
    payload = await request.json()
    event_type = payload.get("type")
    obj = (payload.get("data") or {}).get("object") or {}
    stripe_id = obj.get("id")
    if event_type not in {"invoice.paid", "invoice.payment_succeeded"} or not stripe_id:
        return {"status": "ignored"}
    await apply_stripe_paid(db, stripe_id, payload)
    await db.commit()
    return {"status": "ok"}
