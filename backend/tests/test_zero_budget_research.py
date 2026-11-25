import uuid
from itertools import permutations
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.core.config import get_settings
from backend.tests.conftest import requires_db
from backend.services.formation_optimizer import optimal_assignments

PREFIX = "/api/research/fc27/cards"
REQUEST = dict(game_version="FC27", position="RW", tactical_profile="BALANCED", include_research_data=True)


def test_column_changes_and_extra_same_version_items_cannot_enter_pinned_release():
    from backend.services import fc27_card_research as release
    for key, rows in [("wrong-fields", [{"record_id":"1"}]*release.SOURCE.rows),
                      ("extra-member", [{"record_id":"1"}]*(release.SOURCE.rows+1))]:
        with patch.object(release, "staged_cards", return_value=rows), pytest.raises(ValueError, match="pinned"):
            release.local_release(key)


def test_optimizer_searches_joint_assignments_and_handles_unfilled_slots():
    def row(p, score):
        return {"entity_id": p, "score": score}
    options = [[row("a", .9), row("b", .89)], [row("a", .85), row("b", .2)], []]
    for first in permutations(options[0]):
        result = optimal_assignments([first, *options[1:]])
        assert [r["entity_id"] if r else None for r in result] == ["b", "a", None]
    assert optimal_assignments([[], []]) == [None, None]


