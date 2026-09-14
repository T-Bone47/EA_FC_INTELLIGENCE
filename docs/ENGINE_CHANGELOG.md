# ENGINE CHANGELOG

## Phase 4 — 2026-09-14

* Added the required `3-4-2-1` formation to both the API reference layout and
  the scoring-side tactical-slot model. Wing midfielders, paired central
  midfielders, two attacking midfielders, and the striker now receive
  formation-specific duties and attribute emphasis through the existing V2
  path.
* Added a regression contract asserting every Phase 4 minimum formation is
  present and that its UI layout and scoring slots stay aligned.
* Added Kaggle source forensics and field-authority records. No GPL/CC BY
  research source was promoted into the canonical production foundation.

All notable engine changes. Versioning: `ENGINE_VERSION` in
`backend/services/engine_config.py`, reported on every response as
`engine_version` and in `telemetry.engine_version`.

Policy: the engine is **evolved in place** — no `recommendation_engine_v3`,
no `_new`/`_final` variants, no disconnected parallel engine. Legacy request
shapes must keep producing identical scores unless a change is documented here
with evidence (§47/§69/§70).

---

## 2.2.0 — 2026-09-14 — Phase 3: Card Intelligence

Evolved in place (§0): same engine, same weights, same legacy behaviour.
Adds production-grade UT CARD intelligence and the data-ready card pipeline.
Full design: `docs/CARD_INTELLIGENCE.md` (+ CARD_DATA_MODEL / CARD_IDENTITY /
CARD_SCORING / CARD_PROVENANCE / CARD_CHEMISTRY / CARD_MARKET /
CARD_DATA_ACQUISITION, `DATASET_FORENSICS_REPORT.md`).

### Fixed (correctness)

* **§5 violation removed**: `Candidate.from_ut_card` used to back-fill base
  player attributes under card overrides and inherit base PlayStyles when the
  card's list was empty. Now card candidates carry card-published values only;
  anything unpublished is UNKNOWN. Base player contributes labelled link facts
  (nation/club/league/secondary positions) exclusively.
* `Normalizer.normalize_card` now **rejects cards without a source_card_id**
  instead of deriving an identity from `None` (§4).

### Added — schema (migration `005_card_intelligence.sql`, additive)

`ut_card`: canonical_card_id (unique per version), card_type, rarity_raw,
release_date, valid_from/to, identity_status/rule, playstyle_data_published ·
new tables: `ut_card_role`, `card_evolution`, `card_availability`,
`chemistry_rule`, `meta_signal` (firewalled), `ingestion_run`,
`ingestion_quarantine` · `card_price`: source_id, currency, validity window,
source_authority · retrieval indexes (§49/§50), incl. partial indexes behind
the synthetic firewall.

### Added — pipeline & data governance

* `ingestion/forensics.py` — mandatory pre-import dataset forensics (§23):
  duplicates, identity coverage, version contamination, impossible ratings,
  position/PlayStyle vocabulary, PS+ cap, price/timestamp coverage → verdict
  PASS/REVIEW/REJECT + markdown report.
* `ingestion/run_tracker.py` + `scripts/activate_card_dataset.py` — one-command
  atomic activation (§26/§27): legal gate → forensics → run record → normalize
  → validate → quarantine → staging → promote (single transaction) →
  watermarks → cache invalidate → integrity → golden regression → report.
  Non-permitted sources are refused; dry-run mode for research.
* `ingestion/meta_signals.py` — META_SIGNAL schema+adapter first (§18/§19);
  hard firewall: no code path to canonical tables; RESEARCH_ONLY labelling.
* `scripts/register_card_sources.py` — per-source license/permission research
  persisted (§22): EA official FUT DB discontinued (404); Kaggle card datasets
  RESEARCH_ONLY (images/GPL-3); FutDB et al. UNKNOWN-gated; FUTBIN/FUTWIZ/
  FUT.GG/WeFUT NOT_PERMITTED. **No permitted structured FC26 card source
  exists yet — system is DATA-READY** (`docs/CARD_DATA_ACQUISITION.md`).

