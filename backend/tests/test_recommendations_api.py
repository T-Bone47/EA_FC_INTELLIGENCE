"""Recommendation / compare / squad / feedback API behaviour over HTTP,
including the Phase-E version-boundary acceptance checks."""
from __future__ import annotations

import uuid

import pytest

from backend.tests.conftest import requires_db

pytestmark = requires_db

TACTICAL_PROFILES = {"BALANCED", "PRESSING", "COUNTER_ATTACK", "POSSESSION",
                     "DRIBBLE_HEAVY", "CROSSING", "LONG_SHOT", "DIRECT_PLAY",
                     "BUILD_UP", "PACE_ABUSER"}


def first_player(client, q, **params):
    d = client.get("/api/players", params={"game_version": "FC26", "q": q,
                                           "page_size": 1, **params}).json()
    return d["items"][0]


# ------------------------------------------------------------------ recommend
def test_recommendation_returns_ranked_explanations(client):
    r = client.post("/api/recommendations", json={
        "game_version": "FC26", "position": "CM", "formation": "4-2-3-1",
        "tactical_profile": "PRESSING", "limit": 5})
    assert r.status_code == 200
    d = r.json()
    assert d["game_version"] == "FC26" and d["best"] is not None
    assert d["weights_used"] == {"overall_quality": 0.15, "attribute_fit": 0.30,
                                 "position_fit": 0.15, "tactical_fit": 0.15,
                                 "playstyle_fit": 0.15, "team_fit": 0.10}
    ranked = d["ranked"]
    assert len(ranked) == 5
    scores = [x["weighted_score"] for x in ranked]
    assert scores == sorted(scores, reverse=True)
    top = ranked[0]
    assert set(top["components"]) == {"overall_quality", "position_fit",
                                      "attribute_fit", "tactical_fit",
                                      "playstyle_fit", "role_fit", "team_fit"}
    assert 0 <= top["confidence"]["score"] <= 1
    # explanations are generated, honest, and bounded
    ex = d["explanations"]
    assert ex["summary"] and isinstance(ex["why_this"], list)
    assert ex["why_this"] and isinstance(ex["strengths"], list)
    assert d["candidate_pool"]["version_config_status"] == "ACTIVE"
    assert d["data_freshness"]["last_source_observation"] is not None


def test_recommendation_deterministic(client):
    body = {"game_version": "FC26", "position": "ST", "tactical_profile": "COUNTER_ATTACK",
            "attribute_preferences": [{"attribute": "pace", "min_value": 90}], "limit": 5}
    a = client.post("/api/recommendations", json=body).json()
    b = client.post("/api/recommendations", json=body).json()
    assert [x["entity_id"] for x in a["ranked"]] == [x["entity_id"] for x in b["ranked"]]
    assert [x["weighted_score"] for x in a["ranked"]] == \
           [x["weighted_score"] for x in b["ranked"]]


def test_recommendation_respects_attribute_minimums(client):
    d = client.post("/api/recommendations", json={
        "game_version": "FC26", "position": "CM", "limit": 5,
        "attribute_preferences": [{"attribute": "stamina", "min_value": 90}]}).json()
    assert d["ranked"]
    for rec in d["ranked"]:
        ev = "stamina=" in " ".join(rec["components"]["attribute_fit"]["evidence"])
        # evidence strings carry the real attribute values used
        assert ev or rec["components"]["attribute_fit"]["status"] != "KNOWN"


def test_budget_honesty_unverified_prices(client):
    d = client.post("/api/recommendations", json={
        "game_version": "FC26", "position": "ST", "limit": 3,
        "budget_coins": 50000}).json()
    assert d["budget_status"].startswith("BUDGET_UNVERIFIED")
    for rec in d["ranked"]:
        assert rec["budget"]["quote"]["price_coins"] is None   # never faked


