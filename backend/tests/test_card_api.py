"""Phase 3 §41/§44/§49 — additive card API surface.

Legacy endpoints must be untouched; new card endpoints must be honest about
NO_DATA and keep the synthetic firewall at the API boundary.
"""
from __future__ import annotations

import uuid

import pytest

from backend.tests.conftest import requires_db


@requires_db
class TestCardEndpoints:
    def test_cards_list_empty_but_honest(self, client):
        r = client.get("/api/cards", params={"game_version": "FC26"})
        assert r.status_code == 200
        d = r.json()
        assert d["game_version"] == "FC26"
        assert d["total"] == 0            # no production cards ingested yet
        assert d["items"] == []

    def test_cards_list_validates_params(self, client):
        assert client.get("/api/cards", params={"game_version": "FC25"}).status_code == 422
        assert client.get("/api/cards", params={"page_size": 999}).status_code == 422
        assert client.get("/api/cards", params={"ovr_min": 0}).status_code == 422
        assert client.get("/api/cards", params={"sort_dir": "sideways"}).status_code == 422

    def test_card_data_status_reports_no_data_honestly(self, client):
        r = client.get("/api/card-data-status", params={"game_version": "FC26"})
        assert r.status_code == 200
        d = r.json()
        assert d["production_cards"] == 0
        assert d["synthetic_cards_firewalled"] > 0     # fixtures exist, firewalled
        assert d["availability"]["card_attributes"] == "NO_DATA"
        assert d["availability"]["chemistry_rules"] == "NO_VERIFIED_RULES"
        assert d["availability"]["evolutions"] == "NO_DATA"
        assert isinstance(d["recent_ingestion_runs"], list)

    def test_unknown_card_404(self, client):
        r = client.get(f"/api/cards/{uuid.uuid4()}", params={"game_version": "FC26"})
        assert r.status_code == 404

    def test_synthetic_card_firewalled_on_every_card_endpoint(self, client):
        from backend.core.db import query
        rows = query("SELECT id FROM ut_card WHERE is_synthetic = TRUE LIMIT 1")
        if not rows:
            pytest.skip("no synthetic fixture cards loaded")
        sid = rows[0]["id"]
        assert client.get(f"/api/cards/{sid}",
                          params={"game_version": "FC26"}).status_code == 404
        assert client.get(f"/api/cards/{sid}/versions",
                          params={"game_version": "FC26"}).status_code == 404
        assert client.get(f"/api/cards/{sid}/prices",
                          params={"game_version": "FC26"}).status_code == 404
        assert client.get(f"/api/cards/{sid}/value",
                          params={"game_version": "FC26"}).status_code == 404

    def test_fc27_card_endpoints_hit_version_wall(self, client):
        # FC27 is registered but has NO data: endpoints answer, never fabricate
        r = client.get("/api/cards", params={"game_version": "FC27"})
        if r.status_code == 200:
            assert r.json()["total"] == 0
        else:
            assert r.status_code in (404, 422)

    def test_compare_still_works_for_players(self, client):
        from backend.core.db import query
        rows = query("""SELECT gp.id FROM game_player gp
                        JOIN game_version gv ON gv.id = gp.game_version_id
                        WHERE gv.code='FC26' AND gp.data_status <> 'SYNTHETIC_TEST'
                        ORDER BY gp.overall_rating DESC NULLS LAST LIMIT 2""")
        ids = [str(r["id"]) for r in rows]
        r = client.post("/api/compare", json={"game_version": "FC26",
                                              "entity_ids": ids})
        assert r.status_code == 200
        d = r.json()
        assert len(d["columns"]) == 2
        for col in d["columns"]:
            assert col["entity_type"] == "game_player"
            assert col["card"] is None       # additive field; None for players

    def test_recommendations_card_scope_refused_while_no_data(self, client):
        r = client.post("/api/recommendations", json={
            "game_version": "FC26", "position": "ST", "entity_scope": "ut_card"})
        assert r.status_code == 404
        assert "No canonical (non-synthetic) UT card data" in r.json()["detail"]

    def test_legacy_endpoints_unchanged(self, client):
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/meta/game-versions").status_code == 200
        r = client.get("/api/players", params={"game_version": "FC26",
                                               "page_size": 5})
        assert r.status_code == 200
        assert r.json()["items"]
