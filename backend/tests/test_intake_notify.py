"""Welcome mail, Slack text, and the booking token. No Postgres."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.services.intake_notify import (
    format_meeting,
    issue_meeting_token,
    read_meeting_token,
    welcome_message,
)


def test_meeting_token_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTAKE_NOTIFY_SECRET", "test-secret")
    intake_id = uuid.uuid4()
    token = issue_meeting_token(intake_id)
    assert token is not None
    assert read_meeting_token(token) == intake_id
    assert read_meeting_token(token + "x") is None


def test_welcome_includes_lisbon_time() -> None:
    starts = datetime(2026, 11, 9, 15, 0, tzinfo=UTC)
    label = format_meeting(starts, "en")
    assert "15:00" in label or "14:00" in label
    subject, text, rich = welcome_message(
        legal_name="Waiting Lda",
        locale="pt",
        meeting_label=format_meeting(starts, "pt"),
    )
    assert "guardada" in subject
    assert "Waiting Lda" in text
    assert "Waiting Lda" in rich
    assert "não pode entrar" not in text
    assert "Anthony-fl.png" in rich
    assert "https://anteater.pt/" in rich
    assert "<script" not in rich
    en_subject, en_text, _en_rich = welcome_message(
        legal_name="Waiting Lda",
        locale="en",
        meeting_label=format_meeting(starts, "en"),
    )
    assert "meeting" in en_subject.lower()
    assert "cannot sign in" not in en_text
    assert "Lisbon" in en_text
