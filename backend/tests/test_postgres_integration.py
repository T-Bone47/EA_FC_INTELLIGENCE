"""Integration tests against the real PostgreSQL canonical store:
upsert idempotency, version-contamination guard, firewall filters,
observation bookkeeping. Test rows are labelled SYNTHETIC_TEST and
removed in teardown — production data is never mutated destructively."""
from __future__ import annotations

import uuid

import pytest

from backend.core.db import execute, query, query_one
from backend.domain.card_model import DataStatus, GamePlayer, GameVersionCode
from backend.repositories.postgres_canonical_repository import (
    PostgresCanonicalRepository,
)
from backend.tests.conftest import requires_db
from backend.tests.helpers import make_attrs

pytestmark = requires_db

SOURCE = "kaggle_justdhia_ea_fc26_player_ratings"
RUN = uuid.uuid4().hex[:8]
SPID = 990_000_000 + int(RUN[:6], 16) % 9_000_000   # unique-ish source_player_id
NOTE = f"itest-{RUN}"


def _gp(overall: int = 75, plus: list[str] | None = None) -> GamePlayer:
    return GamePlayer(
        id=uuid.uuid4(),
        game_version=GameVersionCode.FC26,
        source_id=SOURCE,
        source_player_id=SPID,
        display_name="Integration Testee",
        position_primary="CM",
        overall_rating=overall,
        attributes=make_attrs(pace=70, stamina=80),
        nation="Testland",
        data_status=DataStatus.SYNTHETIC_TEST,      # firewall keeps it invisible
    )


def _cleanup() -> None:
    rows = query("""SELECT id FROM game_player
                    WHERE source_id=%s AND source_player_id=%s""", (SOURCE, SPID))
    for r in rows:
        gid = r["id"]
        execute("DELETE FROM game_player_playstyle WHERE game_player_id=%s", (gid,))
        execute("DELETE FROM game_player_attributes WHERE game_player_id=%s", (gid,))
        execute("DELETE FROM game_player_position_secondary WHERE game_player_id=%s", (gid,))
        execute("DELETE FROM club_affiliation WHERE game_player_id=%s", (gid,))
        execute("DELETE FROM game_player WHERE id=%s", (gid,))
    execute("""DELETE FROM source_observation
               WHERE entity_source_id=%s AND raw_payload::text LIKE %s""",
            (f"{SOURCE}:FC26", f"%{NOTE}%"))


@pytest.fixture()
def clean_rows():
    _cleanup()
    yield
    _cleanup()


def _row():
    return query_one("""SELECT gp.*, a.pace, a.stamina
                        FROM game_player gp
                        LEFT JOIN game_player_attributes a ON a.game_player_id=gp.id
                        WHERE gp.source_id=%s AND gp.source_player_id=%s""",
                     (SOURCE, SPID))


def test_upsert_is_idempotent_and_updates_in_place(clean_rows):
    repo = PostgresCanonicalRepository(SOURCE, "FC26")
    repo.upsert_game_player(_gp(overall=75), ["Rapid"], [], True)
    counts = repo.flush(observation_note=NOTE)
    assert counts["players"] == 1
    row = _row()
    assert row is not None and row["overall_rating"] == 75
    gid = row["id"]

    # re-upsert same source key with a changed rating => UPDATE, not duplicate
    repo2 = PostgresCanonicalRepository(SOURCE, "FC26")
    repo2.upsert_game_player(_gp(overall=78), ["Rapid"], ["Finesse Shot"], True)
    repo2.flush(observation_note=NOTE)

    rows = query("""SELECT id, overall_rating FROM game_player
                    WHERE source_id=%s AND source_player_id=%s""", (SOURCE, SPID))
    assert len(rows) == 1
    assert rows[0]["id"] == gid and rows[0]["overall_rating"] == 78

    # playstyles merged without duplication
    ps = query("""SELECT pd.playstyle_name, gpp.tier
                  FROM game_player_playstyle gpp
                  JOIN playstyle_definition pd ON pd.id=gpp.playstyle_definition_id
                  WHERE gpp.game_player_id=%s ORDER BY 1,2""", (gid,))
    assert {(p["playstyle_name"], p["tier"]) for p in ps} == {
        ("Rapid", "base"), ("Finesse Shot", "plus")}


