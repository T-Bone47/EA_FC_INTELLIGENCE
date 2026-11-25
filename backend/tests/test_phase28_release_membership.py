"""Mixed-release fixture checks against the dedicated disposable PostgreSQL database."""
from dataclasses import replace
import os
from unittest.mock import patch
from urllib.parse import urlparse
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.core.config import get_settings
from backend.data_access.candidate_repository import CandidateRepository
from backend.repositories.player_repository import PlayerRepository
from backend.services import data_license_gate as policy

URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(urlparse(URL).path not in {"/eafc_ci", "/eafc28_ci"}, reason="requires disposable eafc_ci")


def test_approved_membership_filters_same_version_rows_links_and_caches():
    marker = uuid.uuid4().hex
    source = "phase28-test-" + marker
    player_ids = [uuid.uuid4(), uuid.uuid4()]
    card_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    player_release = "fc26-players-2026-09-r1"
    card_release = f"fixture-cards-{marker}"
    with psycopg.connect(URL) as conn:
        gv = conn.execute("SELECT id FROM game_version WHERE code='FC26'").fetchone()[0]
        conn.execute("""INSERT INTO source_registry (source_id,name,source_type,authority_tier,usage_status,legal_gate)
                        VALUES (%s,%s,'OTHER',5,'AUTHORIZED','CLEARED')""", (source, source))
        obs = conn.execute("""INSERT INTO source_observation (source_id,game_version_id,entity_type)
                              VALUES (%s,%s,'TEST_SNAPSHOT') RETURNING id""", (source, gv)).fetchone()[0]
        for index, player in enumerate(player_ids):
            conn.execute("""INSERT INTO game_player
                            (id,game_version_id,source_id,source_player_id,normalized_name,display_name,
                             position_primary,overall_rating,data_status)
                            VALUES (%s,%s,%s,%s,%s,%s,'CM',78,'CANONICAL')""",
                         (player, gv, source, index + 1, marker, marker))
            conn.execute("INSERT INTO game_player_attributes (game_player_id,short_passing) VALUES (%s,78)", (player,))
            conn.execute("""INSERT INTO ut_card (id,game_version_id,game_player_id,source_id,source_card_id,
                                                 card_name,position,data_status,is_synthetic)
                            VALUES (%s,%s,%s,%s,%s,%s,'CM','CANONICAL',false)""",
                         (card_ids[index], gv, player_ids[0], source, str(index), marker))
        from backend.domain.card_model import DETAIL_ATTRS, FACADE_ATTRS
        with conn.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO ut_card_attribute_override (ut_card_id,attribute_code,value) VALUES (%s,%s,%s)",
                [(card, attribute, 80 + i) for i, card in enumerate(card_ids[:2])
                 for attribute in (*DETAIL_ATTRS, *FACADE_ATTRS)],
            )
            cursor.executemany("""INSERT INTO catalogue_release_member
                                  (entity_scope,entity_id,dataset_version,game_version_id,source_id,source_observation_id)
                                  VALUES (%s,%s,%s,%s,%s,%s)""",
                               [("game_player", player_ids[0], player_release, gv, source, obs),
                                ("game_player", player_ids[1], "unapproved-fixture", gv, source, obs),
                                ("ut_card", card_ids[0], card_release, gv, source, obs),
                                ("ut_card", card_ids[1], card_release, gv, source, obs)])
    settings = get_settings().model_copy(update={"environment": "production"})
    allowed = {
        player_release: replace(policy._DATASET_LICENSE_REGISTRY[player_release],
                                status=policy.DataLicenseStatus.VERIFIED),
        card_release: policy.DatasetLicenseEntry(policy.DataLicenseStatus.VERIFIED, "FC26", "ut_card"),
    }
    repo = PlayerRepository()
    candidates = CandidateRepository()
    try:
        assert set(player_ids) <= {p.entity_id for p in candidates.load_candidates("FC26", {"CM"})}
        with patch.dict(policy._DATASET_LICENSE_REGISTRY, allowed), patch(
            "backend.core.db.get_settings", return_value=settings
        ), patch("backend.api.deps.get_settings", return_value=settings):
            client = TestClient(create_app())
            assert [p["id"] for p in client.get("/api/players", params={"q": marker}).json()["items"]] == [str(player_ids[0])]
            assert client.get(f"/api/players/{player_ids[1]}").status_code == 404
            page = client.get(f"/api/players/{player_ids[0]}").json()
            assert {row["id"] for row in page["cards"]} == set(map(str, card_ids[:2]))
            assert repo.card_page(gv, card_ids[2]) is None
            status = client.get("/api/card-data-status").json()
            assert status == {"game_version": "FC26", "production_cards": 2,
                              "cards_with_attributes": 2, "availability": {"card_attributes": "AVAILABLE"}}
            assert {p["id"] for p in repo.card_search(gv, q=marker)["items"]} == set(card_ids[:2])
            from backend.services import reference_distribution as refs
            from backend.services.recommendation_service_v3 import RecommendationServiceV3
            ref = refs.build_from_rows([{"position": "CM", "short_passing": n} for n in (70, 80, 90)],
                attribute_columns=["short_passing"], position_field="position",
                version=card_release, game_version="FC26", universe=refs.Universe.UT_CARDS,
                generated_at="2026-11-23T00:00:00Z", min_n=1)
            with patch.dict(refs._REFERENCE_REGISTRY, {("FC26", refs.Universe.UT_CARDS):
                          {"version": card_release, "research_only": False}}), patch(
                    "backend.services.reference_distribution.load_reference_distribution", return_value=ref), patch(
                    "backend.api.routes.cards.get_service_v3",
                    return_value=RecommendationServiceV3(environment=policy.Environment.PRODUCTION)):
                result = client.post("/api/cards/recommendations", json={"game_version": "FC26", "position": "CM"})
                assert result.status_code == 200, result.text
                data = result.json()
                reference = data["provenance_summary"]["reference_distribution"]
                assert reference["universe"] == refs.Universe.UT_CARDS
                assert "Ultimate Team card items" in reference["note"]
                ranked = data["ranked"]
                assert ranked, result.text[:1600]
                assert {row["entity_id"] for row in ranked} == set(map(str, card_ids[:2]))
                assert all(row["entity_type"] == "ut_card" and "card" in row and "player" not in row for row in ranked)
                assert all(row["explanation"]["reconstructed_score_matches_ranking"] for row in ranked)
                compare = client.post("/api/cards/compare", json={"game_version": "FC26",
                                      "card_ids": list(map(str, card_ids[:2]))})
                assert compare.status_code == 200
                assert all(row["delta"] == 1 for row in compare.json()["attributes"])
                mixed = client.post("/api/cards/compare", json={"game_version": "FC26",
                                    "card_ids": [str(card_ids[0]), str(card_ids[2])]})
                assert mixed.status_code == 404
            assert {p.entity_id for p in candidates.load_candidates("FC26", {"CM"})} == {player_ids[0]}
            with psycopg.connect(URL) as conn:
                conn.execute("UPDATE game_player_attributes SET short_passing=79 WHERE game_player_id=%s", (player_ids[0],))
                assert [p.entity_id for p in candidates.load_candidates("FC26", {"CM"})] == [player_ids[0]]
                conn.rollback()
                assert [p.entity_id for p in candidates.load_candidates("FC26", {"CM"})] == [player_ids[0]]
                conn.execute("UPDATE game_player_attributes SET short_passing=79 WHERE game_player_id=%s", (player_ids[0],))
            assert candidates.load_candidates("FC26", {"CM"}) == []
            assert repo.player_page(gv, player_ids[0]) is None
            assert repo.card_page(gv, card_ids[0])["game_player"] is None
    finally:
        with psycopg.connect(URL) as conn:
            conn.execute("DELETE FROM ut_card WHERE id=ANY(%s)", (card_ids,))
            conn.execute("DELETE FROM game_player WHERE id=ANY(%s)", (player_ids,))
            conn.execute("DELETE FROM source_observation WHERE id=%s", (obs,))
            conn.execute("DELETE FROM source_registry WHERE source_id=%s", (source,))
