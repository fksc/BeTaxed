"""Root pytest configuration.

Tests that require a live PostgreSQL connection are marked via the ``db_session``
fixture. When no database is reachable those tests are skipped.
"""

import socket

import pytest


def _postgres_reachable(host: str = "127.0.0.1", port: int = 5432) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(config, items):
    if _postgres_reachable():
        return
    skip = pytest.mark.skip(reason="No PostgreSQL reachable at localhost:5432 — skipping DB tests")
    for item in items:
        if "db_session" in getattr(item, "fixturenames", []):
            item.add_marker(skip)
