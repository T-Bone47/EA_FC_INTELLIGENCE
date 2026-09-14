"""API surface tests: health, meta, search, player/card pages, safe errors."""
from __future__ import annotations

import pytest

from backend.tests.conftest import requires_db

pytestmark = requires_db


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    # legacy alias kept for compatibility
    assert client.get("/api/v1/health").status_code == 200


def test_ready(client):
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    assert r.json()["game_players"] >= 16228


def test_api_root_lists_canonical_endpoints(client):
    body = client.get("/api").json()
    assert "POST /api/recommendations" in body["canonical_endpoints"]


def test_meta_reference_fc26(client):
    r = client.get("/api/meta/reference?game_version=FC26")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ACTIVE"
    assert "CM" in d["positions"] and "GK" in d["positions"]
    assert len(d["playstyles"]) == 36
    assert d["capabilities"]["market_data_available"] is False
    assert d["capabilities"]["chemistry_rules_verified"] is False
    assert "4-2-3-1" in d["formations"]


def test_meta_reference_fc27_no_data(client):
    d = client.get("/api/meta/reference?game_version=FC27").json()
    assert d["status"] == "NO_DATA"
    assert d["positions"] == []


def test_meta_rejects_unknown_version(client):
    assert client.get("/api/meta/reference?game_version=FC25").status_code == 422


def test_search_basic(client):
    d = client.get("/api/players?game_version=FC26&q=mbappe&page_size=5").json()
    assert d["total"] >= 1
    names = [i["display_name"] for i in d["items"]]
    assert any("Mbappé" in n for n in names)     # accent-insensitive


def test_search_pagination_bounds(client):
    d1 = client.get("/api/players?game_version=FC26&page=1&page_size=10").json()
    d2 = client.get("/api/players?game_version=FC26&page=2&page_size=10").json()
    assert len(d1["items"]) == 10 and len(d2["items"]) == 10
    assert {i["id"] for i in d1["items"]}.isdisjoint({i["id"] for i in d2["items"]})
    assert d1["total"] == d2["total"] >= 16228


def test_search_page_size_capped(client):
    assert client.get("/api/players?game_version=FC26&page_size=5000").status_code == 422


def test_search_filters(client):
    d = client.get("/api/players", params={
        "game_version": "FC26", "position": "GK", "ovr_min": 85,
        "sort": "overall_rating", "sort_dir": "desc", "page_size": 10}).json()
    assert d["total"] >= 10
    for i in d["items"]:
        assert i["position_primary"] == "GK" and i["overall_rating"] >= 85


def test_search_playstyle_filter(client):
    d = client.get("/api/players", params={"game_version": "FC26",
                                           "playstyle": "Rapid", "page_size": 3}).json()
    assert d["total"] > 100


def test_search_nation_league_facets(client):
    f = client.get("/api/players/facets?game_version=FC26").json()
    nations = {n["nation"] for n in f["nations"]}
    assert "France" in nations and len(f["leagues"]) >= 40


def test_player_page(client):
    pid = client.get("/api/players?game_version=FC26&q=kylian&page_size=1").json()["items"][0]["id"]
    d = client.get(f"/api/players/{pid}?game_version=FC26").json()
    gp = d["game_player"]
    assert gp["display_name"] == "Kylian Mbappé"
    assert d["attributes"]["finishing"] is not None
    assert d["provenance"]["usage_status"] == "LICENSED"
    assert d["freshness"]["last_observed"]
    # card list exists but real cards are not ingested
    assert d["cards"] == []
    assert isinstance(d["playstyles"], list) and d["playstyle_data_published"]


def test_player_page_gk_shape(client):
    d0 = client.get("/api/players", params={"game_version": "FC26", "position": "GK",
                                            "ovr_min": 88, "page_size": 1}).json()
    pid = d0["items"][0]["id"]
    d = client.get(f"/api/players/{pid}?game_version=FC26").json()
    a = d["attributes"]
    # canonical GK shape: outfield details UNKNOWN, GK attrs KNOWN (forensics F1/F2)
    assert a["gk_diving"] is not None and a["gk_reflexes"] is not None
    assert a["finishing"] is None and a["stamina"] is None


def test_player_page_404(client):
    import uuid
    r = client.get(f"/api/players/{uuid.uuid4()}?game_version=FC26")
    assert r.status_code == 404


def test_synthetic_cards_hidden_from_production_surface(client):
    # synthetic cards exist in DB but must not surface on production endpoints
    from backend.core.db import query
    rows = query("SELECT id FROM ut_card WHERE is_synthetic LIMIT 1")
    assert rows, "fixture expects synthetic cards to be ingested"
    r = client.get(f"/api/cards/{rows[0]['id']}?game_version=FC26")
    assert r.status_code == 404
    d = client.get("/api/players?game_version=FC26&q=Fixture&page_size=5").json()
    assert d["total"] == 0


def test_unknown_route_no_internals_leaked(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert "Traceback" not in r.text and "psycopg" not in r.text
