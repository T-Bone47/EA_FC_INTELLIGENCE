"""Row-status defense in depth, exercised only on disposable CI PostgreSQL."""
import os
import uuid
from urllib.parse import urlparse

import pytest

URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(urlparse(URL).path != "/eafc_ci", reason="requires disposable eafc_ci")


def test_noncanonical_cards_are_absent_from_direct_search_and_linked_reads():
    import psycopg
    from backend.repositories.player_repository import PlayerRepository

    repository = PlayerRepository()
    version_id = repository.game_version_id("FC26")
    marker = str(uuid.uuid4())
    ids = {}
    with psycopg.connect(URL) as conn:
        player_id = conn.execute(
            "SELECT id FROM game_player WHERE game_version_id=%s AND data_status='CANONICAL' LIMIT 1",
            (version_id,),
        ).fetchone()[0]
        for status in ("CANONICAL", "PENDING_REVIEW", "REJECTED", "SYNTHETIC_TEST"):
            ids[status] = conn.execute(
                """INSERT INTO ut_card (game_version_id, game_player_id, source_id, source_card_id,
                                        card_name, position, data_status, is_synthetic)
                   VALUES (%s, %s, 'synthetic_fixtures', %s, %s, 'CM', %s, %s) RETURNING id""",
                (version_id, player_id, f"{marker}-{status}", marker, status, status == "SYNTHETIC_TEST"),
            ).fetchone()[0]
    try:
        assert repository.card_page(version_id, ids["CANONICAL"])["game_player"]["id"] == player_id
        for status in ("PENDING_REVIEW", "REJECTED", "SYNTHETIC_TEST"):
            assert repository.card_page(version_id, ids[status]) is None
        assert [row["id"] for row in repository.card_search(version_id, q=marker)["items"]] == [ids["CANONICAL"]]
        linked = {row["id"] for row in repository.player_page(version_id, player_id)["cards"]}
        assert linked.intersection(ids.values()) == {ids["CANONICAL"]}
    finally:
        with psycopg.connect(URL) as conn:
            conn.execute("DELETE FROM ut_card WHERE id = ANY(%s)", (list(ids.values()),))
