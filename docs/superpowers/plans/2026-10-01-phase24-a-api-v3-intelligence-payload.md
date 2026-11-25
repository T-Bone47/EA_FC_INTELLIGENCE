# Phase 24 / Plan A — API v3 Intelligence Payload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `POST /api/v3/recommendations` (plus `/v3/compare`, `/v3/what-if`) the clean, honest, production-facing intelligence API: every response fact comes from `ScoringContext`, every ambiguity (division, ties, evidence, confidence) is explicit.

**Architecture:** The engine is untouched. New pure, DB-free response-block builders live in `backend/services/v3_response_blocks.py` and are called by `RecommendationServiceV3`; routes only thread a request id and map error codes. Plan B (frontend) and Plan C (E2E / performance / security / artifacts) are separate plans written against this plan's final shapes.

**Tech Stack:** Python 3.12, FastAPI, pydantic v2, psycopg 3, pytest; run with `PYTHONUTF8=1 DATABASE_URL=postgresql://eafc:eafc_dev_only@127.0.0.1:5432/eafc_intelligence /home/claude/venv/bin/python -m pytest <path> -q -p no:cacheprovider`.

**Spec:** `docs/superpowers/specs/2026-10-01-phase24-next-development-phase.md` (the owner's `CLAUDE_NEXT_DEVELOPMENT_PHASE.md`) plus the owner's Phase 24 directive §§6–8, 11, 13, 15–17 (quoted in Global Constraints). Baseline for this plan: branch `phase24-v32-api-ui`, full suite **714 passed / 24 failed / 1 skipped**, the 24 failing IDs identical to Phase 23.

## Global Constraints

- "Only expose facts actually supported by ScoringContext. No fabricated fields. No frontend-side ranking. The backend engine remains the single source of truth."
- "Do not silently choose a division. If no division is supplied, follow the existing documented API policy rather than inventing one." (Existing policy: division is an optional user-selected filter; omitted = no filter.)
- FC26/FC27 version wall: FC26 and FC27 never mix; FC27 is `RESEARCH_ONLY`; UT-card scope stays DISABLED; interactions stay disabled; GK model unchanged; confidence stays reporting-only; ranking stays deterministic; OVR is never a scoring input.
- "Do not modify tests merely to make them pass." The 24 classified failures are never hidden, deleted or weakened. Every task ends with the full-suite count unchanged except for the new tests.
- "Never expose API keys or internal database details." Error payloads carry codes and user-actionable text only.
- Engine version stays `3.2.0` (no engine change in this plan). Response fields are only ever added, never renamed or removed.

## Review Focus

1. FC27 request with no `division` (user may assume men only) — response must state `division.scope == "ALL_DIVISIONS"` with per-division counts (Task 2).
2. Candidate with partial evidence (κ < 1) — evidence block lists missing attributes and a wider interval; nothing crashes (Task 4, synthetic pool via an injected repository).
3. GK request — `tactical_fit` uses GK demand attributes only (Task 4).
4. Compare that includes an excluded/out-of-family player, leaving fewer than two ranked players — empty `pairwise`, player listed under `excluded`, no exception (Task 5).
5. What-if with `limit` smaller than `track_top` — tracked players still get real ranks (Task 6).

## File Structure

- Create `backend/services/v3_response_blocks.py` — pure builders `division_block`, `confidence_block`, `evidence_block`, `tactical_fit_block`, `near_tie_block`, `intervals_overlap`.
- Modify `backend/services/recommendation_service_v3.py` — `DIVISIONS_BY_GAME_VERSION`, `check_division`, request-id on compare/what-if, `_entry`/`_serialise` use the blocks, what-if depth.
- Modify `backend/api/routes/recommendations.py` — v3 routes take `Request`, set the unified id, error map entry `DIVISION_NOT_APPLICABLE`.
- Modify `backend/api/schemas_v3.py` — `WhatIfChange.division`.
- Create `scripts/profile_v3_api.py`, `docs/API_V3.md`.
- Tests: create `backend/tests/test_v3_api_contract.py`, `backend/tests/test_v3_response_blocks.py`. Existing tests are not edited.

---

### Task 1: Unified request id

**Files:** Modify `backend/api/routes/recommendations.py` (the three v3 routes), `backend/services/recommendation_service_v3.py` (`compare`, `what_if` signatures); Test `backend/tests/test_v3_api_contract.py`.

**Interfaces:**
- Produces: every v3 response body has `request_id: str` (UUID) equal to the `X-Request-ID` response header. `RecommendationServiceV3.compare(body, entity_ids, request_id: uuid.UUID | None = None)` and `.what_if(base, variants, track_top=10, request_id: uuid.UUID | None = None)` return `request_id` in their dict.

- [ ] **Step 1: Write the failing tests** (module fixture `client = TestClient(app)`; helper `REQ = {"game_version":"FC26","position":"CM","tactical_profile":"BALANCED","limit":10}`)
```python
def test_request_id_header_equals_body_on_recommendations():
    r = client.post("/api/v3/recommendations", json=REQ); assert r.status_code == 200
    assert r.headers["x-request-id"] == r.json()["request_id"]
def test_request_id_header_equals_body_on_compare():
    ids = [x["entity_id"] for x in client.post("/api/v3/recommendations", json=REQ).json()["ranked"][:2]]
    r = client.post("/api/v3/compare", json={"request": REQ, "entity_ids": ids})
    assert r.headers["x-request-id"] == r.json()["request_id"]
def test_request_id_header_equals_body_on_what_if():
    r = client.post("/api/v3/what-if", json={"base": REQ, "variants": [{"label": "press", "tactical_profile": "HIGH_PRESS"}]})
    assert r.headers["x-request-id"] == r.json()["request_id"]
def test_request_id_is_a_uuid_and_unique_per_call():
    a, b = (client.post("/api/v3/recommendations", json=REQ).json()["request_id"] for _ in range(2))
    assert uuid.UUID(a) and a != b
```
- [ ] **Step 2: Run** `pytest backend/tests/test_v3_api_contract.py -k request_id` — Expected: FAIL (header is 8 chars; compare/what-if bodies have no `request_id`).
- [ ] **Step 3: Implement.** In each v3 route add `request: Request`; `rid = uuid.uuid4(); request.state.request_id = str(rid)` (the middleware stamps the header from `request.state` after the handler); pass `request_id=rid` to the service. In `compare`/`what_if` add the optional parameter and put `"request_id": str(request_id or uuid.uuid4())` in the returned dict.
- [ ] **Step 4: Run** the same command — Expected: 4 passed. Also run `pytest backend/tests/test_security.py -q` — Expected: unchanged (it only requires the header to exist).
- [ ] **Step 5: Commit** `git add -A backend && git commit -m "feat(api): unify v3 request id across header and body"`.

### Task 2: Explicit division policy and refusal semantics

**Files:** Create `backend/services/v3_response_blocks.py` (`division_block`); Modify `recommendation_service_v3.py`, `recommendations.py` (`_V3_ERROR_STATUS`); Test `test_v3_api_contract.py`, `test_v3_response_blocks.py`.

**Interfaces:**
- Produces: `DIVISIONS_BY_GAME_VERSION: dict[str, tuple[str, ...]] = {"FC27": ("Men's Football", "Women's Football")}`; `check_division(body: RecommendationRequestV3) -> None` raises `ServiceRefusal("DIVISION_NOT_APPLICABLE", <text naming the game version and why>)` when `body.division` is set for a game version absent from the map; `division_block(requested: str | None, pool: Sequence[Candidate]) -> dict` returns `{"requested": requested, "scope": "FILTERED" | "ALL_DIVISIONS", "candidate_counts": {division_label_or_"UNKNOWN": int}}`. Response gains top-level `division` (recommend only). Error map: `DIVISION_NOT_APPLICABLE` → 422. FC27-without-opt-in stays **503** (pinned by `test_phase23_version_wall_api.py:254`) but its `detail` dict gains `"requires": "include_research_data"`.

- [ ] **Step 1: Write the failing tests** (contract file; `FC27 = {**REQ, "game_version": "FC27", "include_research_data": True}`)
```python
def test_fc26_with_division_is_rejected_not_silently_empty():
    r = client.post("/api/v3/recommendations", json={**REQ, "division": "Men's Football"})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "DIVISION_NOT_APPLICABLE"
def test_fc27_men_and_women_filters_only_return_that_division():
    for d in ("Men's Football", "Women's Football"):
        j = client.post("/api/v3/recommendations", json={**FC27, "division": d}).json()
        assert j["ranked"] and {x["player"]["division"] for x in j["ranked"]} == {d}
        assert j["division"]["scope"] == "FILTERED" and j["division"]["requested"] == d
def test_fc27_without_division_states_all_divisions_explicitly():
    j = client.post("/api/v3/recommendations", json=FC27).json()
    assert j["division"]["scope"] == "ALL_DIVISIONS" and j["division"]["requested"] is None
    assert set(j["division"]["candidate_counts"]) == {"Men's Football", "Women's Football"}
    assert sum(j["division"]["candidate_counts"].values()) == j["counts"]["candidates"]
def test_invalid_division_is_422():
    assert client.post("/api/v3/recommendations", json={**FC27, "division": "Mixed"}).status_code == 422
def test_fc26_and_fc27_results_are_disjoint_versions():
    a = {x["entity_id"] for x in client.post("/api/v3/recommendations", json={**REQ, "limit": 50}).json()["ranked"]}
    b = {x["entity_id"] for x in client.post("/api/v3/recommendations", json={**FC27, "limit": 50}).json()["ranked"]}
    assert a and b and a.isdisjoint(b)
def test_fc27_without_research_optin_is_503_with_machine_readable_requirement():
    r = client.post("/api/v3/recommendations", json={**REQ, "game_version": "FC27"})
    assert r.status_code == 503 and r.json()["detail"]["requires"] == "include_research_data"
```
and in `test_v3_response_blocks.py`: `test_division_block_counts_unknown_division_separately` (a pool with one candidate whose `extra` lacks `division` → `candidate_counts["UNKNOWN"] == 1`).
- [ ] **Step 2: Run** `-k "division or disjoint or optin"` — Expected: FAIL (FC26+division returns 200 with 0 results; no `division` block; no `requires`).
- [ ] **Step 3: Implement** the interfaces above. `check_division` is called first inside `recommend`, `compare` and `what_if` (inside their existing try/refusal handling so it returns the error dict). `_serialise` adds `"division": division_block(body.division, pool)`. The `requires` field is added where `REFERENCE_DISTRIBUTION_UNAVAILABLE` is raised for a RESEARCH_ONLY version without the opt-in.
- [ ] **Step 4: Run** the same command plus `pytest backend/tests/test_phase23_version_wall_api.py -q` — Expected: all pass (existing 503 and division tests unchanged).
- [ ] **Step 5: Commit** `feat(api): explicit division policy; FC26+division refused; machine-readable research opt-in`.

### Task 3: Expose engine confidence (reporting-only)

**Files:** Modify `v3_response_blocks.py` (`confidence_block`), `recommendation_service_v3.py` (`_entry`); Test both test files.

**Interfaces:**
- Produces: `confidence_block(ctx: ScoringContext) -> dict | None` → `None` when `ctx.confidence is None`, else `{"level": ctx.confidence["level"], "score": ctx.confidence["score_v2"], "reasons": list(ctx.confidence["reasons"]), "composition": ctx.confidence["composition"], "reporting_only": True}`. Each ranked entry gains `confidence`. `confidence_note` is kept unchanged for compatibility (deprecated in docs).

- [ ] **Step 1: Write the failing tests**
```python
def test_every_entry_exposes_engine_confidence():
    for e in client.post("/api/v3/recommendations", json={**REQ, "limit": 50}).json()["ranked"]:
        c = e["confidence"]; assert c["level"] in {"HIGH", "MEDIUM", "LOW", "VERY_LOW"} and c["reporting_only"] is True
        assert 0.0 <= c["score"] <= 1.0 and isinstance(c["reasons"], list)
def test_confidence_never_enters_the_score():
    for e in client.post("/api/v3/recommendations", json=REQ).json()["ranked"]:
        sc = e["scoring_context"]; assert abs(e["score"] - sc["c_lo"] * sc["modifier_total"]) < 1e-9
def test_confidence_note_kept_for_compatibility():
    assert "confidence_note" in client.post("/api/v3/recommendations", json=REQ).json()["ranked"][0]
```
and `test_confidence_block_is_none_without_context_confidence` (unit, a `SimpleNamespace(confidence=None)`).
- [ ] **Step 2: Run** `-k confidence` — Expected: FAIL (no `confidence` key). **Step 3: Implement** the interface and add `"confidence": confidence_block(ctx)` in `_entry`. **Step 4: Run** — Expected: pass. **Step 5: Commit** `feat(api): expose reporting-only engine confidence`.

### Task 4: Tactical-fit and evidence blocks

**Files:** Modify `v3_response_blocks.py`, `recommendation_service_v3.py` (`_entry`); Test both.

**Interfaces:**
- Consumes: `ScoringContext` (`position`, `tactical_profile`, `secondary_tactical_profile`, `lam`, `demand_stages`, `per_attribute`, `c_lo`, `c_hi`, `coverage_kappa`, `missing_attributes`, `r`, `r_hi`, `modifiers`), `Candidate.playstyle_data_published`.
- Produces: `tactical_fit_block(ctx, *, top: int = 5) -> dict` = `{"position", "tactical_profile", "secondary_tactical_profile", "lambda", "demand_stages": [{"stage", "inputs"}], "top_demanded": [{"attribute","weight","value","saturated","contribution","covered"}] (the `top` demanded attributes by weight, descending), "capability": {"low": c_lo, "high": c_hi}}`; `evidence_block(ctx, cand: Candidate | None, *, reference_version: str) -> dict` = `{"coverage", "demanded_attributes": int, "published_attributes": int, "missing_attributes": list[str], "interval": {"low","high","width"}, "playstyle": {"published": bool | None, "modifier_applied": float | None, "reason": str | None}, "reference_distribution": reference_version}`. Entries gain `tactical_fit` and `evidence`; no new aggregate score is computed.

- [ ] **Step 1: Write the failing tests**
```python
def test_tactical_fit_lists_only_demanded_attributes_in_weight_order():
    j = client.post("/api/v3/recommendations", json={**REQ, "tactical_profile": "HIGH_PRESS"}).json()
    for e in j["ranked"]:
        rows = e["tactical_fit"]["top_demanded"]; w = [r["weight"] for r in rows]
        assert len(rows) == 5 and w == sorted(w, reverse=True)
        assert all(r["attribute"] in j["demand_vector"] for r in rows)
        assert e["tactical_fit"]["tactical_profile"] == "HIGH_PRESS"
def test_evidence_counts_reconcile_and_interval_is_ordered():
    for e in client.post("/api/v3/recommendations", json=REQ).json()["ranked"]:
        ev = e["evidence"]; assert ev["published_attributes"] + len(ev["missing_attributes"]) == ev["demanded_attributes"]
        assert ev["interval"]["high"] >= ev["interval"]["low"] and ev["coverage"] == e["coverage"]
def test_blocks_survive_explain_top_n_zero():
    assert client.post("/api/v3/recommendations", json={**REQ, "explain_top_n": 0}).json()["ranked"][0]["tactical_fit"]["top_demanded"]
def test_gk_tactical_fit_uses_gk_demand_only():
    j = client.post("/api/v3/recommendations", json={**REQ, "position": "GK"}).json()
    assert all(r["attribute"] in j["demand_vector"] for e in j["ranked"] for r in e["tactical_fit"]["top_demanded"])
```
and unit `test_partial_evidence_candidate_reports_missing_attributes_and_wider_interval` (engine over a `make_candidate` with half the attributes removed → `evidence["missing_attributes"]` non-empty, `interval.width > 0`, `coverage < 1`).
- [ ] **Step 2: Run** `-k "tactical_fit or evidence or blocks or gk_tactical or partial"` — Expected: FAIL (keys absent). **Step 3: Implement** both builders (reuse `_attr_row`-style rounding to 6 dp) and attach in `_entry`. **Step 4: Run** — Expected: pass. **Step 5: Commit** `feat(api): tactical_fit and evidence blocks derived from ScoringContext`.

### Task 5: Near ties in compare, one shared implementation

**Files:** Modify `v3_response_blocks.py` (`near_tie_block`, `intervals_overlap`), `recommendation_service_v3.py` (`_serialise` and `compare` use them; `_overlap = intervals_overlap`); Test `test_v3_api_contract.py`.

**Interfaces:**
- Produces: `intervals_overlap(a: ScoringContext, b: ScoringContext) -> bool` (`b.r_hi > a.r`); `near_tie_block(a, b, eps: float) -> dict | None` returning the existing `near_tie_with_next` dict (`next_entity_id`, `score_gap`, `within_noise_threshold`, `intervals_overlap`, `why_ahead`) or `None`. `eps` comes from the engine's config `tie_epsilon` (0.005). Compare: each `pairwise` item gains `within_noise_threshold: bool`; each `players[i]` (except the last) gains `near_tie_with_next` when `near_tie_block` is not `None`.

- [ ] **Step 1: Write the failing tests**
```python
def test_compare_pairwise_noise_flag_matches_epsilon():
    ids = [x["entity_id"] for x in client.post("/api/v3/recommendations", json=REQ).json()["ranked"][:3]]
    for p in client.post("/api/v3/compare", json={"request": REQ, "entity_ids": ids}).json()["pairwise"]:
        assert p["within_noise_threshold"] == (p["score_gap"] < 0.005)
def test_compare_and_recommend_agree_on_near_tie_for_the_same_pair():
    rec = client.post("/api/v3/recommendations", json=REQ).json()["ranked"]
    cmp_ = client.post("/api/v3/compare", json={"request": REQ, "entity_ids": [rec[0]["entity_id"], rec[1]["entity_id"]]}).json()["players"]
    assert ("near_tie_with_next" in rec[0]) == ("near_tie_with_next" in cmp_[0])
def test_compare_with_out_of_family_player_does_not_crash():
    cm = client.post("/api/v3/recommendations", json=REQ).json()["ranked"][0]["entity_id"]
    gk = client.post("/api/v3/recommendations", json={**REQ, "position": "GK"}).json()["ranked"][0]["entity_id"]
    j = client.post("/api/v3/compare", json={"request": REQ, "entity_ids": [cm, gk]}).json()
    assert j["pairwise"] == [] and gk in {e["entity_id"] for e in j["excluded"]} | set(j["not_found"])
```
- [ ] **Step 2: Run** `-k "compare"` — Expected: FAIL (no `within_noise_threshold`). **Step 3: Implement**, replacing the inline near-tie code in `_serialise` with `near_tie_block` (behavior unchanged for recommendations — `test_v3_*` must still pass). **Step 4: Run** `-k compare` plus `pytest backend/tests/test_phase23_version_wall_api.py backend/tests/test_recommendations_v3_api.py -q` — Expected: pass. **Step 5: Commit** `feat(api): near-tie semantics shared by recommend and compare`.

### Task 6: What-if — division variants and full-depth tracking

**Files:** Modify `backend/api/schemas_v3.py` (`WhatIfChange.division: Optional[Literal["Men's Football","Women's Football"]] = None`, included in `changes()`), `recommendation_service_v3.py` (`what_if`); Test contract file.

**Interfaces:**
- Consumes: `check_division` (Task 2). Produces: what-if ranks base and variants with `limit=50` internally (`"ranking_depth": 50` in the response); `new_rank` is `None` only when the player is excluded by a gate or beyond depth 50; a variant refused by `check_division` appears as `{"label", "changes", "error": "DIVISION_NOT_APPLICABLE", "detail"}`.

- [ ] **Step 1: Write the failing tests**
```python
def test_what_if_tracks_base_top_beyond_display_limit():
    j = client.post("/api/v3/what-if", json={"base": {**REQ, "limit": 3}, "track_top": 10, "variants": [{"label": "press", "tactical_profile": "HIGH_PRESS"}]}).json()
    assert len(j["base_top"]) == 10 and j["ranking_depth"] == 50
    assert all(t["new_rank"] is not None for t in j["variants"][0]["tracked_from_base"])
def test_what_if_variant_top_equals_recommendations_for_the_same_request():
    for change in ({"tactical_profile": "LOW_BLOCK"}, {"position": "CAM"}):
        j = client.post("/api/v3/what-if", json={"base": REQ, "track_top": 10, "variants": [{"label": "v", **change}]}).json()
        rec = client.post("/api/v3/recommendations", json={**REQ, **change, "limit": 10}).json()["ranked"]
        assert [(t["name"], t["score"]) for t in j["variants"][0]["top"]] == [(r["name"], r["score"]) for r in rec]
def test_what_if_division_variant_on_fc27_matches_recommendations():
    j = client.post("/api/v3/what-if", json={"base": FC27, "track_top": 10, "variants": [{"label": "w", "division": "Women's Football"}]}).json()
    rec = client.post("/api/v3/recommendations", json={**FC27, "division": "Women's Football", "limit": 10}).json()["ranked"]
    assert [t["name"] for t in j["variants"][0]["top"]] == [r["name"] for r in rec]
def test_what_if_division_variant_on_fc26_reports_an_error_entry():
    j = client.post("/api/v3/what-if", json={"base": REQ, "variants": [{"label": "d", "division": "Men's Football"}]}).json()
    assert j["variants"][0]["error"] == "DIVISION_NOT_APPLICABLE"
```
- [ ] **Step 2: Run** `-k what_if` — Expected: FAIL (`division` rejected as extra field; no `ranking_depth`). **Step 3: Implement** (internal `limit` override via `model_copy(update={"limit": 50})` for the base and every variant; echo the original base in `request`). **Step 4: Run** `-k what_if` plus the existing what-if tests in `test_phase23_version_wall_api.py` / `test_recommendations_v3_api.py` — Expected: pass. **Step 5: Commit** `feat(api): what-if division variants and full-depth rank tracking`.

### Task 7: Latency profile (measure only)

**Files:** Create `scripts/profile_v3_api.py`; Test `test_v3_api_contract.py`.

**Interfaces:**
- Produces: `profile(game_version: str, position: str, repeats: int = 3) -> dict` with keys `db_load_ms`, `engine_ms`, `serialise_ms`, `total_ms`, `n_candidates` (medians over `repeats`, using `RecommendationServiceV3` internals `_resolve`, `repository.load_candidates`, `RecommendationEngineV3.recommend`, `_serialise`); CLI `--out PATH` writes JSON `{"generated_at", "engine_version", "config_version", "profiles": {"FC26:CM": {...}, "FC27:CM": {...}}}`. No optimization is made in this plan; Plan C decides from these numbers.

- [ ] **Step 1: Test** `test_profile_reports_a_stage_breakdown_that_adds_up`: `p = profile("FC26", "CM", repeats=1)`; assert keys present, all values ≥ 0, `p["n_candidates"] > 1000`, and `abs(p["total_ms"] - (p["db_load_ms"] + p["engine_ms"] + p["serialise_ms"])) <= 0.25 * p["total_ms"]`.
- [ ] **Step 2: Run** — Expected: FAIL (module missing). **Step 3: Implement** the script. **Step 4: Run** the test, then `python scripts/profile_v3_api.py --out artifacts/phase24/PHASE_24_API_RESULTS.json` — Expected: file written with both profiles. **Step 5: Commit** `feat(perf): v3 latency stage profile`.

### Task 8: API contract document and drift guard

**Files:** Create `docs/API_V3.md`; Test `test_v3_api_contract.py`.

**Interfaces:** Consumes the final shapes of Tasks 1–6. Produces `docs/API_V3.md` covering: request fields, division policy, error codes and statuses (including `DIVISION_NOT_APPLICABLE` 422 and the 503 research opt-in), response top-level keys, entry keys, `near_tie_with_next`, `confidence` (reporting-only; `confidence_note` deprecated), `tactical_fit`, `evidence`, compare and what-if shapes.

- [ ] **Step 1: Write the failing test**
```python
def test_api_doc_mentions_every_response_key_and_error_code():
    doc = Path("docs/API_V3.md").read_text(encoding="utf-8"); j = client.post("/api/v3/recommendations", json=REQ).json()
    keys = set(j) | set(j["ranked"][0]) | set(j["ranked"][0]["tactical_fit"]) | set(j["ranked"][0]["evidence"])
    missing = sorted(k for k in keys if f"`{k}`" not in doc)
    assert not missing, missing
    assert "DIVISION_NOT_APPLICABLE" in doc and "include_research_data" in doc
```
- [ ] **Step 2: Run** — Expected: FAIL (file missing). **Step 3: Write** `docs/API_V3.md` from the real responses. **Step 4: Run** the test, then the **full suite** `pytest backend/tests -q -p no:cacheprovider` — Expected: **≥ 714 + new tests passed, 24 failed (identical IDs), 1 skipped**. **Step 5: Commit** `docs(api): v3 contract + drift guard`.
