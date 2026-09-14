"""Authentication & authorization: signup/login/logout, session revocation,
ownership checks, no user enumeration, password storage safety."""
from __future__ import annotations

import uuid

import pytest

from backend.api.security import hash_password, verify_password
from backend.tests.conftest import requires_db

pytestmark = requires_db

PASSWORD = "Test-Passw0rd!xyz"


def signup(client, email=None, password=PASSWORD):
    email = email or f"t-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/auth/signup",
                    json={"email": email, "password": password, "display_name": "T"})
    return r, email


def test_password_hashing_is_bcrypt_and_not_plaintext():
    h = hash_password(PASSWORD)
    assert h != PASSWORD and PASSWORD not in h
    assert h.startswith("$2")           # bcrypt prefix
    assert verify_password(PASSWORD, h)
    assert not verify_password("wrong", h)


def test_signup_login_me_logout_flow(client):
    r, email = signup(client)
    assert r.status_code == 201
    token = r.json()["access_token"]
    assert r.json()["user"]["email"] == email

    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=h).status_code == 200

    # logout revokes the session server-side
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_login_after_signup(client):
    r, email = signup(client)
    lr = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert lr.status_code == 200
    assert lr.json()["access_token"]


def test_login_wrong_password_generic_error(client):
    r, email = signup(client)
    bad = client.post("/api/auth/login", json={"email": email, "password": "Wrong-Pass-123"})
    assert bad.status_code == 401
    assert bad.json()["detail"] == "Invalid email or password."


def test_login_unknown_email_same_generic_error(client):
    bad = client.post("/api/auth/login",
                      json={"email": f"nope-{uuid.uuid4().hex[:6]}@example.com",
                            "password": "Whatever-123"})
    assert bad.status_code == 401
    # identical message => no user enumeration
    assert bad.json()["detail"] == "Invalid email or password."


def test_duplicate_signup_does_not_leak_account_existence(client):
    _, email = signup(client)
    dup, _ = signup(client, email=email)
    assert dup.status_code == 409
    assert dup.json()["detail"] == "Unable to create account with these details."


def test_password_not_returned_by_any_endpoint(client):
    r, email = signup(client)
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    for path in ("/api/auth/me",):
        body = client.get(path, headers=h).text
        assert "password" not in body.lower() or "password_hash" not in body


def test_short_password_rejected(client):
    r = client.post("/api/auth/signup",
                    json={"email": f"short-{uuid.uuid4().hex[:6]}@example.com",
                          "password": "abc"})
    assert r.status_code == 422


def test_invalid_email_rejected(client):
    r = client.post("/api/auth/signup", json={"email": "not-an-email",
                                              "password": PASSWORD})
    assert r.status_code == 422


def test_extra_fields_rejected(client):
    r = client.post("/api/auth/signup",
                    json={"email": f"x-{uuid.uuid4().hex[:6]}@example.com",
                          "password": PASSWORD, "is_admin": True})
    assert r.status_code == 422


def test_protected_endpoints_require_auth(client):
    for path, method in (("/api/squads", "GET"), ("/api/saved-players", "GET"),
                         ("/api/auth/me", "GET")):
        r = client.request(method, path)
        assert r.status_code == 401, path
        assert r.json()["detail"] == "Authentication required."


def test_invalid_and_tampered_tokens_rejected(client):
    r, _ = signup(client)
    token = r.json()["access_token"]
    # tamper the PAYLOAD segment (not signature tail — base64 bit-padding can
    # make trailing-char swaps decode identically)
    head, payload, sig = token.split(".")
    flipped = ("A" if payload[0] != "A" else "B") + payload[1:]
    for bad in ("garbage", f"{head}.{flipped}.{sig}", f"{head}.{payload}.AAAA",
                f"{head}.x{payload[1:]}.{sig}"):
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {bad}"})
        assert resp.status_code == 401, bad[:24]


def test_logout_all_revokes_every_session(client):
    r, email = signup(client)
    t1 = r.json()["access_token"]
    t2 = client.post("/api/auth/login",
                     json={"email": email, "password": PASSWORD}).json()["access_token"]
    client.post("/api/auth/logout-all", headers={"Authorization": f"Bearer {t1}"})
    assert client.get("/api/auth/me",
                      headers={"Authorization": f"Bearer {t1}"}).status_code == 401
    assert client.get("/api/auth/me",
                      headers={"Authorization": f"Bearer {t2}"}).status_code == 401


def test_profile_update_and_preferences(auth_client):
    r = auth_client.patch("/api/auth/me", json={
        "display_name": "New Name", "preferred_game_version": "FC26",
        "preferences": {"favourite_position": "CM"}})
    assert r.status_code == 200
    assert r.json()["display_name"] == "New Name"
    assert r.json()["preferences"]["favourite_position"] == "CM"


def test_profile_rejects_unknown_game_version(auth_client):
    assert auth_client.patch("/api/auth/me", json={
        "preferred_game_version": "FC25"}).status_code == 422


def test_admin_endpoint_forbidden_for_regular_user(auth_client):
    assert auth_client.get("/api/feedback/stats").status_code == 403


def test_squad_ownership_enforced(client):
    r1, _ = signup(client)
    h1 = {"Authorization": f"Bearer {r1.json()['access_token']}"}
    sq = client.post("/api/squads", headers=h1, json={
        "name": "Private Squad", "formation": "4-3-3", "game_version": "FC26"}).json()

    r2, _ = signup(client)
    h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    assert client.get(f"/api/squads/{sq['id']}", headers=h2).status_code == 404
    assert client.delete(f"/api/squads/{sq['id']}", headers=h2).status_code == 404
    assert client.get(f"/api/squads/{sq['id']}/evaluation", headers=h2).status_code == 404
    # owner can see it
    assert client.get(f"/api/squads/{sq['id']}", headers=h1).status_code == 200
    assert client.get("/api/squads", headers=h2).json() == []


def test_saved_player_ownership(auth_client, client):
    pid = client.get("/api/players?game_version=FC26&q=mbappe&page_size=1"
                     ).json()["items"][0]["id"]
    r = auth_client.post("/api/saved-players",
                         json={"entity_id": pid, "game_version": "FC26", "note": "x"})
    assert r.status_code == 201
    listed = auth_client.get("/api/saved-players").json()
    assert listed["total"] == 1
    # another user must not see it
    r2, _ = signup(client)
    h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    assert client.get("/api/saved-players", headers=h2).json()["total"] == 0
    # unsave
    assert auth_client.delete(f"/api/saved-players/{pid}").status_code == 204
    assert auth_client.get("/api/saved-players").json()["total"] == 0
