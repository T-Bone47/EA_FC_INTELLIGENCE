# INTELLIGENCE ENGINE MASTER UPGRADE — FINAL REPORT

Project: EA FC Player Intelligence · Engine: **v2.0 → v2.1.0** · Date: 2026-09-14
Mandate: transform the existing engine into a world-class UT Player Intelligence
Engine that answers **"which player/card is best for THIS user's exact context?"**

---

## 1. Executive summary

The V2 engine was **understood, then evolved in place** — no v3, no parallel
engine, no rewrite-from-scratch. A layered intelligence system was added
(intent → hard constraints → retrieval → position/role eligibility →
attribute/tactical/playstyle/role fit → squad → budget/value → gameplay
profile → overall suitability → confidence → Pareto → explanation), every
stage inspectable and evidence-backed. All **8 golden scenarios remain
bit-identical** for legacy requests; the API changed **additively only**.
Backend tests went **161 → 262**, frontend **33 → 38**, all green. Both
mandatory tests pass: the engine picks an 81-OVR better fit over a 90-OVR
mismatch (§50), and missing data never scores as "bad" nor as "equally
certain" (§51). The engine is FC27-ready with zero data.

## 2. Scope & strategy

Constraint: do not destroy working behavior without evidence of superiority;
do not game tests; baseline weights (0.15/0.30/0.15/0.15/0.15/0.10 =
BASELINE V1) frozen. Strategy: (a) capture a golden baseline first
(`benchmarks/engine_baseline_v2_2026-09-14.json`, `docs/ENGINE_BASELINE.md`);
(b) add new modules beside the engine; (c) integrate behind opt-in request
fields so absent fields ⇒ exact legacy code paths; (d) re-verify goldens
after every phase. One documented rejection: down-ranking thin-evidence
candidates was implemented, broke a pinned legacy contract ("UNKNOWN never
penalizes"), and was **reverted** — honesty moved to the band/confidence
layer instead (see §16).

## 3. Architecture — layered decision system (§4)

`docs/INTELLIGENCE_ENGINE_ARCHITECTURE.md` holds the full map. Decision flow:
intent parse → validated UserRequirements → version guard → synthetic
firewall → retrieval (hard prefilters) → hard constraints (exclude + reason /
cannot-verify report) → seven component fits (+ optional archetype_fit), each
KNOWN / UNKNOWN / INSUFFICIENT_EVIDENCE → effective weights → weighted score
(UNKNOWN redistributed) → tactical floor → deterministic sort → top-25
enrichment (bands, derived analytics, constraint report) → Pareto →
sensitivity/counterfactuals → replacement analysis → service layer
(explanations, confidence v2, freshness, provenance, telemetry). No stage is
a black box; there is no single opaque formula.

## 4. Intent understanding (§2/§3/§4)

`intent_parser.parse()` converts free text into a `ParsedIntent`: every
emitted field carries `source` (USER_TEXT/INFERRED/DEFAULT), `confidence`
(HIGH/MEDIUM/LOW) and `explicit` (bool). Hard constraints and soft preferences
are separated at parse time; unrecognized fragments are recorded, never
guessed; roles referenced in text produce an INSUFFICIENT_EVIDENCE note
instead of an invented role. Bugs found and fixed by tests: clause-boundary
leak ("must have X, would love Y" made Y mandatory), multi-word PlayStyle
consumption ("tiki" tactical word ate "Tiki Taka"), first-occurrence-only
classification. The parser never invents ratings, cards, prices, PlayStyles
or Roles — it maps the user's football vocabulary onto the real DB
vocabulary (36 PlayStyles, 16 tactical profiles, 11 formations, 17 archetypes).

## 5. Hard constraints vs soft preferences (§19)

Hard: game version, position/slot eligibility, min/max OVR, explicit numeric
attribute minimums, required PlayStyles, required league/club/nation, budget
(only when a verified price exists). Violations exclude **with a machine-
readable reason**; unverifiable constraints produce "cannot verify"
exclusions or `unknown` entries — never silent passes, never silent drops.
Soft: attribute bands (soft targets), preference weights, tactical/archetype/
playstyle context, OVR emphasis bias, complement hint. Soft inputs shape the
score; they never eliminate. Live example: required "Intercept" excluded
9,854 of 10,275 CM-family candidates, each with the reason
`mandatory PlayStyle 'Intercept' not held`.

## 6. Retrieval & performance engineering (§56/§57)

Position prefiltering runs before scoring (CM family = 10,275 of 16,228;
adjacency ≥ 0.4). The candidate cache is keyed by version + scope and
invalidated by a DB watermark (`count@max(updated_at)`) — never by market
values (none exist). Per-request work (effective weights, slot/dimension
context) is hoisted out of the per-candidate loop. Scaling is linear:
54 ms @1K → 1.13 s @16K warm (legacy path); ~54–69 µs per candidate.
Precomputed per-candidate features (archetype vectors, position-weighted
attribute aggregates) are designed in this document's roadmap but **not yet
wired** — recorded as a known limitation rather than faked.

## 7. Formation & positional intelligence (§6)

`formations.py`: 11 formations (4-2-2-2 added) with slot objects
(slot/position/side/duty/emphasis). CAM ≠ CM is structural: the 4-2-3-1 CAM
slot (ATTACK duty) and 4-3-3 CDM slot (DEFEND duty) produce different
dimension vectors and different attribute importance. Slot-adjusted weights
multiply position weights by the slot emphasis when a slot is requested.
Formation slots are exposed via `/api/meta/reference` for UI slot pickers.

## 8. Tactical intelligence incl. combinations (§7)

16 tactical profiles (5 new: HIGH_PRESS, MID_BLOCK, LOW_BLOCK,
FAST_BUILD_UP, SLOW_BUILD_UP) over 6 tactical dimensions. When a secondary
profile is set, dimension vectors merge (primary 0.6 / secondary 0.4) and
attribute demand is **derived** from the merged vector
(`|v−0.5|×2 × affinity`, normalized) — never hardcoded per combination.
Tested distinction: HIGH_PRESS+FAST_BUILD_UP demands more acceleration;
HIGH_PRESS+POSSESSION keeps more pure pressing demand (interceptions,
defensive awareness); the weight tables are provably different. Live what-if:
swapping FAST_BUILD_UP→POSSESSION changed every top-10 score and moved the
counterfactual pick to Vitinha. GK under combination tactics stays
INSUFFICIENT (consistent with legacy single-profile GK behavior).

## 9. Attribute intelligence (§8–§11)

Configurable importance (position weights × slot emphasis × tactical demand —
nothing hardcoded in the scoring function). Qualitative bands map to soft
targets in `engine_config.QUALITY_BANDS` (elite/excellent/very_good/good/
average/weak) with a ramp, saturating at the target ("enough", not "more").
Diminishing returns: per-attribute saturation knees (default 85, pace family
90, excess ×0.35) — configurable and tested (monotonic, slope-decreasing).
Interactions (e.g. pace+dribbling+agility → explosive_ball_carrier, geo/min
aggregation) activate **only when every input is KNOWN**; skipped
interactions are reported, never zero-filled. Blend cap
`INTERACTION_TOTAL_CAP` keeps interactions from dominating. A coverage gate
(0.5 of demanded attribute weight) turns thin records into
INSUFFICIENT_EVIDENCE instead of confident scores.

## 10. PlayStyle intelligence (§11/§12)

Contextual value, not fixed bonuses: `context_value()` returns 1.0 when the
profile explicitly values the PlayStyle, 0.75 for position affinity, 0.35
neutral. PS+ multiplies demand-weighted value (×1.5 context) but base-only
holders keep 0.6× — a mismatched PS+ **loses to a perfectly contextual base
PlayStyle** (tested). The affinity table is unit-tested to contain only the
real 36-PlayStyle vocabulary. Unpublished PlayStyle data →
INSUFFICIENT_EVIDENCE (never "no playstyles"). Redundant +/base pairs are
counted once.

## 11. Role intelligence (§13)

Roles are first-class in the request model and component set
(`role_fit`), with eligibility/familiarity handled by `RoleFitService`
against `role_definition` data. FC26 has **no verified role data ingested** —
so role_fit correctly reports UNKNOWN/INSUFFICIENT_EVIDENCE and its weight is
redistributed; it is never zero and never faked. Text like "false nine" maps
to the computed FALSE_9 **archetype** (engine-derived), and the parser emits
an explicit note that official Role data is unavailable.

## 12. Dynamic archetypes & gameplay profile (§12/§14/§32)

17 archetypes (BOX_TO_BOX, DEEP_PLAYMAKER, POACHER, BALL_PLAYING_DEFENDER,
SWEEPER_KEEPER, …) are **computed per candidate** from attributes +
PlayStyles — the module source contains zero player names (test-enforced).
Position eligibility is enforced (GK archetypes only for GKs and vice versa).
`dominant_archetype` is deterministic (tie-break by name). The ENGINE-DERIVED
gameplay profile labels (EXPLOSIVE, TECHNICAL, PHYSICAL, CREATIVE, DEFENSIVE,
PRESS_RESISTANT, CLINICAL, DIRECT; GK variants) require ALL inputs KNOWN,
are capped at the 4 strongest with the remainder disclosed
(`additional_qualified`), and always carry the disclaimer "not official EA
attributes". Versatility scores secondary-position + slot coverage.
`archetype_fit` enters the weights at 0.10 **only when the user requests an
archetype** — otherwise baseline weights are untouched.

## 13. Squad, chemistry & replacement intelligence (§22/§28)

`squad_structural_fit` (ADVISORY): weighted link density (0.5, verified
club/league/nation facts only), archetype diversity (0.3) and complementarity
(0.2, stylistic bias ATTACKING/DEFENSIVE/BALANCED computed from attributes),
honestly renormalized when parts are unknown; every result carries the note
"NOT a chemistry score (chemistry rules remain unverified/UNKNOWN)". Real EA
chemistry stays withheld per the no-fabrication contract. Replacement
intelligence: per-candidate UPGRADE/SIDEGRADE/DOWNGRADE (±0.02 verdict
margin) from **component-level** deltas with improved/sacrificed lists,
critical-sacrifice downgrade rule (>0.15 loss demotes UPGRADE→SIDEGRADE),
attribute movers (≥5-point diffs) and a standing OVR-honesty note — verdicts
are never OVR-based.

## 14. Budget & value intelligence (§21)

Budget is a hard constraint **only against verified prices**. No permitted
price feed exists for FC26 → every budget request reports
`BUDGET_UNVERIFIED: no candidate has a verified price; budget constraint
could not be enforced (prices are UNKNOWN, never assumed affordable)`.
Candidates are never excluded for UNKNOWN price; `best_value` Pareto
dimension reports UNAVAILABLE with a reason. Counterfactual "if budget
removed" answers honestly: "no effect — the budget was never enforceable".

## 15. Multi-objective Pareto & diversity (§29/§53)

Pareto fronts: best_overall, best_attribute_fit, best_tactical_alignment,
best_playstyle_fit, best_chemistry_fit, best_value, best_archetype_fit, plus
v2.1's `best_alternative_archetype` (highest scorer with a different derived
archetype than the winner — diversity of alternatives). Unavailable
dimensions are listed **with reasons** (missing verified data, never
invented). Ranking remains single-objective by weighted score; Pareto is
advisory surface, as specified.