def test_pareto_dimensions_honest_about_unknown(client):
    d = client.post("/api/recommendations", json={
        "game_version": "FC26", "position": "CM", "limit": 3}).json()
    par = d["pareto"]
    assert par["best_overall"] is not None
    # no verified prices => best_value must be unavailable, not invented
    assert par["best_value"] is None
    assert "best_value" in par["unavailable_dimensions"]


def test_strict_tactics_excludes_below_floor(client):
    d = client.post("/api/recommendations", json={
        "game_version": "FC26", "position": "CM", "tactical_profile": "PRESSING",
        "strict_tactics": True, "limit": 10}).json()
    for rec in d["ranked"]:
        assert not rec["below_tactical_floor"]
    # hard-excluded entries are reported, not silently dropped
    assert isinstance(d["excluded_by_floor"], list)


def test_rejects_synthetic_scope_leakage(client):
    # synthetic cards are firewalled: no production request may surface them
    d = client.post("/api/recommendations", json={
        "game_version": "FC26", "position": "CM", "limit": 50}).json()
    for rec in d["ranked"]:
        assert rec["entity_type"] == "game_player"
    # explicit card scope is refused honestly (no real card data ingested)
    r = client.post("/api/recommendations", json={
        "game_version": "FC26", "position": "CM", "entity_scope": "ut_card"})
    assert r.status_code == 404
    assert "No canonical (non-synthetic) UT card data" in r.json()["detail"]


def test_recommendation_validation(client):
    assert client.post("/api/recommendations", json={
        "game_version": "FC26", "position": "XYZ"}).status_code == 422
    assert client.post("/api/recommendations", json={
        "game_version": "FC26", "tactical_profile": "FOOTBALL"}).status_code == 422
    assert client.post("/api/recommendations", json={
        "game_version": "FC25", "position": "CM"}).status_code == 422
    assert client.post("/api/recommendations", json={
        "game_version": "FC26", "limit": 999}).status_code == 422
    assert client.post("/api/recommendations", json={
        "game_version": "FC26", "position": "CM", "unknown_field": 1}).status_code == 422


def test_fc27_explicit_no_data_404(client):
    r = client.post("/api/recommendations", json={
        "game_version": "FC27", "position": "CM", "limit": 3})
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert "NO ingested production data" in detail and "none were" in detail


# ------------------------------------------------------------------ intent parse
def test_parse_intent_endpoint(client):
    r = client.post("/api/recommendations/parse-intent", json={
        "text": "need a right winger for counter attack, budget 100k",
        "game_version": "FC26"})
    assert r.status_code == 200
    d = r.json()["draft"]
    assert d["position"] == "RW"
    assert d["tactical_profile"] == "COUNTER_ATTACK"
    assert d["budget_coins"] == 100_000
    assert any("deterministic" in n for n in d["confidence_notes"])
    # every emitted value is reference-valid: feeding it back must work
    draft = {k: d[k] for k in ("game_version", "position", "tactical_profile",
                               "budget_coins") if k in d}
    assert client.post("/api/recommendations", json=draft).status_code == 200


def test_parse_intent_never_invents(client):
    d = client.post("/api/recommendations/parse-intent", json={
        "text": "blorp zzz quantum foo bar", "game_version": "FC26"}
        ).json()["draft"]
    assert "position" not in d and "tactical_profile" not in d
    assert "attribute_preferences" not in d and "budget_coins" not in d
    assert d["game_version"] == "FC26"
    assert any("no budget detected" in n for n in d["confidence_notes"])


