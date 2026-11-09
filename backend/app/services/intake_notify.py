"""Welcome mail and Slack when a public intake becomes an inactive workspace."""

from __future__ import annotations

import hashlib
import hmac
import html
import logging
import time
import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx

from app.services.mail import InviteMailError, send_invite_email
from app.settings import get_intake_notify_secret, get_slack_webhook_url

logger = logging.getLogger(__name__)

_SITE = "https://anteater.pt"
_LOGO = f"{_SITE}/for_og_white.png"
_ANTHONY = f"{_SITE}/Anthony-fl.png"
_LISBON = ZoneInfo("Europe/Lisbon")
_TOKEN_TTL_SECONDS = 48 * 3600
_WEEKDAYS_PT = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)
_MONTHS_PT = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def issue_meeting_token(intake_id: uuid.UUID) -> str | None:
    secret = get_intake_notify_secret()
    if not secret:
        return None
    exp = int(time.time()) + _TOKEN_TTL_SECONDS
    body = f"{intake_id}.{exp}"
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def read_meeting_token(token: str) -> uuid.UUID | None:
    secret = get_intake_notify_secret()
    if not secret:
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    intake_raw, exp_raw, sig = parts
    body = f"{intake_raw}.{exp_raw}"
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        exp = int(exp_raw)
        intake_id = uuid.UUID(intake_raw)
    except ValueError:
        return None
    if exp < int(time.time()):
        return None
    return intake_id


def format_meeting(starts_at: datetime, locale: str) -> str:
    local = starts_at.astimezone(_LISBON)
    if locale == "en":
        return f"{local.strftime('%A')}, {local.day} {local.strftime('%B')} {local.year} at {local:%H:%M}"
    weekday = _WEEKDAYS_PT[local.weekday()]
    month = _MONTHS_PT[local.month - 1]
    return f"{weekday}, {local.day} de {month} de {local.year} às {local:%H:%M}"


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def notify_workspace_saved(
    *,
    to_email: str | None,
    legal_name: str,
    locale: str,
    meeting_starts_at: datetime | None,
) -> None:
    """Best-effort. A missed send does not undo the workspace."""
    label = format_meeting(meeting_starts_at, locale) if meeting_starts_at else None
    if to_email:
        subject, text, rich = welcome_message(legal_name=legal_name, locale=locale, meeting_label=label)
        _send(to_email, subject, text, rich)
    _slack(
        "\n".join(
            [
                "New inactive workspace",
                f"Company: {legal_name}",
                f"Email: {to_email or 'unknown'}",
                "Status: inactive until activation",
                f"Meeting: {label or 'not booked yet'}",
            ]
        )
    )


def notify_meeting_booked(
    *,
    to_email: str | None,
    legal_name: str,
    locale: str,
    meeting_starts_at: datetime,
) -> None:
    label = format_meeting(meeting_starts_at, locale)
    if to_email:
        subject, text, rich = meeting_message(legal_name=legal_name, locale=locale, meeting_label=label)
        _send(to_email, subject, text, rich)
    _slack(
        "\n".join(
            [
                "Meeting booked",
                f"Company: {legal_name}",
                f"Email: {to_email or 'unknown'}",
                f"When: {label}",
            ]
        )
    )


def _site(locale: str) -> str:
    return f"{_SITE}/en" if locale == "en" else f"{_SITE}/"


def welcome_message(*, legal_name: str, locale: str, meeting_label: str | None) -> tuple[str, str, str]:
    safe_name = html.escape(legal_name)
    safe_when = html.escape(meeting_label) if meeting_label else ""
    site = _site(locale)
    if locale == "en":
        subject = "Your Anteater meeting is saved"
        when_text = f"We have you down for {meeting_label} (Lisbon time)." if meeting_label else ""
        text = (
            f"Thank you for booking time with Anteater. "
            f"The reading for {legal_name} is stored securely, and it stays that way until we meet.\n"
            f"{when_text}\n"
            "What you shared is encrypted and kept only so we can prepare for that conversation. "
            "At the meeting we will walk through the estimate with you and decide the next step together. "
            "We are looking forward to it.\n"
            f"{site}\n"
        )
        when_html = (
            f"<p style=\"margin:20px 0;padding:16px 18px;border-radius:12px;background:#241018;color:#f4f1ec\">"
            f"We have you down for <strong>{safe_when}</strong>, Lisbon time.</p>"
            if meeting_label
            else ""
        )
        body = (
            f"<p>Thank you for booking time with Anteater. "
            f"The reading for <strong>{safe_name}</strong> is stored securely, and it stays that way until we meet.</p>"
            f"{when_html}"
            "<p>What you shared is encrypted and kept only so we can prepare for that conversation. "
            "At the meeting we will walk through the estimate with you and decide the next step together. "
            "We are looking forward to it.</p>"
        )
        link = "Visit anteater.pt"
    else:
        subject = "A sua reunião com a Anteater ficou guardada"
        when_text = f"Ficou marcado para {meeting_label} (hora de Lisboa)." if meeting_label else ""
        text = (
            f"Obrigado por marcar uma hora com a Anteater. "
            f"A leitura de {legal_name} ficou guardada em segurança, e assim permanece até nos encontrarmos.\n"
            f"{when_text}\n"
            "O que partilhou está cifrado e fica connosco apenas para prepararmos essa conversa. "
            "Na reunião percorremos a estimativa consigo e decidimos o passo seguinte. "
            "Estamos ansiosos por o conhecer.\n"
            f"{site}\n"
        )
        when_html = (
            f"<p style=\"margin:20px 0;padding:16px 18px;border-radius:12px;background:#241018;color:#f4f1ec\">"
            f"Ficou marcado para <strong>{safe_when}</strong>, hora de Lisboa.</p>"
            if meeting_label
            else ""
        )
        body = (
            f"<p>Obrigado por marcar uma hora com a Anteater. "
            f"A leitura de <strong>{safe_name}</strong> ficou guardada em segurança, e assim permanece até nos encontrarmos.</p>"
            f"{when_html}"
            "<p>O que partilhou está cifrado e fica connosco apenas para prepararmos essa conversa. "
            "Na reunião percorremos a estimativa consigo e decidimos o passo seguinte. "
            "Estamos ansiosos por o conhecer.</p>"
        )
        link = "Visitar anteater.pt"
    return subject, text, _wrap(body, site=site, link_label=link)