### Added — engine & services (all deterministic, config-driven)

* `CandidateRepository.load_cards` — production card pool (§11) with its own
  cache namespace + watermark (§28) covering cards/versions/prices/chemistry
  rules (no stale prices after updates, §31).
* `card_value_service` — verified-price status, freshness (FRESH/AGING/STALE),
  budget status (BUDGET_UNVERIFIED honesty), value = marginal contextual
  utility per verified cost (§14), price history that is never manufactured
  (§48). New tunables: VALUE_PRICE_UNIT, VALUE_MIN_PRICE_COINS,
  PRICE_FRESH_DAYS, PRICE_STALE_DAYS, VALUE_RANK_TOP_N.
* `chemistry_service` — structural fit (labelled, factual) vs chemistry score
  (only from verified rules; none exist ⇒ CHEMISTRY_UNKNOWN) (§15);
  squad_impact for §16 prep. Tunable: CHEMISTRY_REQUIRE_VERIFIED_RULES.
* `role_fit_service` — card-published Role familiarity via configurable
  reference mapping CARD_ROLE_FAMILIARITY_SCORES; requested role only; no
  generic bonus (§9). Roles and archetypes remain distinct concepts.
* `counterfactual.card_counterfactuals` — §35 card variants: +100K budget
  (BUDGET_COUNTERFACTUAL_STEP), top card without PS+, alternate position,
  squad-member removal, honest chemistry unavailability.
* `recommendation_service` — ut_card scope loads the card pool; card-scope
  payloads add `card_value`, `pareto.best_value/best_within_budget` (§17),
  `card_counterfactuals`, `chemistry`. Legacy (auto/game_player) payloads
  bit-identical.
* `comparison_service` — pool spans players+cards; card columns expose the
  `card` provenance block; mixed-scope comparisons carry an explicit
  scope_note (§12).
* §29 precomputation: per-candidate `feature_cache` (archetype scores,
  dominant archetype, gameplay profile, versatility, interaction features,
  data confidence) + memoized normalized weight tables in `ScoringConfig`.
  Measured (warm, this sandbox): intelligence-CM 855→~795 ms, full pool
  ~880→~810 ms (±15% machine noise); 10K-warm target <1000 ms holds.

### Added — API (additive only, §41)

`GET /api/cards` (server-side filter/sort/paginate), `/api/cards/{id}/versions`,
`/api/cards/{id}/prices`, `/api/cards/{id}/value`, `GET /api/card-data-status`
(§44). Existing `GET /api/cards/{card_id}` (players.py) untouched; card
comparison via existing `POST /api/compare` — no duplicate endpoints.

### Added — frontend (§42–§44)

`/cards` discovery page (honest NO_DATA empty state + data-quality panel),
premium `/cards/:id` page (identity block, card-level attributes with UNKNOWN
hatching, PlayStyle tiers, version history, price history, base-player link,
chemistry disclaimer), `DataQualityPanel` component, nav entry. 41 tests,
tsc clean.

### Tests

* New: `test_card_model.py` (18), `test_card_value_chemistry.py` (18),
  `test_card_scenarios.py` (22 incl. §45 no-hallucination + §46 conflicts +
  §39 adversarial/determinism), `test_card_api.py` (9),
  `test_card_ingestion_phase3.py` (9). Backend **338 passed**.
* `scripts/verify_goldens.py` — permanent golden gate (§57): S1–S8 +
  FC27 wall **bit-identical** after every Phase 3 change.
* Engine version bumped 2.1.0 → 2.2.0 (payload metadata only; no scoring
  change — goldens prove it).

---

## 2.1.0 — 2026-09-14 — Intelligence Engine master upgrade

The largest change to the engine since V2. Adds a layered intelligence system
(intent → constraints → retrieval → eligibility → fit layers → squad → value →
profile → overall → confidence → Pareto → explanation) while keeping every
legacy path bit-identical.

### Added — new modules