## 16. Score bands & interpretability (§23/§51)

Bands: 90–100 EXCEPTIONAL_FIT · 80–89.9 STRONG_FIT · 70–79.9 SOLID_FIT ·
60–69.9 SITUATIONAL_FIT · <60 WEAK_FIT — validated against real outputs
(live: full-intelligence winner 0.841 → STRONG_FIT). Every band carries
"engine suitability score — not a probability". The §51 honesty gate: when a
score rests on < 0.5 of component weight (`MIN_BAND_EVIDENCE`), the band
becomes INSUFFICIENT_EVIDENCE with the coverage disclosed — a 1.000 score on
30% evidence can never masquerade as EXCEPTIONAL_FIT. Considered and
rejected (documented in the changelog): down-ranking thin-evidence
candidates — it contradicted the pinned legacy contract that UNKNOWN data
never penalizes; scores stay exact, interpretation carries the caveat.

## 17. Confidence 2.0 (§24)

Legacy confidence (0.7×component coverage + 0.3×entity data) is preserved
untouched. `confidence_v2` (additive) renormalizes four factors over KNOWN
inputs only: legacy (0.55), freshness (0.20; linear decay 180d→730d, floor
0.4), source authority (0.15; tier factor × 0.15-per-unresolved-conflict
penalty, floor 0.5), identity (0.10; RESOLVED 1.0 / REVIEW 0.6 / UNRESOLVED
0.4). Levels HIGH/MEDIUM/LOW/VERY_LOW with human-readable `reasons` and a
`composition` breakdown. Live example: legacy 0.72 → v2 0.756 MEDIUM
(fresh same-day data, tier-3 source, resolved identity, 0 conflicts).

