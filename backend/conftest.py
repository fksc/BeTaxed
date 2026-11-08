"""Root pytest configuration.

Tests that require a live PostgreSQL connection are marked via the ``db_session``
fixture. When no database is reachable those tests are skipped.
"""

import os
import socket
from urllib.parse import urlparse

import pytest

_DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://betaxed:betaxed_dev@localhost:5433/betaxed"
)
# App default. Tests that open AsyncSessionLocal without the db_session fixture use this.
_APP_DATABASE_URL = (
    "postgresql+asyncpg://betaxed:betaxed_dev@localhost:5434/betaxed"
)


def _postgres_host_port(raw: str) -> tuple[str, int]:
    parsed = urlparse(raw.replace("postgresql+asyncpg://", "postgresql://", 1))
    return parsed.hostname or "127.0.0.1", parsed.port or 5432


def _postgres_reachable(raw: str) -> bool:
    host, port = _postgres_host_port(raw)
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _skip_when_down(items, raw: str, predicate) -> None:
    if _postgres_reachable(raw):
        return
    host, port = _postgres_host_port(raw)
    skip = pytest.mark.skip(
        reason=f"No PostgreSQL reachable at {host}:{port} — skipping DB tests"
    )
    for item in items:
        if predicate(item):
            item.add_marker(skip)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "needs_app_db: test opens the app database directly",
    )


def pytest_collection_modifyitems(config, items):
    session_url = os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL).strip()
    app_url = os.environ.get("DATABASE_URL", _APP_DATABASE_URL).strip()
    _skip_when_down(
        items,
        session_url,
        lambda item: "db_session" in getattr(item, "fixturenames", []),
    )
    _skip_when_down(
        items,
        app_url,
        lambda item: item.get_closest_marker("needs_app_db") is not None,
    )


@pytest.fixture(autouse=True)
def _quiet_verbose(monkeypatch: pytest.MonkeyPatch) -> None:
    """Public teaser tests must not inherit VERBOSE=TRUE from a local .env."""
    monkeypatch.setenv("VERBOSE", "FALSE")