def test_upsert_records_source_observation(clean_rows):
    before = query_one("SELECT count(*)::int AS n FROM source_observation")["n"]
    repo = PostgresCanonicalRepository(SOURCE, "FC26")
    repo.upsert_game_player(_gp(), [], [], False)
    repo.flush(observation_note=NOTE)
    after = query_one("SELECT count(*)::int AS n FROM source_observation")["n"]
    assert after == before + 1
    obs = query_one("""SELECT * FROM source_observation
                       WHERE raw_payload::text LIKE %s""", (f"%{NOTE}%",))
    assert obs["source_id"] == SOURCE and obs["retrieval_context"] == "ingestion-pipeline"


def test_repository_blocks_cross_version_contamination(clean_rows):
    repo = PostgresCanonicalRepository(SOURCE, "FC26")
    gp = _gp()
    gp.game_version = GameVersionCode.FC27
    with pytest.raises(ValueError, match="version contamination"):
        repo.upsert_game_player(gp, [], [], False)
    # nothing was queued, nothing to flush into FC26 either
    assert repo.flush(observation_note=NOTE)["players"] == 0


def test_playstyle_definitions_not_duplicated(clean_rows):
    before = query_one("""SELECT count(*)::int AS n FROM playstyle_definition pd
                          JOIN game_version gv ON gv.id=pd.game_version_id
                          WHERE gv.code='FC26'""")["n"]
    repo = PostgresCanonicalRepository(SOURCE, "FC26")
    repo.upsert_game_player(_gp(), ["Rapid", "Technical"], [], True)
    repo.flush(observation_note=NOTE)
    after = query_one("""SELECT count(*)::int AS n FROM playstyle_definition pd
                         JOIN game_version gv ON gv.id=pd.game_version_id
                         WHERE gv.code='FC26'""")["n"]
    assert after == before      # both names already defined for FC26


def test_firewall_hides_synthetic_gp_from_all_production_reads(clean_rows):
    repo = PostgresCanonicalRepository(SOURCE, "FC26")
    repo.upsert_game_player(_gp(), [], [], False)
    repo.flush(observation_note=NOTE)

    from backend.data_access.candidate_repository import CandidateRepository
    prod = CandidateRepository(cache_ttl=0).load_candidates("FC26")
    assert all(c.data_status == DataStatus.CANONICAL for c in prod)
    assert not any(c.name == "Integration Testee" for c in prod)

    # test-scope flag sees it (proves the row exists and the filter is real)
    testscope = CandidateRepository(cache_ttl=0).load_candidates(
        "FC26", include_synthetic=True)
    assert any(c.name == "Integration Testee" for c in testscope)

    # API search never surfaces it
    from fastapi.testclient import TestClient
    from backend.api.main import create_app
    with TestClient(create_app()) as c:
        d = c.get("/api/players", params={"game_version": "FC26",
                                          "q": "Integration Testee"}).json()
        assert d["total"] == 0


def test_production_counts_unchanged(clean_rows):
    """After the full test cycle the canonical dataset is exactly as before."""
    n = query_one("""SELECT count(*)::int AS n FROM game_player
                     WHERE data_status='CANONICAL'""")["n"]
    assert n == 16228
    synth = query_one("""SELECT count(*)::int AS n FROM game_player
                         WHERE data_status='SYNTHETIC_TEST'""")["n"]
    assert synth == 0       # teardown removed every test row


def test_card_page_flags_synthetic_cards():
    """Synthetic UT cards exist but every read path must flag them."""
    row = query_one("SELECT id FROM ut_card WHERE is_synthetic LIMIT 1")
    assert row is not None
    from backend.repositories.player_repository import PlayerRepository
    gvid = PlayerRepository().game_version_id("FC26")
    page = PlayerRepository().card_page(gvid, row["id"])
    assert page is not None and page["card"]["is_synthetic"] is True
    # a FC27-scoped lookup of the same card finds nothing (version isolation)
    gvid27 = PlayerRepository().game_version_id("FC27")
    assert PlayerRepository().card_page(gvid27, row["id"]) is None
