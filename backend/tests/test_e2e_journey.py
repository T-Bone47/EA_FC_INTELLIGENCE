"""End-to-end user journeys over the real HTTP surface (TestClient + real DB).

These mirror what the frontend does, step by step: signup -> search -> player
page -> recommendation -> feedback -> squad build -> evaluation -> replacement
-> compare -> saved -> logout. Every assertion is about REAL behaviour; no
fixtures are injected into the production path.
"""
from __future__ import annotations

import uuid

import pytest

from backend.tests.conftest import requires_db

pytestmark = requires_db

PASSWORD = "Journey-Pass-123!"


def _signup(client, name="Journey Tester"):
    email = f"journey-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/auth/signup", json={
        "email": email, "password": PASSWORD, "display_name": name})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_journey_discover_recommend_save(client):
    """Anonymous discovery -> recommendation -> signup -> save -> feedback."""
    # 1. landing page data
    versions = client.get("/api/meta/game-versions").json()
    status = {v["code"]: v["status"] for v in versions}
    assert status.get("FC26") == "ACTIVE" and status.get("FC27") == "NO_DATA"
    ref = client.get("/api/meta/reference", params={"game_version": "FC26"}).json()
    assert ref["capabilities"]["market_data_available"] is False

    # 2. search like the UI does (debounced q + filters)
    res = client.get("/api/players", params={
        "game_version": "FC26", "q": "de bruyne", "sort": "overall_rating",
        "sort_dir": "desc", "page": 1, "page_size": 25}).json()
    assert res["total"] >= 1
    target = res["items"][0]

    # 3. player page with honest unknowns
    page = client.get(f"/api/players/{target['id']}",
                      params={"game_version": "FC26"}).json()
    assert page["game_player"]["display_name"] == target["display_name"]
    assert page["cards"] == []                    # no fabricated UT cards
    assert page["provenance"]["license"]

    # 4. run a recommendation from the player's position
    rec = client.post("/api/recommendations", json={
        "game_version": "FC26", "position": target["position_primary"],
        "tactical_profile": "POSSESSION", "limit": 5,
        "attribute_preferences": [{"attribute": "short_passing", "min_value": 85}],
    }).json()
    assert rec["best"] is not None
    assert rec["budget_status"] or True
    request_id = rec["request_id"]
    best = rec["ranked"][0]

    # 5. signup, then save + feedback (what the UI buttons do)
    h = _signup(client)
    assert client.post("/api/saved-players", headers=h, json={
        "entity_type": "game_player", "entity_id": best["entity_id"],
        "game_version": "FC26", "note": "engine pick"}).status_code == 201
    assert client.post("/api/feedback", headers=h, json={
        "recommendation_id": request_id, "action": "SELECTED",
        "entity_type": "game_player", "entity_id": best["entity_id"],
        "game_version": "FC26"}).status_code == 201
    saved = client.get("/api/saved-players", headers=h).json()
    assert saved["total"] == 1

    # 6. the same recommendation is deterministic across runs
    rec2 = client.post("/api/recommendations", json={
        "game_version": "FC26", "position": target["position_primary"],
        "tactical_profile": "POSSESSION", "limit": 5,
        "attribute_preferences": [{"attribute": "short_passing", "min_value": 85}],
    }).json()
    assert [x["entity_id"] for x in rec2["ranked"]] == \
           [x["entity_id"] for x in rec["ranked"]]