| module | what it adds |
|---|---|
| `engine_config.py` | single explicit home for every tunable (§46): score bands + `MIN_BAND_EVIDENCE`, saturation knees/excess, interaction caps, playstyle context bounds, overall-bias factors, confidence-v2 weights/levels, diversity scan size |
| `formations.py` | formation slots (11 formations incl. new 4-2-2-2), duties, 6 tactical dimensions, `dimension_vector`, `attribute_weights_from_dimensions`, `tactical_weights_from_dimensions`, slot-adjusted weights (§6/§7) |
| `intent.py`, `intent_parser.py` | structured intent with per-field provenance (source / confidence / explicit-vs-inferred), hard vs soft separation, unrecognized-fragment reporting (§2/§3/§4) |
| `archetypes.py` | 17 **computed** archetypes, `dominant_archetype`, `gameplay_profile` (ENGINE-DERIVED labels, capped at 4 with disclosure), `versatility` (§12/§14/§32) |
| `attribute_model.py` | band soft-targets, per-attribute saturation, explainable interactions, position×slot×dimension importance (§8-§11) |
| `playstyle_context.py` | contextual PlayStyle value + position affinity table over the real 36-PlayStyle vocabulary (§11/§12) |
| `squad_intelligence.py` | advisory structural fit (link density / archetype diversity / complementarity) and replacement verdicts UPGRADE / SIDEGRADE / DOWNGRADE (§22/§28) |
| `counterfactual.py` | sensitivity analysis with a 0.005 noise threshold + 4 counterfactual families (§35/§36) |
| `confidence_v2.py` | renormalized 4-factor confidence with freshness / authority / identity (§24) |
| `engine_evaluation.py` | 12-scenario qualitative suite (§49) |
| `engine_experiments.py` | offline config experiments persisted to `experiment` / `experiment_result`, never touching production (§48) |
| `feedback_analytics.py` | deterministic label measurement; ML gated at 500 labels + 80% context coverage (§33) |

### Added — engine

* `ENGINE_VERSION` tracking; `RecommendationResult.engine_version`.
* `effective_weights(req)`: `overall_quality_bias` (low/normal/high) and
  `archetype_fit` at 0.10 only when an archetype is requested; renormalized.
* Extended hard constraints: required PlayStyles, league, club, nation —
  each with an explicit "cannot verify" exclusion when the underlying field
  is UNKNOWN (never silently passed, never silently dropped).
* `score_band()` with the §51 honesty gate: a score resting on less than
  `MIN_BAND_EVIDENCE` (0.5) of component weight gets
  `INSUFFICIENT_EVIDENCE` instead of a qualitative band.
* `CandidateEvaluation`: `component_weights` (effective, redistributed),
  `evidence_coverage`, `score_band`, `intelligence`, `squad_structural`,
  `constraints`, and the `insufficient_evidence` property.
* `constraint_report()` → satisfied / failed / unknown (§54).
* Top-25 enrichment with ENGINE-DERIVED analytics; Pareto gains
  `best_archetype_fit` and `best_alternative_archetype`; unavailable
  dimensions now carry reasons.
* `recommend()` accepts `squad_members` and `replacement_current`.
* Per-request hoisting of `effective_weights`/`_context` out of the
  per-candidate loop (§57 performance).

### Added — requirements / API / UI

* `UserRequirements`: `archetype`, `slot`, `secondary_tactical_profile`,
  `attribute_bands`, `enable_interactions`, `enable_saturation`,
  `enable_playstyle_context`, `required_playstyles`, `required_league`,
  `required_club`, `required_nation`, `replacement_for`,
  `overall_quality_bias`, `complement_hint`, `disable_counterfactuals`
  — all optional and validated.
* 5 new tactical profiles (HIGH_PRESS, MID_BLOCK, LOW_BLOCK, FAST_BUILD_UP,
  SLOW_BUILD_UP) → 16 total; formation 4-2-2-2 → 11 total.
* `recommendation_confidence.compute()` gained an optional `weights`
  parameter (default preserves prior behavior exactly).
