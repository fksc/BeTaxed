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


@dataclass(frozen=True)
class FirebaseUserRecord:
    uid: str
    email: str
    has_password: bool


def get_user_by_email(email: str) -> FirebaseUserRecord | None:
    """Look up a Firebase Auth user. Tests patch this."""
    try:
        from firebase_admin import auth as firebase_auth

        _get_firebase_app()
        record = firebase_auth.get_user_by_email(email.strip().lower())
    except HTTPException:
        raise
    except Exception as exc:
        from firebase_admin.auth import UserNotFoundError

        if isinstance(exc, UserNotFoundError):
            return None
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase user lookup failed.",
        ) from exc
    return FirebaseUserRecord(
        uid=str(record.uid),
        email=str(record.email or email).strip().lower(),
        has_password=bool(getattr(record, "password_hash", None)),
    )


def create_email_user(
    email: str, display_name: str | None = None
) -> FirebaseUserRecord:
    """Create a Firebase user with no password (set on invite accept). Tests patch this."""
    normalized = email.strip().lower()
    name = display_name.strip() if display_name and display_name.strip() else None
    try:
        from firebase_admin import auth as firebase_auth

        _get_firebase_app()
        kwargs: dict = {"email": normalized}
        if name:
            kwargs["display_name"] = name
        record = firebase_auth.create_user(**kwargs)
    except HTTPException:
        raise
    except Exception as exc:
        from firebase_admin.auth import EmailAlreadyExistsError

        if isinstance(exc, EmailAlreadyExistsError):
            existing = get_user_by_email(normalized)
            if existing is not None:
                if name:
                    set_user_display_name(existing.uid, name)
                return existing
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase user create failed.",
        ) from exc
    return FirebaseUserRecord(
        uid=str(record.uid),
        email=str(record.email or normalized).strip().lower(),
        has_password=False,
    )


def ensure_password_user(email: str, password: str) -> FirebaseUserRecord:
    """Create or update a Firebase email/password user. Tests patch this."""
    normalized = email.strip().lower()
    existing = get_user_by_email(normalized)
    try:
        from firebase_admin import auth as firebase_auth

        _get_firebase_app()
        if existing is None:
            record = firebase_auth.create_user(
                email=normalized,
                password=password,
                email_verified=True,
            )
            return FirebaseUserRecord(
                uid=str(record.uid),
                email=str(record.email or normalized).strip().lower(),
                has_password=True,
            )
        firebase_auth.update_user(
            existing.uid, password=password, email_verified=True
        )
        return FirebaseUserRecord(
            uid=existing.uid, email=existing.email, has_password=True
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase password user upsert failed.",
        ) from exc


def set_user_password(uid: str, password: str) -> None:
    """Set or replace the Firebase password. Tests patch this."""
    try:
        from firebase_admin import auth as firebase_auth

        _get_firebase_app()
        firebase_auth.update_user(uid, password=password, email_verified=True)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase password update failed.",
        ) from exc


def set_user_display_name(uid: str, display_name: str) -> None:
    """Set Firebase displayName. Tests patch this."""
    name = display_name.strip()
    if not name:
        return
    try:
        from firebase_admin import auth as firebase_auth

        _get_firebase_app()
        firebase_auth.update_user(uid, display_name=name)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase display name update failed.",
        ) from exc
