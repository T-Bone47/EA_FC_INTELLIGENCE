"""V3 formation settings, demand and HTTP contract."""
from fastapi.testclient import TestClient
import pytest

from backend.api.main import create_app
from backend.api.schemas_v3 import RecommendationRequestV3
from backend.services.formations import FORMATION_SLOTS
from backend.tests.conftest import requires_db


@pytest.mark.parametrize("formation", sorted(FORMATION_SLOTS))
def test_every_declared_assignment_validates(formation):
    for slot in FORMATION_SLOTS[formation]:
        body = RecommendationRequestV3(game_version="FC26", position=slot.position,
                                       formation=formation, slot=slot.slot)
        assert body.slot == slot.slot


def test_intent_only_returns_supported_v3_requests():
    client = TestClient(create_app())
    supported = client.post("/api/v3/parse-intent", json={"text": "high press midfielder"})
    assert supported.status_code == 200, supported.text
    draft = RecommendationRequestV3.model_validate(supported.json()["draft"])
    assert (draft.position, draft.tactical_profile) == ("CM", "HIGH_PRESS")
    rejected = client.post("/api/v3/parse-intent", json={"text": "midfielder under 100k"})
    assert rejected.status_code == 422
    assert "budget_coins" in rejected.json()["detail"]["fields"]


def test_slot_position_and_incompatible_tactics_are_rejected():
    client = TestClient(create_app())
    for body in (
        {"formation": "4-3-3", "slot": "ST"},
        {"formation": "4-3-3", "slot": "BOGUS"},
        {"tactical_profile": "HIGH_PRESS", "secondary_tactical_profile": "LOW_BLOCK"},
    ):
        response = client.post("/api/v3/recommendations", json={"game_version": "FC26", "position": "CM", **body})
        assert response.status_code == 422


@requires_db
def test_live_slot_scoring_comparison_and_what_if_share_demand():
    client = TestClient(create_app())
    body = {"game_version": "FC26", "position": "CM", "formation": "4-3-3", "slot": "CDM"}
    response = client.post("/api/v3/recommendations", json=body)
    assert response.status_code == 200, response.text[:500]
    ranked = response.json()
    assert ranked["request"]["slot"] == "CDM"
    right = client.post("/api/v3/recommendations", json={**body, "slot": "RCM"}).json()
    assert ranked["demand_vector"] != right["demand_vector"]
    ids = [row["entity_id"] for row in ranked["ranked"][:2]]
    compared = client.post("/api/v3/compare", json={"request": body, "entity_ids": ids}).json()
    assert compared["request"]["slot"] == "CDM"
    assert {row["entity_id"]: row["score"] for row in compared["players"]} == {
        row["entity_id"]: row["score"] for row in ranked["ranked"][:2]
    }
    changed = client.post("/api/v3/what-if", json={
        "base": body, "variants": [{"label": "Right CM", "slot": "RCM"}],
    }).json()
    assert changed["variants"][0]["changes"] == {"slot": "RCM"}
    assert changed["variants"][0]["demand_shift"]


@requires_db
def test_stated_style_roundtrips_through_the_owned_profile(auth_client):
    style = {"position": "CB", "tactical_profile": "LOW_BLOCK"}
    response = auth_client.patch("/api/auth/me", json={"preferences": {"football_style": style}})
    assert response.status_code == 200, response.text
    assert auth_client.get("/api/auth/me").json()["preferences"]["football_style"] == style
    invalid = auth_client.patch("/api/auth/me", json={
        "preferences": {"football_style": {**style, "inferred_skill": "elite"}},
    })
    assert invalid.status_code == 422
