"""Shared fixtures. Tests depend on production code only (§14)."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def db_available() -> bool:
    try:
        from backend.core.db import query_one
        return query_one("SELECT 1 AS ok") is not None
    except Exception:
        return False


requires_db = pytest.mark.skipif(not db_available(),
                                 reason="PostgreSQL not reachable")


@pytest.fixture(autouse=True)
def _relax_rate_limits():
    """Tests share one client IP; relax limits so suites don't 429 themselves.
    Security tests re-tighten explicitly via `strict_rate_limits`."""
    from backend.api import deps
    from backend.core.config import get_settings
    s = get_settings()
    old = (s.rate_limit_auth_per_minute, s.rate_limit_requests_per_minute)
    s.rate_limit_auth_per_minute = 1_000_000
    s.rate_limit_requests_per_minute = 1_000_000
    deps.rate_limiter._buckets.clear()
    yield
    s.rate_limit_auth_per_minute, s.rate_limit_requests_per_minute = old


@pytest.fixture()
def strict_rate_limits():
    from backend.api import deps
    from backend.core.config import get_settings
    s = get_settings()
    old = (s.rate_limit_auth_per_minute, s.rate_limit_requests_per_minute)
    s.rate_limit_auth_per_minute = 3
    s.rate_limit_requests_per_minute = 5
    deps.rate_limiter._buckets.clear()
    yield s
    s.rate_limit_auth_per_minute, s.rate_limit_requests_per_minute = old
    deps.rate_limiter._buckets.clear()


@pytest.fixture(scope="session")
def app():
    from backend.api.main import create_app
    return create_app()


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_client(app):
    """A SEPARATE TestClient authenticated as a fresh unique user.
    Never mutate the shared `client` — tests that request both fixtures
    need one anonymous and one authenticated view."""
    from fastapi.testclient import TestClient
    email = f"test-{uuid.uuid4().hex[:10]}@example.com"
    with TestClient(app) as c:
        r = c.post("/api/auth/signup", json={
            "email": email, "password": "Test-Passw0rd!xyz",
            "display_name": "Tester"})
        assert r.status_code == 201, r.text
        c.headers.update(
            {"Authorization": f"Bearer {r.json()['access_token']}"})
        yield c


@pytest.fixture()
def fresh_email():
    return f"test-{uuid.uuid4().hex[:10]}@example.com"