def meeting_message(*, legal_name: str, locale: str, meeting_label: str) -> tuple[str, str, str]:
    safe_name = html.escape(legal_name)
    safe_when = html.escape(meeting_label)
    site = _site(locale)
    if locale == "en":
        subject = "Your Anteater meeting time"
        text = (
            f"The meeting for {legal_name} is now {meeting_label} (Lisbon time). "
            "What you shared stays securely stored until we meet.\n"
            f"{site}\n"
        )
        body = (
            f"<p>The meeting for <strong>{safe_name}</strong> is now "
            f"<strong>{safe_when}</strong>, Lisbon time.</p>"
            "<p>What you shared stays securely stored until we meet. "
            "We will walk through the estimate with you then.</p>"
        )
        link = "Visit anteater.pt"
    else:
        subject = "A hora da sua reunião com a Anteater"
        text = (
            f"A reunião de {legal_name} ficou para {meeting_label} (hora de Lisboa). "
            "O que partilhou permanece guardado em segurança até nos encontrarmos.\n"
            f"{site}\n"
        )
        body = (
            f"<p>A reunião de <strong>{safe_name}</strong> ficou para "
            f"<strong>{safe_when}</strong>, hora de Lisboa.</p>"
            "<p>O que partilhou permanece guardado em segurança até nos encontrarmos. "
            "Percorremos a estimativa consigo nessa altura.</p>"
        )
        link = "Visitar anteater.pt"
    return subject, text, _wrap(body, site=site, link_label=link)


def _wrap(body: str, *, site: str, link_label: str) -> str:
    safe_site = html.escape(site, quote=True)
    safe_link = html.escape(link_label)
    return (
        "<div style=\"font-family:Georgia,serif;background:#0c0b0c;padding:32px;color:#f4f1ec\">"
        "<div style=\"max-width:520px;margin:0 auto;background:#171417;border-radius:16px;padding:32px\">"
        f"<p style=\"margin:0 0 20px\"><a href=\"{safe_site}\">"
        f"<img src=\"{_LOGO}\" alt=\"Anteater\" width=\"200\" style=\"display:block;border:0;max-width:200px;height:auto\"/>"
        "</a></p>"
        f"<p style=\"margin:0 0 20px\"><img src=\"{_ANTHONY}\" alt=\"Anthony\" width=\"220\" "
        "style=\"display:block;border:0;border-radius:16px;max-width:220px;height:auto\"/></p>"
        f"{body}"
        f"<p style=\"margin:28px 0 0\"><a href=\"{safe_site}\" "
        "style=\"color:#f4f1ec;background:#88375c;text-decoration:none;border-radius:999px;"
        f"padding:12px 18px;display:inline-block\">{safe_link}</a></p>"
        "</div></div>"
    )


def _send(to_email: str, subject: str, text: str, rich: str) -> None:
    try:
        send_invite_email(to_email=to_email, subject=subject, body=text, html=rich)
    except InviteMailError:
        logger.warning("workspace mail failed to=%s", to_email)


def _slack(text: str) -> None:
    url = get_slack_webhook_url()
    if not url:
        logger.info("slack skipped (SLACK_WEBHOOK_URL unset)")
        return
    try:
        response = httpx.post(url, json={"text": text}, timeout=10)
    except Exception:
        logger.warning("slack webhook failed")
        return
    if response.status_code >= 400:
        logger.warning("slack webhook HTTP %s", response.status_code)
