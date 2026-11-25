"""Phase 24 / Plan A -- API v3 contract tests (real FastAPI app + real Postgres)."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)
REQ = {"game_version": "FC26", "position": "CM", "tactical_profile": "BALANCED", "limit": 10}
FC27 = {**REQ, "game_version": "FC27", "include_research_data": True}


def post(path, body):
    return client.post(path, json=body)


# ---------------------------------------------------------------- Task 1: request id
def test_request_id_header_equals_body_on_recommendations():
    r = post("/api/v3/recommendations", REQ); assert r.status_code == 200
    assert r.headers["x-request-id"] == r.json()["request_id"]


def test_request_id_header_equals_body_on_compare():
    ids = [x["entity_id"] for x in post("/api/v3/recommendations", REQ).json()["ranked"][:2]]
    r = post("/api/v3/compare", {"request": REQ, "entity_ids": ids}); assert r.status_code == 200
    assert r.headers["x-request-id"] == r.json()["request_id"]


def test_request_id_header_equals_body_on_what_if():
    r = post("/api/v3/what-if", {"base": REQ, "variants": [{"label": "press", "tactical_profile": "HIGH_PRESS"}]})
    assert r.status_code == 200 and r.headers["x-request-id"] == r.json()["request_id"]


def test_request_id_is_a_uuid_and_unique_per_call():
    a, b = (post("/api/v3/recommendations", REQ).json()["request_id"] for _ in range(2))
    assert uuid.UUID(a) and a != b


# ---------------------------------------------------------------- Task 2: division policy
def test_fc26_with_division_is_rejected_not_silently_empty():
    r = post("/api/v3/recommendations", {**REQ, "division": "Men's Football"})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "DIVISION_NOT_APPLICABLE"


def test_fc26_division_scope_is_not_applicable():
    j = post("/api/v3/recommendations", REQ).json()
    assert j["division"] == {"requested": None, "scope": "NOT_APPLICABLE", "candidate_counts": {}}


def test_fc27_men_and_women_filters_only_return_that_division():
    for d in ("Men's Football", "Women's Football"):
        j = post("/api/v3/recommendations", {**FC27, "division": d}).json()
        assert j["ranked"] and {x["player"]["division"] for x in j["ranked"]} == {d}
        assert j["division"]["scope"] == "FILTERED" and j["division"]["requested"] == d


def test_fc27_without_division_states_all_divisions_explicitly():
    j = post("/api/v3/recommendations", FC27).json()
    assert j["division"]["scope"] == "ALL_DIVISIONS" and j["division"]["requested"] is None
    assert set(j["division"]["candidate_counts"]) == {"Men's Football", "Women's Football"}
    assert sum(j["division"]["candidate_counts"].values()) == j["counts"]["candidates"]


def test_invalid_division_is_422():
    assert post("/api/v3/recommendations", {**FC27, "division": "Mixed"}).status_code == 422


def test_fc26_and_fc27_results_are_disjoint_versions():
    a = {x["entity_id"] for x in post("/api/v3/recommendations", {**REQ, "limit": 50}).json()["ranked"]}
    b = {x["entity_id"] for x in post("/api/v3/recommendations", {**FC27, "limit": 50}).json()["ranked"]}
    assert a and b and a.isdisjoint(b)


def test_fc27_without_research_optin_is_503_with_machine_readable_requirement():
    r = post("/api/v3/recommendations", {**REQ, "game_version": "FC27"})
    assert r.status_code == 503 and r.json()["detail"]["requires"] == "include_research_data"


# ------------------------------------------------------------------ Task 3: engine confidence (reporting-only)
def rec(body):
    return post("/api/v3/recommendations", body).json()


def test_every_entry_exposes_engine_confidence():
    for e in rec({**REQ, "limit": 50})["ranked"]:
        c = e["confidence"]
        assert c["level"] in {"HIGH", "MEDIUM", "LOW", "VERY_LOW"} and c["reporting_only"] is True
        assert 0.0 <= c["score"] <= 1.0 and isinstance(c["reasons"], list)


def test_confidence_never_enters_the_score():
    for e in rec(REQ)["ranked"]:
        sc = e["scoring_context"]
        assert abs(e["score"] - sc["c_lo"] * sc["modifier_total"]) < 1e-9


def test_confidence_note_kept_for_compatibility():
    assert "confidence_note" in rec(REQ)["ranked"][0]


# ------------------------------------------------------------------ Task 4: tactical_fit + evidence
def test_tactical_fit_lists_only_demanded_attributes_in_weight_order():
    j = rec({**REQ, "tactical_profile": "HIGH_PRESS"})
    for e in j["ranked"]:
        tf = e["tactical_fit"]; w = [r["weight"] for r in tf["top_demanded"]]
        assert len(w) == 5 and w == sorted(w, reverse=True)
        assert all(r["attribute"] in j["demand_vector"] for r in tf["top_demanded"])
        assert tf["tactical_profile"] == "HIGH_PRESS" and tf["position"] == "CM"


def test_evidence_counts_reconcile_and_interval_is_ordered():
    for e in rec(REQ)["ranked"]:
        ev = e["evidence"]
        assert ev["published_attributes"] + len(ev["missing_attributes"]) == ev["demanded_attributes"]
        assert ev["interval"]["high"] >= ev["interval"]["low"] and ev["coverage"] == e["coverage"]


def test_blocks_survive_explain_top_n_zero():
    r = post("/api/v3/recommendations", {**REQ, "explain_top_n": 0}); assert r.status_code == 200, r.text
    assert r.json()["ranked"][0]["tactical_fit"]["top_demanded"]


def test_gk_tactical_fit_uses_gk_demand_only():
    j = rec({**REQ, "position": "GK"})
    assert all(r["attribute"] in j["demand_vector"] for e in j["ranked"] for r in e["tactical_fit"]["top_demanded"])


# ------------------------------------------------------------------ Task 5: near ties in compare
def test_compare_pairwise_noise_flag_matches_epsilon():
    ids = [x["entity_id"] for x in rec(REQ)["ranked"][:3]]
    j = post("/api/v3/compare", {"request": REQ, "entity_ids": ids}).json()
    assert j["pairwise"]
    for p in j["pairwise"]:
        assert p["within_noise_threshold"] == (p["score_gap"] < 0.005)


def test_compare_and_recommend_agree_on_near_tie_for_the_same_pair():
    r = rec(REQ)["ranked"]
    c = post("/api/v3/compare", {"request": REQ, "entity_ids": [r[0]["entity_id"], r[1]["entity_id"]]}).json()["players"]
    assert c[0].get("near_tie_with_next") == r[0].get("near_tie_with_next")


def test_compare_with_out_of_family_player_does_not_crash():
    cm = rec(REQ)["ranked"][0]["entity_id"]; gk = rec({**REQ, "position": "GK"})["ranked"][0]["entity_id"]
    j = post("/api/v3/compare", {"request": REQ, "entity_ids": [cm, gk]}).json()
    assert j["pairwise"] == [] and gk in {e["entity_id"] for e in j["excluded"]} | set(j["not_found"])


# ------------------------------------------------------------------ Task 6: what-if
def test_what_if_tracks_base_top_beyond_display_limit():
    j = post("/api/v3/what-if", {"base": {**REQ, "limit": 3}, "track_top": 10,
                                 "variants": [{"label": "same", "position": "CM"}]}).json()
    assert len(j["base_top"]) == 10 and j["ranking_depth"] == 50
    t = j["variants"][0]["tracked_from_base"]       # a no-op variant must reproduce the base ranks exactly
    assert [x["new_rank"] for x in t] == [x["base_rank"] for x in t]


def test_what_if_variant_top_equals_recommendations_for_the_same_request():
    for change in ({"tactical_profile": "LOW_BLOCK"}, {"position": "CAM"}):
        j = post("/api/v3/what-if", {"base": REQ, "track_top": 10, "variants": [{"label": "v", **change}]}).json()
        r = rec({**REQ, **change, "limit": 10})["ranked"]
        assert [(t["name"], t["score"]) for t in j["variants"][0]["top"]] == [(x["name"], x["score"]) for x in r]


def test_what_if_division_variant_on_fc27_matches_recommendations():
    j = post("/api/v3/what-if", {"base": FC27, "track_top": 10, "variants": [{"label": "w", "division": "Women's Football"}]}).json()
    r = rec({**FC27, "division": "Women's Football", "limit": 10})["ranked"]
    assert [t["name"] for t in j["variants"][0]["top"]] == [x["name"] for x in r]


def test_what_if_division_variant_on_fc26_reports_an_error_entry():
    j = post("/api/v3/what-if", {"base": REQ, "variants": [{"label": "d", "division": "Men's Football"}]}).json()
    assert j["variants"][0]["error"] == "DIVISION_NOT_APPLICABLE"


# ------------------------------------------------------------------ Task 7: latency stage profile
def test_profile_reports_a_stage_breakdown_that_adds_up():
    from scripts.profile_v3_api import profile
    p = profile("FC26", "CM", repeats=1)
    assert set(p) >= {"db_load_ms", "engine_ms", "serialise_ms", "total_ms", "n_candidates"}
    stages = ("db_load_ms", "engine_ms", "serialise_ms")
    assert all(p[k] >= 0 for k in stages) and p["n_candidates"] > 1000
    assert abs(p["total_ms"] - sum(p[k] for k in stages)) <= 0.25 * p["total_ms"]


# ------------------------------------------------------------------ Task 8: documentation + determinism
def test_api_doc_mentions_every_response_key_and_error_code():
    doc = Path("docs/API_V3.md").read_text(encoding="utf-8"); j = rec(REQ)
    keys = set(j) | set().union(*(set(e) | set(e["tactical_fit"]) | set(e["evidence"]) for e in j["ranked"]))
    missing = sorted(k for k in keys if f"`{k}`" not in doc)
    assert not missing, missing
    assert "DIVISION_NOT_APPLICABLE" in doc and "include_research_data" in doc


def test_api_is_deterministic_apart_from_request_id_and_latency():
    a, b = (rec({**REQ, "limit": 25}) for _ in range(2))
    for j in (a, b):
        j.pop("request_id"); j.pop("latency_ms")
    assert a == b


# ------------------------------------------------------------------ Plan A addendum: transfer size
def test_large_responses_are_gzip_compressed_when_the_client_accepts_it():
    r = client.post("/api/v3/recommendations", json=REQ, headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200 and r.headers.get("content-encoding") == "gzip"