## 18. Evidence graph, freshness & conflicts (§25/§26/§27)

Chain: recommendation → components (evidence strings naming exact attribute
values) → source observation → dataset. Responses carry `provenance` (source
registry rows: license "CC0 1.0 Public Domain", authority tier 3, usage
status), `data_freshness` (last source observation; market prices
UNAVAILABLE; chemistry UNVERIFIED), and per-candidate `constraints`
{satisfied, failed, unknown}. Conflicts resolve by the authority hierarchy
(official > licensed carrier > reference-only community); unresolved
`attribute_conflict_log` rows penalize confidence v2 and are counted live
(currently 0 for FC26). META_SIGNAL vs CANONICAL separation is preserved —
no community signal can overwrite official attributes.

## 19. No-hallucination contract (§18) — verification

Vocabulary: KNOWN / UNKNOWN / INSUFFICIENT_EVIDENCE / CONFLICTED used
consistently across every layer. Verified by tests: UNKNOWN attribute vs a
required minimum → `unknown`, never `failed`; unpublished PlayStyles →
INSUFFICIENT, never KNOWN(0); missing price → never affordable; missing role
data → never incompatible; empty FC27 → 404 wall stating nothing was
fabricated. There is no data-quality point subtraction anywhere — missing
data reduces **confidence and band claims**, never scores. No arbitrary
randomness exists in the engine (determinism + pool-order-invariance tests).

