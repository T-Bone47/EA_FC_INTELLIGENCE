"""Regression coverage for staged evidence and the release-scoped FC27 user journey."""
import uuid
from unittest.mock import patch

from backend.core.config import get_settings
from backend.ingestion.fc27_source_evidence import ITEMS, OCTOBER, crosswalk, normalize_item
from backend.tests.conftest import requires_db


def test_namespace_conflict_null_and_editorial_role():
    players = {"1": {"overall_rating": "70"}, "2": {"overall_rating": "71"}}
    oct_row = {**dict.fromkeys(OCTOBER, ""), "base_id": "1", "stats_id": "5",
               "rating": "83", "full_name": "Fixture One", "position": "CM",
               "position_alt": "R", "position_alt_2": "CDM", "club_name": "C", "league_name": "L"}
    card = {**dict.fromkeys(ITEMS, ""), "eaId": "5", "overall": "83", "full_name": "Fixture One",
            "rarity": "Fixture Promo", "positions": "CM", "club": "C", "league": "L",
            "fc_iq_roles": "CM Playmaker ++: 96.9", "stat_finishing": "82.0", "stat_aggression": "0"}
    rows = list(crosswalk(players, [oct_row], [card, {**card, "eaId": "2"}, {**card, "eaId": "6"}]))
    assert [r["status"] for r in rows] == ["PROVISIONAL", "CONFLICTED", "UNMATCHED"]
    assert rows[1]["candidate_base_id"] is None
    result = normalize_item(card, october=False)
    assert result["official_role_eligibility"] is None
    assert result["unverified_editorial_role_fit"] == "CM Playmaker ++: 96.9"
    assert result["attributes"]["finishing"] == 82 and result["attributes"]["aggression"] is None
    assert normalize_item(oct_row, october=True)["observed_positions"] == ["CM", "CDM"]


@requires_db
def test_research_opt_in_search_squad_and_replacement(client, auth_client):
    opts = {"include_research_data": True}
    query = {**opts, "game_version": "FC27", "position": "CM", "page_size": 3,
             "sort": "overall_rating", "sort_dir": "asc"}
    search = client.get("/api/players", params=query)
    assert search.status_code == 200, search.text
    assert search.json()["research_only"]
    assert {p["data_status"] for p in search.json()["items"]} == {"RESEARCH_ONLY"}
    pid = search.json()["items"][0]["id"]
    page = f"/api/players/{pid}"
    assert client.get(page, params=query).status_code == 200
    assert client.get(page, params={"game_version": "FC27"}).status_code == 404
    assert client.get("/api/players", params={**query, "game_version": "FC26"}).status_code == 422
    production = get_settings().model_copy(update={"environment": "production"})
    with patch("backend.api.deps.get_settings", return_value=production):
        assert client.get("/api/players", params=query).status_code == 403
        for mode in ("compare", "recommendations"):
            assert client.post(f"/api/cards/{mode}", json={
                "game_version": "FC27", **({"card_ids": [str(uuid.uuid4()), str(uuid.uuid4())]}
                                           if mode == "compare" else {"position": "CM"}),
            }).status_code == 403

    created = auth_client.post("/api/squads", json={"game_version": "FC27", "formation": "4-3-3",
        "name": f"Fixture squad {uuid.uuid4().hex[:8]}", "tactics": {"tactical_profile": "HIGH_PRESS"}})
    assert created.status_code == 201, created.text
    base = "/api/squads/" + created.json()["id"]
    try:
        assignment = auth_client.put(base + "/slots/6", params=opts,
            json={"slot_index": 6, "slot_position": "CM", "game_player_id": pid})
        assert assignment.status_code == 200, assignment.text
        assert auth_client.get(base).json()["slots"] == []
        analysis = auth_client.get(base + "/tactical-analysis", params=opts)
        assert analysis.status_code == 200, analysis.text
        fit = analysis.json()["slots"][6]
        assert fit["slot"] == "CDM" and fit["status"] == "ASSESSED"
        assert client.get(base + "/tactical-analysis").status_code == 401
        response = auth_client.get(base + "/tactical-replacements/6", params=opts)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["request"]["slot"] == "CDM" and data["incumbent_score"] == fit["score"]
        assert data["ranked"] and all(row["score_change"] > 0 for row in data["ranked"])
        selected = data["ranked"][0]
        assert auth_client.put(base + "/slots/6", params=opts,
            json={"slot_index": 6, "slot_position": "CM", "game_player_id": selected["entity_id"]}).status_code == 200
        assert auth_client.get(base + "/tactical-analysis", params=opts).json()["slots"][6]["score"] == selected["score"]
    finally:
        auth_client.delete(base)


@requires_db
def test_recommendation_receipt_protects_feedback_metadata(auth_client):
    from backend.core.db import query_one
    response = auth_client.post("/api/v3/recommendations", json={
        "game_version": "FC27", "position": "CM", "limit": 1, "include_research_data": True,
    })
    assert response.status_code == 200, response.text
    data = response.json()
    payload = {"recommendation_id": data["request_id"], "game_version": "FC27",
               "entity_id": data["ranked"][0]["entity_id"], "entity_type": "game_player",
               "action": "SELECTED", "receipt": data["feedback_receipt"],
               "request_context": {"engine_version": "client supplied"}}
    assert auth_client.post("/api/feedback", json={**payload, "entity_id": str(uuid.uuid4())}).status_code == 422
    saved = auth_client.post("/api/feedback", json=payload)
    assert saved.status_code == 201, saved.text
    row = query_one("SELECT request_context FROM user_recommendation_feedback WHERE id=%s", (saved.json()["id"],))
    assert row["request_context"]["engine_version"] == data["engine_version"]
    assert row["request_context"]["served_recommendation_verified"] is True
