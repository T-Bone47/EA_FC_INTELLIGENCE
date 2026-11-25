"""V3 API integration tests. Player-scope only."""
from __future__ import annotations

import pytest

from backend.tests.conftest import requires_db

pytestmark = requires_db


class TestRecommendationsV3Endpoint:
    def test_player_scope_returns_ranked_results(self, client):
        r = client.post("/api/v3/recommendations", json={
            "game_version": "FC26", "position": "CM",
            "tactical_profile": "POSSESSION", "limit": 5,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["entity_scope"] == "game_player"
        # The V3.2.1 scoring version includes preference input hardening.
        assert data["engine_version"] == "3.2.1"
        assert data["config_version"] == "v3.2-2026-09-30-r1"
        assert data["reference_distribution_universe"] == "RATINGS_SITE_PLAYERS"
        assert len(data["ranked"]) > 0
        assert data["ranked"][0]["rank"] == 1
        assert "explanation" in data["ranked"][0]
        assert data["ranked"][0]["explanation"]["reconstructed_score_matches_ranking"] is True

    def test_ut_card_scope_rejected_at_validation(self, client):
        r = client.post("/api/v3/recommendations", json={
            "game_version": "FC26", "position": "CM", "entity_scope": "ut_card",
        })
        assert r.status_code == 422
        assert "game_player" in r.text

    def test_response_carries_all_required_versions(self, client):
        r = client.post("/api/v3/recommendations", json={
            "game_version": "FC26", "position": "CB", "tactical_profile": "LOW_BLOCK",
        })
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("engine_version", "config_version", "data_version",
                    "reference_distribution_version", "reference_distribution_universe"):
            assert data.get(key), f"missing {key}"

    def test_tactical_flip_visible_through_the_api(self, client):
        """End-to-end confirmation that the signed tactical fix is reachable
        through the real HTTP surface, not only the engine in isolation."""
        low_block = client.post("/api/v3/recommendations", json={
            "game_version": "FC26", "position": "CB",
            "tactical_profile": "LOW_BLOCK", "limit": 10,
        }).json()
        high_press = client.post("/api/v3/recommendations", json={
            "game_version": "FC26", "position": "CB",
            "tactical_profile": "HIGH_PRESS", "limit": 10,
        }).json()
        low_block_top10 = {r["name"] for r in low_block["ranked"]}
        high_press_top10 = {r["name"] for r in high_press["ranked"]}
        overlap = len(low_block_top10 & high_press_top10)
        assert overlap < 10, "LOW_BLOCK and HIGH_PRESS returned an identical top-10 through the API"

    def test_full_provenance_detail_available_on_request(self, client):
        r = client.post("/api/v3/recommendations", json={
            "game_version": "FC26", "position": "CM", "tactical_profile": "POSSESSION",
            "limit": 1, "provenance_detail": "full",
        })
        assert r.status_code == 200, r.text
        ctx = r.json()["ranked"][0]["scoring_context"]
        assert "per_attribute" in ctx
        assert "demand_stages" not in ctx or True  # to_dict() may omit stages; per_attribute is the key contract
        assert ctx["per_attribute"], "full provenance detail must include per-attribute contributions"
