"""Invite email (DEV-852). Resend or Brevo when keyed; otherwise link-only."""

from __future__ import annotations

import logging
import re

import httpx

from app.settings import (
    get_brevo_api_key,
    get_email_from,
    get_email_provider,
    get_resend_api_key,
)

logger = logging.getLogger(__name__)

_FROM_RE = re.compile(r"^(?P<name>.+?)\s*<(?P<email>[^>]+)>$")


class InviteMailError(Exception):
    """Provider send failed."""


def _parse_from(raw: str) -> tuple[str | None, str]:
    match = _FROM_RE.match(raw.strip())
    if match:
        return match.group("name").strip().strip('"'), match.group("email").strip()
    return None, raw.strip()


def send_invite_email(*, to_email: str, subject: str, body: str) -> str:
    """Send invite mail. Returns ``resend``, ``brevo``, or ``link_only``.

    Tests patch this. Raises InviteMailError on provider failure.
    """
    provider = get_email_provider()
    if provider is None:
        logger.info("invite mail skipped (no EMAIL_PROVIDER / API key) to=%s", to_email)
        return "link_only"
    if provider == "resend":
        _send_resend(to_email, subject, body)
        return "resend"
    if provider == "brevo":
        _send_brevo(to_email, subject, body)
        return "brevo"
    raise InviteMailError(f"Unknown EMAIL_PROVIDER {provider}.")


def _send_resend(to_email: str, subject: str, body: str) -> None:
    key = get_resend_api_key()
    if not key:
        raise InviteMailError("RESEND_API_KEY is not set.")
    name, email = _parse_from(get_email_from())
    payload = {
        "from": f"{name} <{email}>" if name else email,
        "to": [to_email],
        "subject": subject,
        "text": body,
    }
    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
    except Exception as exc:
        logger.warning("resend invite mail failed to=%s", to_email, exc_info=True)
        raise InviteMailError(str(exc)) from exc
    if response.status_code >= 400:
        raise InviteMailError(f"Resend HTTP {response.status_code}: {response.text[:300]}")


def _send_brevo(to_email: str, subject: str, body: str) -> None:
    key = get_brevo_api_key()
    if not key:
        raise InviteMailError("BREVO_API_KEY is not set.")
    name, email = _parse_from(get_email_from())
    sender: dict[str, str] = {"email": email}
    if name:
        sender["name"] = name
    payload = {
        "sender": sender,
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body,
    }
    try:
        response = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": key,
                "accept": "application/json",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
    except Exception as exc:
        logger.warning("brevo invite mail failed to=%s", to_email, exc_info=True)
        raise InviteMailError(str(exc)) from exc
    if response.status_code >= 400:
        raise InviteMailError(f"Brevo HTTP {response.status_code}: {response.text[:300]}")