# ------------------------------------------------------------------ compare
def test_compare_verdict_consistent_with_context(client):
    a = first_player(client, "pedri")["id"]
    b = first_player(client, "bellingham")["id"]
    d = client.post("/api/compare", json={
        "game_version": "FC26", "entity_ids": [a, b],
        "user_context": {"game_version": "FC26", "position": "CM",
                         "tactical_profile": "POSSESSION", "limit": 1}}).json()
    assert d["verdict"]["user_context"] is True
    ranked = d["verdict"]["ranked_for_user"]
    assert len(ranked) == 2
    assert ranked[0]["weighted_score"] >= ranked[1]["weighted_score"]
    assert d["verdict"]["why"][0].startswith("For THIS request,")
    assert ranked[0]["name"] in d["verdict"]["why"][0]
    # side-by-side columns carry real facts and honest unknowns
    col = d["columns"][0]
    assert col["price_coins"] is None          # UNKNOWN, never 0
    assert col["overall_rating"] is not None
    assert set(col["facades"]) == {"pace", "shooting", "passing",
                                    "dribbling", "defending", "physicality"}


def test_compare_without_context_no_ranking(client):
    a = first_player(client, "pedri")["id"]
    b = first_player(client, "bellingham")["id"]
    d = client.post("/api/compare", json={
        "game_version": "FC26", "entity_ids": [a, b]}).json()
    assert d["verdict"] == {"user_context": False}
    assert len(d["columns"]) == 2


def test_compare_validation(client):
    a = first_player(client, "pedri")["id"]
    assert client.post("/api/compare", json={
        "game_version": "FC26", "entity_ids": [a]}).status_code == 422
    assert client.post("/api/compare", json={
        "game_version": "FC26", "entity_ids": [a, str(uuid.uuid4())]
        }).status_code == 404                      # unknown entity => honest 404
    assert client.post("/api/compare", json={
        "game_version": "FC26", "entity_ids": [a, a, a, a, a]}).status_code == 422
    # context version must match comparison version — never mixed
    assert client.post("/api/compare", json={
        "game_version": "FC26", "entity_ids": [a, a],
        "user_context": {"game_version": "FC27"}}).status_code == 422


def test_compare_gk_uses_gk_details(client):
    gk1 = first_player(client, "alisson")["id"]
    gk2 = first_player(client, "courtois")["id"]
    d = client.post("/api/compare", json={
        "game_version": "FC26", "entity_ids": [gk1, gk2]}).json()
    for col in d["columns"]:
        assert "gk_diving" in col["details"]


# ------------------------------------------------------------------ squads
def _make_squad(auth_client, name=None):
    r = auth_client.post("/api/squads", json={
        "name": name or f"S-{uuid.uuid4().hex[:8]}",
        "formation": "4-2-3-1", "game_version": "FC26"})
    assert r.status_code == 201
    return r.json()


