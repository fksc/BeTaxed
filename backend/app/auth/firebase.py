"""Firebase ID-token verification. Tests patch `verify_id_token`.

Local and cloud-agent DEV uses the Auth emulator (`FIREBASE_AUTH_EMULATOR_HOST`).
Staging/prod verify against a real project with Application Default Credentials.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status

from app.settings import get_firebase_auth_emulator_host, get_firebase_project_id


@dataclass(frozen=True)
class FirebaseIdentity:
    uid: str
    email: str


_firebase_app = None


def _get_firebase_app():
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    import firebase_admin
    from firebase_admin import credentials

    if firebase_admin._apps:
        _firebase_app = firebase_admin.get_app()
        return _firebase_app

    emulator_host = get_firebase_auth_emulator_host()
    project_id = get_firebase_project_id()
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase is not configured (FIREBASE_PROJECT_ID).",
        )

    if emulator_host:
        from google.auth.credentials import AnonymousCredentials

        _firebase_app = firebase_admin.initialize_app(
            AnonymousCredentials(),
            {"projectId": project_id},
        )
        return _firebase_app

    cred = credentials.ApplicationDefault()
    _firebase_app = firebase_admin.initialize_app(
        cred, {"projectId": project_id}
    )
    return _firebase_app


def verify_id_token(id_token: str) -> FirebaseIdentity:
    """Verify a Firebase ID token. Raises 401 on failure."""
    if not id_token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )
    try:
        from firebase_admin import auth as firebase_auth

        _get_firebase_app()
        decoded = firebase_auth.verify_id_token(id_token)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase ID token.",
        ) from exc

    uid = decoded.get("uid") or decoded.get("sub")
    email = decoded.get("email")
    if not uid or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token missing uid or email.",
        )
    return FirebaseIdentity(uid=str(uid), email=str(email).strip().lower())
