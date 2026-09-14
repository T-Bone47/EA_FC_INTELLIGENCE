"""API security: rate limiting, headers, request size, error hygiene,
validation, CORS/secret handling."""
from __future__ import annotations

import uuid

import pytest

from backend.tests.conftest import requires_db

pytestmark = requires_db

PASSWORD = "Test-Passw0rd!xyz"


def _signup(client):
    return client.post("/api/auth/signup", json={
        "email": f"sec-{uuid.uuid4().hex[:10]}@example.com",
        "password": PASSWORD, "display_name": "Sec"})


def test_auth_rate_limit_returns_429(client, strict_rate_limits):
    codes = [_signup(client).status_code for _ in range(6)]
    assert 429 in codes, codes
    body = client.post("/api/auth/login", json={
        "email": "whoever@example.com", "password": PASSWORD}).json()
    assert body["detail"].startswith("Rate limit exceeded")


def test_general_rate_limit_returns_429(client, strict_rate_limits):
    # health is intentionally UNLIMITED (liveness probes); protected routes are limited
    assert client.get("/api/health").status_code == 200
    codes = [client.get("/api/meta/game-versions").status_code for _ in range(9)]
    assert 429 in codes, codes


def test_rate_limit_response_has_retry_after(client, strict_rate_limits):
    for _ in range(9):
        r = client.get("/api/meta/game-versions")
        if r.status_code == 429:
            assert "retry-after" in {k.lower() for k in r.headers}
            return
    pytest.fail("expected a 429 within the limit window")


def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "x-request-id" in r.headers
    assert "geolocation=()" in r.headers["permissions-policy"]


def test_500_does_not_leak_internals():
    """A raising handler must produce a safe 500 with only a correlation id."""
    from fastapi.testclient import TestClient

    from backend.api.main import create_app
    app = create_app()

    @app.get("/api/_boom_test")
    def _boom():
        raise RuntimeError("super secret database credential: hunter2")

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/_boom_test")
    assert r.status_code == 500
    body = r.json()
    assert body["detail"] == "Internal server error."
    assert "hunter2" not in r.text
    assert "Traceback" not in r.text
    assert "request_id" in body        # correlation id for support, nothing more


def test_request_size_limit(client):
    big = {"email": f"big-{uuid.uuid4().hex[:8]}@example.com",
           "password": "A" * 2_000_000}
    r = client.post("/api/auth/signup", json=big)
    assert r.status_code in (413, 422)
    if r.status_code == 413:
        assert r.json()["detail"] == "Request body too large."


def test_sql_injection_attempt_is_inert(client):
    payload = "'; DROP TABLE game_player; --"
    r = client.get("/api/players", params={"game_version": "FC26", "q": payload})
    assert r.status_code == 200
    assert r.json()["total"] == 0
    # table still intact
    assert client.get("/api/health/ready").json()["game_players"] >= 16228


def test_validation_rejects_oversized_and_bad_types(client):
    assert client.get("/api/players", params={"game_version": "FC26",
                                              "q": "x" * 500}).status_code == 422
    assert client.get("/api/players", params={"game_version": "FC26",
                                              "ovr_min": 9999}).status_code == 422
    r = client.post("/api/recommendations", json={"game_version": "FC26",
                                                  "limit": 100000})
    assert r.status_code == 422


def test_cors_disabled_by_default(client):
    r = client.get("/api/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_no_secrets_in_responses(client):
    for path in ("/api", "/api/health", "/api/health/ready",
                 "/api/meta/reference?game_version=FC26", "/api/openapi.json"):
        text = client.get(path).text.lower()
        for needle in ("jwt_secret", "eafc_dev_only", "database_url",
                       "postgresql://", "password_hash"):
            assert needle not in text, f"{needle} leaked in {path}"


def test_openapi_does_not_expose_synthetic_data(client):
    text = client.get("/api/openapi.json").text
    assert "Fixture Player" not in text
    assert "synth-fc26" not in text


def test_production_boot_refuses_missing_jwt_secret(monkeypatch):
    """create_app() must fail fast in production without JWT_SECRET (not on
    first token use)."""
    from backend.api.main import create_app
    from backend.core.config import get_settings
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            create_app()
    finally:
        get_settings.cache_clear()


def test_method_not_allowed_and_bad_uuid(client):
    assert client.delete("/api/health").status_code == 405
    assert client.get("/api/players/not-a-uuid?game_version=FC26").status_code == 422