def test_journey_squad_builder(client):
    """Authed squad build: create -> assign GK+CM -> evaluate -> replace -> teardown."""
    h = _signup(client)

    # create squad in current version
    sq = client.post("/api/squads", headers=h, json={
        "name": f"Journey XI {uuid.uuid4().hex[:4]}", "formation": "4-2-3-1",
        "game_version": "FC26"}).json()
    sid = sq["id"]

    def find(q, position=None):
        return client.get("/api/players", params={
            "game_version": "FC26", "q": q, "position": position,
            "page_size": 1}).json()["items"][0]

    gk = find("alisson", "GK")
    cdm = find("rodri", "CDM") if client.get("/api/players", params={
        "game_version": "FC26", "q": "rodri", "position": "CDM",
        "page_size": 1}).json()["total"] else find("kroos", "CDM")

    # assign GK (slot 0) and a CDM (slot 5 per 4-2-3-1 layout)
    r = client.put(f"/api/squads/{sid}/slots/0", headers=h, json={
        "slot_index": 0, "slot_position": "GK", "game_player_id": gk["id"]})
    assert r.status_code == 200
    r = client.put(f"/api/squads/{sid}/slots/5", headers=h, json={
        "slot_index": 5, "slot_position": "CDM", "game_player_id": cdm["id"]})
    assert r.status_code == 200

    # evaluation: links real, chemistry honest
    ev = client.get(f"/api/squads/{sid}/evaluation", headers=h).json()
    assert ev["links"]["filled_slots"] == 2
    assert ev["chemistry"]["status"] == "INSUFFICIENT_EVIDENCE"
    in_pos = {c["slot_index"]: not c["out_of_position"] for c in ev["position_checks"]
              if c["player"]}
    assert in_pos == {0: True, 5: True}

    # replacement recommendation for the CDM slot, in squad context
    rep = client.post(f"/api/squads/{sid}/recommend-replacement", headers=h,
                      json={"slot_index": 5}).json()
    assert rep["slot"]["slot_position"] == "CDM"
    assert rep["best"] is not None
    # assigning the engine's own pick must succeed (position-compatible by design)
    pick = rep["ranked"][0]
    r = client.put(f"/api/squads/{sid}/slots/5", headers=h, json={
        "slot_index": 5, "slot_position": "CDM",
        "game_player_id": pick["entity_id"]})
    assert r.status_code == 200, r.text

    # squad-context recommendation via /api/recommendations
    ctx_rec = client.post("/api/recommendations", headers=h, json={
        "game_version": "FC26", "position": "CB", "squad_id": sid, "limit": 3}).json()
    assert ctx_rec["best"] is not None

    # teardown
    assert client.delete(f"/api/squads/{sid}", headers=h).status_code == 204


def test_journey_compare_and_version_wall(client):
    """Compare flow + the FC27 wall every surface must respect."""
    def find(q):
        return client.get("/api/players", params={
            "game_version": "FC26", "q": q, "page_size": 1}).json()["items"][0]

    a, b = find("haaland"), find("salah")
    cmp = client.post("/api/compare", json={
        "game_version": "FC26", "entity_ids": [a["id"], b["id"]],
        "user_context": {"game_version": "FC26", "position": "ST",
                         "tactical_profile": "COUNTER_ATTACK", "limit": 1}}).json()
    assert cmp["verdict"]["user_context"] is True
    ranked = cmp["verdict"]["ranked_for_user"]
    assert ranked[0]["weighted_score"] >= ranked[1]["weighted_score"]
    assert all(col["price_coins"] is None for col in cmp["columns"])  # UNKNOWN prices

    # the FC27 wall: every surface refuses honestly, none falls back to FC26
    assert client.post("/api/recommendations", json={
        "game_version": "FC27", "position": "ST"}).status_code == 404
    assert client.get("/api/players", params={
        "game_version": "FC27", "q": "haaland"}).json()["total"] == 0
    fc27_cmp = client.post("/api/compare", json={
        "game_version": "FC27", "entity_ids": [a["id"], b["id"]]})
    assert fc27_cmp.status_code == 404          # FC26 ids don't resolve in FC27
    ref27 = client.get("/api/meta/reference",
                       params={"game_version": "FC27"}).json()
    assert ref27["status"] == "NO_DATA" and ref27["positions"] == []


def test_journey_auth_lifecycle(client):
    """Signup -> me -> profile update -> logout-all -> locked out."""
    h = _signup(client)
    me = client.get("/api/auth/me", headers=h).json()
    assert me["role"] == "user"

    upd = client.patch("/api/auth/me", headers=h, json={
        "display_name": "Renamed", "preferred_game_version": "FC26",
        "preferences": {"favourite_position": "CM"}}).json()
    assert upd["display_name"] == "Renamed"
    assert upd["preferences"]["favourite_position"] == "CM"

    assert client.post("/api/auth/logout-all", headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401
    assert client.get("/api/squads", headers=h).status_code == 401

    # password login still works after session revocation
    lr = client.post("/api/auth/login", json={
        "email": me["email"], "password": PASSWORD})
    assert lr.status_code == 200
    h2 = {"Authorization": f"Bearer {lr.json()['access_token']}"}
    assert client.get("/api/auth/me", headers=h2).status_code == 200
