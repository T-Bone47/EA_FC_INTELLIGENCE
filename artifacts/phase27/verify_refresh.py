"""Measure committed attribute refresh on the dedicated, disposable loopback database."""
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
url = os.environ["DATABASE_URL"]
target = urlparse(url)
if (target.hostname, target.port, target.path) != ("127.0.0.1", 35427, "/eafc_fresh27"):
    raise SystemExit("This probe is restricted to the disposable eafc_fresh27 loopback database.")

import psycopg
from fastapi.testclient import TestClient
from backend.api.main import create_app
from backend.core.db import close_pool

request = {"game_version": "FC26", "position": "CM", "tactical_profile": "BALANCED", "limit": 10}
client = TestClient(create_app())
initial = client.post("/api/v3/recommendations", json=request)
initial.raise_for_status()
ids = [row["entity_id"] for row in initial.json()["ranked"][:2]]
assert len(ids) == 2


def compare_score():
    started = perf_counter()
    result = client.post("/api/v3/compare", json={"request": request, "entity_ids": ids})
    result.raise_for_status()
    score = next(player["score"] for player in result.json()["players"] if player["entity_id"] == ids[0])
    return score, round((perf_counter() - started) * 1000, 2)


before, _ = compare_score()
sql = "UPDATE game_player_attributes SET short_passing = %s WHERE game_player_id=%s"
with psycopg.connect(url) as database:
    original = database.execute(
        "SELECT short_passing FROM game_player_attributes WHERE game_player_id=%s", (ids[0],)
    ).fetchone()[0]
    changed = 1 if original != 1 else 99
    try:
        database.execute(sql, (changed, ids[0]))
        during, _ = compare_score()
        assert before == during, "uncommitted update was observable"
        database.rollback()
        rolled_back, _ = compare_score()
        assert before == rolled_back
        database.execute(sql, (changed, ids[0]))
        database.commit()
        committed_at = perf_counter()
        after, http_ms = compare_score()
        refresh_ms = round((perf_counter() - committed_at) * 1000, 2)
        assert after != before, "the next API request did not observe the committed update"
    finally:
        database.execute(sql, (original, ids[0]))
        database.commit()
restored, _ = compare_score()
assert restored == before
close_pool()
report = {"status": "PASS", "transport": "FastAPI TestClient with live PostgreSQL",
          "initial_score": before, "during_uncommitted_score": during,
          "post_rollback_score": rolled_back, "post_commit_score": after,
          "restored_score": restored, "next_request_ms": http_ms, "commit_to_observed_ms": refresh_ms,
          "changes_preserved_on_exit": False}
Path(__file__).with_name("UPDATE_PROPAGATION_RESULTS.json").write_text(
    json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("PASS uncommitted changes isolated, committed changes visible on next request, original restored")
