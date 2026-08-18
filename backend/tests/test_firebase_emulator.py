"""Firebase Auth emulator token verify (DEV-829). No Postgres required."""

from __future__ import annotations

import base64
import json
import time

import firebase_admin
import pytest

from app.auth import firebase as firebase_mod
from app.settings import get_firebase_auth_emulator_host, get_firebase_project_id


def _b64url(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _emulator_id_token(uid: str, email: str, project_id: str = "demo-betaxed") -> str:
    now = int(time.time())
    header = {"alg": "none", "typ": "JWT"}
    body = {
        "iss": f"https://securetoken.google.com/{project_id}",
        "aud": project_id,
        "auth_time": now,
        "user_id": uid,
        "sub": uid,
        "iat": now,
        "exp": now + 3600,
        "email": email,
        "email_verified": True,
        "firebase": {"sign_in_provider": "password"},
    }
    return f"{_b64url(header)}.{_b64url(body)}."


@pytest.fixture
def emulator_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "demo-betaxed")
    get_firebase_auth_emulator_host.cache_clear()
    get_firebase_project_id.cache_clear()
    firebase_mod._firebase_app = None
    for app in list(firebase_admin._apps.values()):
        firebase_admin.delete_app(app)
    yield
    firebase_mod._firebase_app = None
    for app in list(firebase_admin._apps.values()):
        firebase_admin.delete_app(app)
    get_firebase_auth_emulator_host.cache_clear()
    get_firebase_project_id.cache_clear()


def test_emulator_verifies_unsigned_id_token(emulator_env) -> None:
    token = _emulator_id_token("uid-hr", "hr@acme.example")
    identity = firebase_mod.verify_id_token(token)
    assert identity.uid == "uid-hr"
    assert identity.email == "hr@acme.example"
