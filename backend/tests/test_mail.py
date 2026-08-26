"""Invite mail provider selection (DEV-852). No network."""

from __future__ import annotations

import httpx
import pytest

from app.services.mail import InviteMailError, send_invite_email
from app.settings import get_email_provider


def test_email_provider_none_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMAIL_PROVIDER", raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    assert get_email_provider() is None
    assert send_invite_email(to_email="a@b.test", subject="s", body="b") == "link_only"


def test_resend_when_key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMAIL_PROVIDER", raising=False)
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("EMAIL_FROM", "BeTaxed <hello@betaxed.test>")
    monkeypatch.delenv("BREVO_API_KEY", raising=False)

    def fake_post(url: str, **kwargs):
        assert url == "https://api.resend.com/emails"
        assert kwargs["headers"]["Authorization"] == "Bearer re_test"
        assert kwargs["json"]["to"] == ["a@b.test"]
        assert kwargs["json"]["from"] == "BeTaxed <hello@betaxed.test>"
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"id": "ok"}, request=request)

    monkeypatch.setattr("app.services.mail.httpx.post", fake_post)
    assert get_email_provider() == "resend"
    assert send_invite_email(to_email="a@b.test", subject="s", body="hello") == "resend"


def test_brevo_when_provider_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.setenv("BREVO_API_KEY", "xb-test")
    monkeypatch.setenv("EMAIL_FROM", "hello@betaxed.test")

    def fake_post(url: str, **kwargs):
        assert url == "https://api.brevo.com/v3/smtp/email"
        assert kwargs["headers"]["api-key"] == "xb-test"
        assert kwargs["json"]["sender"]["email"] == "hello@betaxed.test"
        request = httpx.Request("POST", url)
        return httpx.Response(201, json={"messageId": "ok"}, request=request)

    monkeypatch.setattr("app.services.mail.httpx.post", fake_post)
    assert send_invite_email(to_email="a@b.test", subject="s", body="hello") == "brevo"


def test_resend_http_error_is_mail_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_test")

    def fake_post(url: str, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(401, json={"message": "no"}, request=request)

    monkeypatch.setattr("app.services.mail.httpx.post", fake_post)
    with pytest.raises(InviteMailError):
        send_invite_email(to_email="a@b.test", subject="s", body="hello")