## 20. Version safety & FC27 readiness (§20/§61)

Every request is version-guarded; candidates and requirements must agree;
FC26 config is never used for FC27. FC27 today: zero data → the service
raises the honest wall ("NO ingested production data… nothing was
fabricated"), tested live (HTTP 404) and in unit tests. Cross-version
comparison remains an explicit mode only (comparison_service), never implied
equivalence. Card-level intelligence (§30): card attributes/PS+/prices would
never be substituted by base-player data — currently untestable against
production card rows (only 60 SYNTHETIC_TEST fixtures exist, firewalled), so
`entity_scope=ut_card` refuses with an explicit explanation instead of
downgrading silently.

## 21. Personalization, feedback & the ML roadmap (§31/§33)

Personalization = GLOBAL_ENGINE (config-driven, versioned) +
USER_PREFERENCE_MODEL (drafts from parsed intent, user-reviewed before
running — the UI applies drafts to the form, never auto-submits). Explicit
hard constraints always win over learned/derived preferences. Feedback
capture stores action + full request context; `feedback_analytics.summarize()`
measures labels (live: 68 rows, 21 labeled decisions, ~60% context
coverage). ML is gated: ≥500 labeled decisions at ≥80% context coverage
before even an offline experiment (phase 4 of 6: capture → measure → label
review → offline experiment → shadow → guarded live). No ML code exists; the
deterministic engine is the permanent fallback.

## 22. Explanations, counterfactuals, sensitivity, what-if (§34/§35/§36)

Positive: `why_this` (component evidence), strengths, summary. **Negative**:
`why_not_alternatives` — for each runner-up, the exact differentiator
(component deltas with numbers), not generic text. Sensitivity: weighted
component deltas between #1 and #2 above the 0.005 noise threshold, else the
honest "no single component decided this" summary. Counterfactuals (4
families over the top-20): alternative tactical profiles, budget removal,
attribute-minimum removal, strict-tactics toggle — each reports if/then and
whether the pick changes (live: "tactical profile changed to POSSESSION →
the top fit becomes Vitinha [changes the pick]"). What-if mode = re-running
the request with altered fields; the §74 test asserts the decision surface
reacts.

## 23. Robustness, evaluation, results & limitations (§49–§62)

**Evaluation:** 12-scenario qualitative suite (`engine_evaluation.py`) +
8 golden real-data scenarios + experiment framework (persisted to DB;
smoke experiment showed attribute_fit 0.35 flips exactly 1/12 winners —
variant not adopted, BASELINE V1 weights vindicated). **Robustness:**
determinism (same input twice, shuffled pools), ±1 OVR/attribute stability,
malformed input (empty names, None OVR, unknown positions, garbage
requirements rejected with per-field problems), synthetic firewall aborts,
conflicting/impossible constraint sets return honest empty results.
**Results:** backend 262/262, frontend 38/38, tsc clean, goldens ALL
IDENTICAL, live smoke 7/7 (reference, parse-intent, legacy recommend,
full-intelligence recommend, FC27 wall, feedback analytics, rebuilt SPA).
Performance: legacy warm 54 ms–1.1 s by pool size; full-intelligence 10K
pool ~1.3 s warm. **Limitations (honest):** sub-second target missed for
full-intelligence on ≥10K pools; feature caching not yet wired; role_fit /
chemistry / prices / production cards remain UNKNOWN for FC26; NDCG/MRR
deferred until real labels exist; expert priors (band thresholds,
interaction weights, label knee 82) await feedback-based validation through
the experiment framework — never cherry-picked tuning.

---

*Deliverables: docs/ENGINE_BASELINE.md · docs/INTELLIGENCE_ENGINE_ARCHITECTURE.md ·
docs/ENGINE_CHANGELOG.md · docs/ENGINE_EVALUATION.md · docs/ENGINE_DATA_REQUIREMENTS.md ·
benchmarks/ENGINE_BENCHMARKS.md · benchmarks/engine_v21_perf.json ·
backend/tests/test_engine_{intelligence,scenarios,robustness,ovr_trap,unknown_data}.py ·
scripts/{run_engine_experiment,benchmark_engine_v21}.py · AUTONOMOUS_STATUS.json (updated) ·
this report.*