* API request schema: the new fields above, plus `AttributeBandIn`.
  Response: `engine_version`, `score_band`, `evidence_coverage`,
  `intelligence`, `constraints`, `sensitivity`, `counterfactuals`,
  `replacement_analysis`, `confidence_v2`, `provenance`, `telemetry`,
  `candidate_pool`. **All additive** — no field removed or renamed.
* New endpoint `GET /api/recommendations/feedback/analytics` (§33 phase 2).
* `GET /api/meta/reference` additionally returns `tactical_dimensions`,
  `formation_slots`, `archetypes`, `quality_bands`, `engine_version`.
* `POST /api/recommendations/parse-intent` now delegates to the structured
  parser while preserving the legacy flat draft keys.
* UI: intelligence layer controls (secondary tactics, archetype, must-have
  PlayStyles, OVR emphasis, three layer toggles), score-band badges,
  ENGINE-DERIVED chips, and a "Decision intelligence" panel with
  constraints / sensitivity / counterfactuals.

### Fixed (found by the new tests)

* `counterfactual.py` re-scored with a different ordering contract than the
  engine (missing the floor-breaker key) — now identical.
* `intent_parser`: a PlayStyle mentioned twice was classified by its first
  occurrence only; "must have X" in a later clause is now honored.
* `intent_parser`: multi-word PlayStyle names ("Tiki Taka") could be consumed
  by a tactical sub-string ("tiki"). PlayStyles are now matched before
  tactical phrases and consumed phrases are masked.
* `intent_parser`: a mandatory marker in a previous clause leaked into the
  next one ("must have X, would love Y" made Y mandatory). Marker detection
  is now clause-scoped.
* `attribute_model`: band lookup only accepted dicts, so the API path
  (which passes `AttributeBand` dataclasses) raised `TypeError`.
* `archetypes.gameplay_profile` emitted up to 7 labels for a world-class
  player, making the label set meaningless — capped at the 4 strongest with
  the remainder disclosed as `additional_qualified`.
* `recommendation_engine_v2.recommend()` called `counterfactuals()` twice and
  referenced an undefined local — dead call removed, variable corrected.

### Explicitly NOT changed

* Component weights remain BASELINE V1 `0.15/0.30/0.15/0.15/0.15/0.10`.
* UNKNOWN-component weight redistribution and the ranking order contract
  (`below_floor`, `-score`, `-OVR`, name, entity_id) are unchanged.
* **Considered and rejected:** down-ranking candidates whose evidence
  coverage is below `MIN_BAND_EVIDENCE`. It broke
  `test_strict_mode_excludes_below_floor` and contradicts the pinned contract
  that UNKNOWN data never penalizes. Honesty is instead carried by the
  `INSUFFICIENT_EVIDENCE` band, low confidence and `unknown_factors`.
  Scores stay legacy-exact; interpretation is where the caveat lives.

### Verification

* Backend **262 passed** (161 baseline + 101 new across
  `test_engine_intelligence.py`, `test_engine_scenarios.py`,
  `test_engine_robustness.py`, `test_engine_ovr_trap.py`,
  `test_engine_unknown_data.py`).
* Frontend **38 passed** (33 baseline + 5 new), `tsc --noEmit` clean.
* Golden regression: all 8 scenarios S1–S8 **bit-identical** (winner, score to
  1e-9, evaluation count, confidence, weights, full ranked order).
* FC27 zero-data wall still returns 404 with an honest message.

---

## 2.0.0 — 2026-09-14 — V2 baseline (pre-upgrade)

Recorded in `docs/ENGINE_BASELINE.md` and frozen in
`benchmarks/engine_baseline_v2_2026-09-14.json`. Component weights
0.15/0.30/0.15/0.15/0.15/0.10, UNKNOWN redistribution, 0.5 attribute
coverage gate, position ladder 1.0/0.85/adjacency/0.05, playstyle base ×1.0 /
plus ×1.5 / base-only 0.75, confidence 0.7×coverage + 0.3×entity,
strict-tactics floor 0.35, FC26 PS+ cap 1, FC27 NO_DATA 404 wall.
161 backend / 33 frontend tests.
