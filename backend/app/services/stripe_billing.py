"""Stripe Checkout (SEPA mandate) and Invoice collection (DEV-842)."""

from __future__ import annotations

import json
from typing import Any

import stripe
from fastapi import HTTPException, status

from app.settings import get_env_name, get_stripe_secret_key, get_stripe_webhook_secret

_PAID_EVENTS = {"invoice.paid", "invoice.payment_succeeded"}
_FAILED_EVENTS = {"invoice.payment_failed", "invoice.overdue"}
_CHECKOUT_COMPLETED = "checkout.session.completed"


def paid_event_types() -> set[str]:
    return set(_PAID_EVENTS)


def failed_event_types() -> set[str]:
    return set(_FAILED_EVENTS)


def checkout_completed_type() -> str:
    return _CHECKOUT_COMPLETED


def _require_stripe() -> None:
    key = get_stripe_secret_key()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured.",
        )
    stripe.api_key = key


def parse_stripe_event(payload: bytes, signature: str | None) -> dict[str, Any]:
    """Verify Stripe-Signature HMAC when a webhook secret is set.

    DEV without a secret still accepts JSON so local stacks can run without Stripe CLI.
    Staging/prod fail closed if the secret is missing. Header equality is not accepted.
    """
    secret = get_stripe_webhook_secret()
    env = get_env_name().upper()
    if not secret:
        if env != "DEV":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stripe webhook secret is not configured.",
            )
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON."
            ) from exc
        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON."
            )
        return parsed
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Stripe-Signature."
        )
    try:
        stripe.Webhook.construct_event(payload, signature, secret)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Stripe signature."
        ) from exc
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON."
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON."
        )
    return parsed


def ensure_stripe_customer(
    *, existing_id: str | None, name: str, metadata: dict[str, str]
) -> str:
    _require_stripe()
    if existing_id:
        return existing_id
    customer = stripe.Customer.create(name=name, metadata=metadata)
    customer_id = getattr(customer, "id", None)
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe did not return a customer id.",
        )
    return str(customer_id)


def create_sepa_setup_session(
    *,
    customer_id: str,
    success_url: str,
    cancel_url: str,
    metadata: dict[str, str],
) -> str:
    _require_stripe()
    session = stripe.checkout.Session.create(
        mode="setup",
        customer=customer_id,
        payment_method_types=["sepa_debit"],
        success_url=success_url,
        cancel_url=cancel_url,
        currency="eur",
        metadata=metadata,
    )
    url = getattr(session, "url", None)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe did not return a checkout URL.",
        )
    return str(url)


def create_and_finalize_stripe_invoice(
    *,
    customer_id: str,
    amount_cents: int,
    currency: str,
    description: str,
    metadata: dict[str, str],
) -> tuple[str, str | None]:
    """Create a Stripe Invoice and finalize it so SEPA collection can run."""
    _require_stripe()
    code = currency.lower()
    invoice = stripe.Invoice.create(
        customer=customer_id,
        collection_method="charge_automatically",
        auto_advance=True,
        currency=code,
        metadata=metadata,
    )
    stripe_invoice_id = getattr(invoice, "id", None)
    if not stripe_invoice_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe did not return an invoice id.",
        )
    stripe.InvoiceItem.create(
        customer=customer_id,
        invoice=stripe_invoice_id,
        amount=amount_cents,
        currency=code,
        description=description,
    )
    finalized = stripe.Invoice.finalize_invoice(stripe_invoice_id, auto_advance=True)
    mandate_id = None
    default_pm = getattr(finalized, "default_payment_method", None)
    if isinstance(default_pm, str):
        try:
            method = stripe.PaymentMethod.retrieve(default_pm)
            sepa = getattr(method, "sepa_debit", None)
            mandate_id = getattr(sepa, "mandate", None) if sepa is not None else None
        except Exception:
            mandate_id = None
    return str(getattr(finalized, "id", stripe_invoice_id)), (
        str(mandate_id) if mandate_id else None
    )
