"""Committed generation visibility and rollback in the dedicated CI database."""
import os
from urllib.parse import urlparse

import pytest

URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    urlparse(URL).path != "/eafc_ci", reason="requires the disposable eafc_ci database")


def test_committed_child_update_invalidates_both_candidate_caches():
    import psycopg
    from backend.data_access.candidate_repository import CandidateRepository

    first = CandidateRepository()
    second = CandidateRepository()
    first.load_candidates("FC26")
    second.load_candidates("FC26")
    before = first.last_load_stats["data_version"]
    assert before == second.last_load_stats["data_version"]
    with psycopg.connect(URL) as database:
        sql = """UPDATE game_player_attributes SET short_passing = short_passing
                 WHERE game_player_id = (SELECT game_player_id FROM game_player_attributes LIMIT 1)"""
        assert database.execute(sql).rowcount == 1
        assert first._watermark("FC26") == before
        database.rollback()
        assert second._watermark("FC26") == before
        assert database.execute(sql).rowcount == 1
        database.commit()
    for repository in (first, second):
        repository.load_candidates("FC26")
        assert not repository.last_load_stats["cache_hit"]
        assert repository.last_load_stats["data_version"] != before
        repository.load_candidates("FC26")
        assert repository.last_load_stats["cache_hit"]
