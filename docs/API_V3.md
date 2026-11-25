# API v3 — contract (Phase 24)

The backend engine is the single source of truth: every number below comes from the engine's `ScoringContext`.
Clients must never rank, re-score or re-explain. Endpoints: `POST /api/v3/recommendations`, `POST /api/v3/compare`, `POST /api/v3/what-if`.

## Request (`/recommendations`)
`game_version` (`FC26` | `FC27`), `position`, `tactical_profile`, `secondary_tactical_profile`, `lam`, `division`,
`include_research_data`, `limit` (max 50), `explain_top_n`. Unknown fields are rejected (422). Limits: see `backend/api/schemas_v3.py`.
FC27 is `RESEARCH_ONLY`: it needs `include_research_data: true` (without it the API answers **503** with `detail.requires = "include_research_data"`).

### Division policy
FC26 has no division label: any `division` on FC26 is **refused with 422 `DIVISION_NOT_APPLICABLE`** (it used to return an empty list silently).
FC27 accepts `"Men's Football"` or `"Women's Football"`. If `division` is omitted nothing is filtered and the response says so:
`division.scope == "ALL_DIVISIONS"` with `division.candidate_counts`. A UI must make the choice explicit; it must never pick one silently.

### Preferences
`attribute_preferences` accepts canonical attribute names. Weight 1 is neutral. Weight 0 is also neutral for compatibility. Positive weights below 1 de-emphasize an attribute and can remove it from the demand vector. The Studio sends weight 2 for its preferred attribute. Requests that remove all effective demand are refused.

`desired_playstyles` requests base-tier preferences and `desired_playstyles_plus` requests plus-tier preferences with partial credit for a base-tier match. Both fields match names case-insensitively and accept a trailing `+`. Use a trailing `+` in `required_playstyles` to require the plus tier. Each requested style contributes up to its tactical relevance for the selected position and profile, subject to the existing modifier cap.

## Errors
| code | HTTP | meaning |
|---|---|---|
| `DIVISION_NOT_APPLICABLE` | 422 | `division` sent for a game version that has none |
| research opt-in missing | 503 | FC27 without `include_research_data` (`detail.requires`) |
| `DATA_LICENSE_GATE_FAILED`, `RESEARCH_DATA_REFUSED_IN_PRODUCTION` | 403 | reference licence policy refused the request |
| validation | 422 | bad field, unknown field, `limit` > 50, malformed JSON |
| body too large | 413 | |
The full code→status map is `_V3_ERROR_STATUS` in `backend/api/routes/recommendations.py`. Error bodies never contain internals.

## Response (`/recommendations`)
Top level: `request_id` (equals the `X-Request-ID` header), `latency_ms`, `engine_version`, `config_version`, `engine`
(`engine_version`, `config_version`, `lambda`), `data_version`, `dataset` (`game_version`, `data_status`, `research_only`, `notice`, `reference_distribution`),
`reference_distribution_version`, `reference_distribution_universe`, `provenance_summary`, `entity_scope` (always `game_player`),
`request` (echo), `division`, `counts` (`candidates`, `excluded`, `not_evaluable`, `ranked_returned`), `demand_vector`,
`tactical_demand_neutral`, `ranked`, `leading_pair`, `excluded` (`entity_id`, `name`, `gate`, `class`, `reason`), `not_evaluable`.

Each `ranked` entry: `rank`, `entity_id`, `entity_type`, `name`, `score`, `score_upper_bound`, `score_interval`, `coverage`, `confidence`,
`confidence_note`, `position_eligibility`, `playstyle_contribution`, `key_strengths`, `key_weaknesses`, `explanation`, `tactical_fit`, `evidence`,
`near_tie_with_next`, `scoring_context`, `player`.
- `score` is the **Intelligence Score** (never an EA rating). `player.overall_rating` is the EA OVR: descriptive only, not a scoring input.
- `score_interval` = [`score`, `score_upper_bound`] (`ranked_on` = low). It reflects uncertainty from **unpublished attributes only**: for a fully published
  player it is a single point. It is not a statistical confidence band.
- `confidence` (`level`, `score`, `reasons`, `composition`, `reporting_only: true`) is the engine's value and **never** affects ranking.
  `confidence_note` is a deprecated coverage label (kappa >= 0.9); prefer `coverage` and `confidence`.
- `explanation` (`reasons`, `trade_offs`, `unknowns`, `reconstructed_score_matches_ranking`) is generated from the ScoringContext.
- `tactical_fit`: `position`, `tactical_profile`, `secondary_tactical_profile`, `lambda`, `demand_stages`, `top_demanded` (the 5 heaviest demanded
  attributes with `attribute`, `value`, `weight`, `contribution`), `capability` (`low`, `high`).
- `evidence`: `coverage`, `demanded_attributes`, `published_attributes`, `missing_attributes`, `interval` (`low`, `high`, `width`),
  `playstyle` (`published`, `modifier_applied`, `reason`).
- `near_tie_with_next` appears only when the next player is not clearly separated: `score_gap`, `within_noise_threshold` (gap < 0.005, the engine's
  `tie_epsilon`), `intervals_overlap` (the next player's upper bound exceeds this score), `why_ahead` (the dimensions that actually separate them).
  A UI must not present such neighbours as a meaningful order.

`leading_pair` is null when fewer than two candidates are returned. Otherwise it names the top two and gives a `status`, `margin_low`, `margin_high` and `noise_threshold`. The signed margin spans the first candidate's lower score minus the second's upper score to the first candidate's upper score minus the second's lower score. `NEAR_TIE` means the ranking scores are within the engine tolerance. `EVIDENCE_SENSITIVE` means missing evidence can narrow the lead below that tolerance. `CLEAR_SEPARATION` means the interval preserves at least that lead. These values are in engine units. The same assessment appears as `decision_evidence` in pairwise and adjacent comparisons.

## Compare — `{"request": <recommendation request>, "entity_ids": [2..5 ids]}`
`request_id`, `request`, `dataset`, `players` (same entry shape, each with `near_tie_with_next` when applicable), `pairwise`
(`higher`, `lower`, `score_gap`, `within_noise_threshold`, `intervals_overlap`, `why`, `decision_evidence`), `excluded`, `not_found`, `note`.
Compare requires distinct player IDs. All players are scored in the same request context. IDs outside the position family are reported and do not receive scores.

## What-if — `{"base": <request>, "variants": [{"label", "position", "tactical_profile", "secondary_tactical_profile", "lam", "division"}], "track_top"}`
Every variant is a fresh engine run at depth 50 (`ranking_depth`), so tracked players get a real rank; `new_rank` is null only when a player is excluded
by a gate or ranked beyond depth 50. Response: `request_id`, `request`, `dataset`, `base_top`, `variants` (`top`, `entered_top`, `tracked_from_base`,
`demand_shift`, or `error`/`detail`), `ranking_depth`, `note`. The base and each successful variant include `candidate_count` and `leading_pair`. Each variant includes a unique `request_id` and the base `parent_request_id`. Changing position or division can change the candidate pool. A variant's `top` equals `/recommendations` for the same changed request.

## Determinism
Same request, same data => identical ranking and scores. Only `request_id` and `latency_ms` differ between calls.