def test_squad_full_lifecycle(client, auth_client):
    sq = _make_squad(auth_client)
    sid = sq["id"]

    gk = first_player(client, "alisson")
    r = auth_client.put(f"/api/squads/{sid}/slots/0", json={
        "slot_index": 0, "slot_position": "GK", "game_player_id": gk["id"]})
    assert r.status_code == 200
    slots = r.json()["slots"]
    assigned = next(s for s in slots if s["slot_index"] == 0)
    assert assigned["player_name"] == "Alisson"

    # wrong position for the slot is rejected with an explanatory 422
    cm = first_player(client, "pedri")
    bad = auth_client.put(f"/api/squads/{sid}/slots/0", json={
        "slot_index": 0, "slot_position": "CM", "game_player_id": cm["id"]})
    assert bad.status_code == 422 and "is GK, not CM" in bad.json()["detail"]

    # path/body slot_index mismatch rejected
    assert auth_client.put(f"/api/squads/{sid}/slots/0", json={
        "slot_index": 1, "slot_position": "GK"}).status_code == 422
    # slot beyond formation rejected
    assert auth_client.put(f"/api/squads/{sid}/slots/99", json={
        "slot_index": 99, "slot_position": "GK"}).status_code == 422

    # evaluation: real link facts, chemistry stays INSUFFICIENT_EVIDENCE
    ev = auth_client.get(f"/api/squads/{sid}/evaluation").json()
    assert ev["chemistry"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert "fabricated" in ev["chemistry"]["reason"]
    checks = {c["slot_index"]: c for c in ev["position_checks"]}
    assert checks[0]["expected_position"] == "GK"
    assert checks[0]["out_of_position"] is False

    # replacement recommendation runs in squad context
    rep = auth_client.post(f"/api/squads/{sid}/recommend-replacement",
                           json={"slot_index": 0}).json()
    assert rep["slot"] == {"slot_index": 0, "slot_position": "GK"}
    assert rep["best"] is not None

    # clear slot, rename, delete
    cleared = auth_client.delete(f"/api/squads/{sid}/slots/0").json()
    assert all(s["player_name"] is None for s in cleared["slots"])
    patched = auth_client.patch(f"/api/squads/{sid}",
                                json={"name": "Renamed XI"}).json()
    assert patched["name"] == "Renamed XI"
    assert auth_client.delete(f"/api/squads/{sid}").status_code == 204
    assert auth_client.get(f"/api/squads/{sid}").status_code == 404


def test_squad_validation(client, auth_client):
    assert auth_client.post("/api/squads", json={
        "name": "x", "formation": "9-9-9", "game_version": "FC26"}).status_code == 422
    assert auth_client.post("/api/squads", json={
        "name": "x", "formation": "4-3-3", "game_version": "FC25"}).status_code == 422
    assert client.post("/api/squads", json={
        "name": "x", "formation": "4-3-3"}).status_code == 401


def test_squad_version_isolation(client, auth_client):
    """FC27 entities cannot be placed into a squad, and FC26 squads cannot be
    used as FC27 recommendation context."""
    sq = _make_squad(auth_client)
    r = auth_client.put(f"/api/squads/{sq['id']}/slots/0", json={
        "slot_index": 0, "slot_position": "GK", "game_player_id": str(uuid.uuid4())})
    assert r.status_code == 404          # unknown/not-in-version player
    # squad is FC26; asking for FC27 recommendations with it must refuse
    r = auth_client.post("/api/recommendations", json={
        "game_version": "FC27", "position": "GK", "squad_id": sq["id"]})
    assert r.status_code in (404, 422)
    assert "never mixed" in r.json()["detail"] or "NO ingested" in r.json()["detail"]


def test_recommendation_with_squad_context_requires_auth(client, auth_client):
    sq = _make_squad(auth_client)
    r = client.post("/api/recommendations", json={
        "game_version": "FC26", "position": "GK", "squad_id": sq["id"]})
    assert r.status_code == 401
    # and with auth it works, returning team_fit evidence from the real squad
    r = auth_client.post("/api/recommendations", json={
        "game_version": "FC26", "position": "GK", "squad_id": sq["id"], "limit": 2})
    assert r.status_code == 200


# ------------------------------------------------------------------ feedback
def test_feedback_roundtrip(client, auth_client):
    rec = client.post("/api/recommendations", json={
        "game_version": "FC26", "position": "CM", "limit": 1}).json()
    top = rec["ranked"][0]
    r = auth_client.post("/api/feedback", json={
        "recommendation_id": rec["request_id"], "action": "SELECTED",
        "entity_type": "game_player", "entity_id": top["entity_id"],
        "game_version": "FC26", "reason": "fits the press"})
    assert r.status_code == 201 and r.json()["status"] == "recorded"
    # invalid action rejected by enum
    assert auth_client.post("/api/feedback", json={
        "recommendation_id": rec["request_id"], "action": "MAYBE",
        "entity_type": "game_player"}).status_code == 422
    # admin stats closed to regular users
    assert auth_client.get("/api/feedback/stats").status_code == 403


def test_recommendation_records_shown_feedback_for_authed_user(auth_client):
    rec = auth_client.post("/api/recommendations", json={
        "game_version": "FC26", "position": "CM", "limit": 1}).json()
    assert rec["best"] is not None
    from backend.core.db import query
    rows = query("""SELECT action FROM user_recommendation_feedback
                    WHERE recommendation_id = %s""", (rec["request_id"],))
    assert rows and rows[0]["action"] == "SHOWN"