def _with_client_addr(app, peer: str, port: int = 55000):
    async def wrapped(scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            scope = {**scope, "client": (peer, port)}
        await app(scope, receive, send)
    return wrapped


@pytest.mark.parametrize(("env", "enabled", "peer", "host"), [
    ("production", True, "127.0.0.1", "127.0.0.1"), ("research", True, "127.0.0.1", "127.0.0.1"),
    ("test", False, "127.0.0.1", "127.0.0.1"), ("test", True, "192.0.2.1", "127.0.0.1"),
    ("test", True, "127.0.0.1", "public.example"),
])
def test_card_release_denied_before_read(env, enabled, peer, host):
    cfg = get_settings().model_copy(update={"environment": env, "fc27_card_research_enabled": enabled})
    with TestClient(_with_client_addr(create_app(), peer, 55000), base_url="http://"+host) as client, patch(
            "backend.api.routes.research_cards.get_settings", return_value=cfg), patch(
            "backend.api.routes.research_cards.local_release") as read:
        assert client.post(PREFIX+"/recommendations", json=REQUEST).status_code == 403
        read.assert_not_called()


@requires_db
def test_pinned_card_items_end_to_end():
    cfg = get_settings().model_copy(update={"environment": "test", "fc27_card_research_enabled": True})
    from backend.core.db import query_one
    from backend.services.fc27_card_research import SNAPSHOT
    if not query_one("SELECT to_regclass('fc27_staging.snapshot') AS table_name")["table_name"]:
        pytest.skip("FC27 staging not installed")
    if not query_one("SELECT 1 FROM fc27_staging.snapshot WHERE snapshot_id=%s", (SNAPSHOT,)):
        pytest.skip("Owner card archive is absent")
    with TestClient(_with_client_addr(create_app(), "127.0.0.1", 55001), base_url="http://127.0.0.1") as c, patch(
            "backend.api.routes.research_cards.get_settings", return_value=cfg):
        assert c.get(PREFIX, params={"q": "Yamal"}).status_code == 422
        assert c.post(PREFIX+"/recommendations", json={**REQUEST, "game_version":"FC26"}).status_code == 422
        assert c.post(PREFIX+"/recommendations", json={**REQUEST, "include_research_data":False}).status_code == 422
        response = c.get(PREFIX, params={"q":"Yamal","include_research_data":"true"})
        assert response.headers["cache-control"] == "private, no-store"
        items = {x["source_item_id"]: x for x in response.json()["items"]}
        ids = [items[i]["entity_id"] for i in ("67386507","84163723")]
        with_style = {**REQUEST, "desired_playstyles_plus":["Quick Step"]}
        pair = c.post(PREFIX+"/compare", json={"request":with_style, "card_ids":ids}).json()
        assert len(pair["players"]) == 2 and pair["pairwise"][0]["why"]
        assert all(p["coverage"] == 1 and p["explanation"]["reconstructed_score_matches_ranking"] for p in pair["players"])
        assert all(p["card"]["market_price"] is None and p["card"]["official_roles"] is None for p in pair["players"])
        assert pair["cards"][0]["attributes"]["stamina"] != pair["cards"][1]["attributes"]["stamina"]
        assert pair["dataset"]["reference_distribution"]["universe"] == "UT_CARDS"
        assert c.post(PREFIX+"/compare", json={"request":REQUEST,"card_ids":[ids[0], str(uuid.uuid4())]}).status_code == 404
        scores = {p["entity_id"]: p["score"] for p in pair["players"]}
        reversed_pair = c.post(PREFIX+"/compare", json={"request":with_style,"card_ids":ids[::-1]}).json()
        assert scores == {p["entity_id"]:p["score"] for p in reversed_pair["players"]}
        gk = c.post(PREFIX+"/recommendations", json={**REQUEST,"position":"GK"}).json()
        assert gk["ranked"] == []
        assert (gk["counts"]["not_evaluable"], gk["counts"]["excluded"], gk["counts"]["candidates"]) == (1100, 2, 1102)
        ranked = c.post(PREFIX+"/recommendations",json=REQUEST).json()
        assert ranked["ranked"] and ranked["entity_scope"] == "ut_card"
        changed = c.post(PREFIX+"/what-if?tactical_profile=HIGH_PRESS", json=REQUEST).json()
        assert changed["base_top"][0]["score"] == ranked["ranked"][0]["score"]
        assert any(p["score_delta"] for p in changed["variants"][0]["tracked_from_base"] if p["new_rank"])
        assert c.post("/api/cards/recommendations", json={**REQUEST, "include_research_data":False}).status_code in (403,503)


@requires_db
def test_optimizer_owned_plan_save_and_stale_receipt(auth_client):
    user = auth_client
    created = user.post("/api/squads", json={"name":"Optimizer "+uuid.uuid4().hex,"formation":"4-3-3","game_version":"FC27"})
    assert created.status_code == 201
    sid = created.json()["id"]
    base = "/api/squads/"+sid
    opts = {"include_research_data":"true"}
    copy_id = None
    try:
        candidates = user.get("/api/players", params={**opts, "position":"RW","game_version":"FC27","page_size":2}).json()["items"]
        assert len(candidates) == 2
        for index, player in enumerate(candidates):
            pos = user.get(base+"/tactical-analysis", params=opts).json()["slots"][index]["position"]
            assert user.put(base+f"/slots/{index}",params=opts,json={"slot_index":index,
                            "game_player_id":player["id"],"slot_position":pos}).status_code == 200
        plan = user.get(base+"/optimal-lineup",params=opts).json()
        assert plan["filled"] == 2 and plan["price_status"] == "UNAVAILABLE"
        assert len({s["player"]["entity_id"] for s in plan["slots"] if s["player"]}) == 2
        body = {"name":"Optimized "+uuid.uuid4().hex, "pool":"squad","receipt":plan["receipt"]}
        assert user.post(base+"/optimal-lineup",params=opts,json={**body,"receipt":"0"*64}).status_code == 409
        copied = user.post(base+"/optimal-lineup",params=opts,json=body)
        assert copied.status_code == 201, copied.text
        copy_id = copied.json()["id"]
        saved = user.get("/api/squads/"+copy_id+"/tactical-analysis",params=opts).json()
        assert sum(s["score"] or 0 for s in saved["slots"]) == pytest.approx(plan["total_fit"])
        assert user.get(base,params=opts).json()["slots"][0]["game_player_id"] == candidates[0]["id"]
    finally:
        if copy_id:
            user.delete("/api/squads/"+copy_id)
        user.delete(base)
