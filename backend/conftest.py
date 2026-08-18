"""Root pytest configuration.

Tests that require a live PostgreSQL connection are marked via the ``db_session``
fixture. When no database is reachable those tests are skipped.
"""

import os
import socket
from urllib.parse import urlparse

import pytest

_DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://betaxed:betaxed_dev@localhost:5432/betaxed"
)


def _postgres_host_port() -> tuple[str, int]:
    raw = os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL).strip()
    parsed = urlparse(raw.replace("postgresql+asyncpg://", "postgresql://", 1))
    return parsed.hostname or "127.0.0.1", parsed.port or 5432


def _postgres_reachable() -> bool:
    host, port = _postgres_host_port()
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(config, items):
    if _postgres_reachable():
        return
    host, port = _postgres_host_port()
    skip = pytest.mark.skip(
        reason=f"No PostgreSQL reachable at {host}:{port} — skipping DB tests"
    )
    for item in items:
        if "db_session" in getattr(item, "fixturenames", []):
            item.add_marker(skip)
