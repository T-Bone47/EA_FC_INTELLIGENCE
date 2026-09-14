# CARD INTELLIGENCE — Phase 3 architecture (v3-phase, engine 2.2.0)

**Question answered:** *Which PLAYER/CARD is best for THIS user's exact
context?* — PLAYER QUALITY ≠ PLAYER SUITABILITY, and CARD SUITABILITY ≠
PLAYER SUITABILITY.

The system was **evolved in place** (§0): one scoring engine
(`recommendation_engine_v2.py`), no Engine V3, no parallel engine. Card
intelligence is the same contextual framework applied to card-level entities.

## 1. Entity hierarchy (never collapsed, §3)

```
RealPlayer → GamePlayer → UTCard → CardVersion
                              ├─ card attributes (ut_card_attribute_override / card_version.attributes)
                              ├─ card PlayStyles (ut_card_playstyle, tier base|plus)
                              ├─ card Roles (ut_card_role)
                              ├─ evolutions (card_evolution)
                              ├─ availability (card_availability)
                              └─ market observations (card_price → source_observation)
```

A card is NOT its base player. The base GamePlayer supplies **identity link
facts only** (nation/club/league/secondary positions), each labelled in the
candidate's `extra` trail (`secondary_positions_source: game_player`).

## 2. Attribute separation (§5 — hard rule, tested)

`Candidate.from_ut_card` uses **card-published attributes only**. An attribute
the card does not publish is `UNKNOWN` (None) — never back-filled from the
base player. A PAC95 card over a PAC84 base scores with 95; the base's FIN85
that the card doesn't publish stays UNKNOWN and is excluded from coverage —
never counted, never zeroed. Proven by
`backend/tests/test_card_model.py::TestCardAttributeSeparation` and
`test_card_scenarios.py::test_card_attributes_differ_from_base_player_engine_uses_card`.

PlayStyles follow the same rule: inherited only when the card's PlayStyle data
is *published* (`playstyle_data_published`); an unpublished list is UNKNOWN,
never the base player's list (§6). PlayStyle vs PlayStyle+ remain distinct
tiers; contextual evaluation lives in the existing v2.1 playstyle-context
layer — a mismatched PS+ never auto-beats a contextual base PS.

## 3. Entity scopes (§11)

`entity_scope = auto | game_player | ut_card` — never mixed silently:

* `auto`/`game_player` → player pool (`CandidateRepository.load_candidates`)
* `ut_card` → card pool (`CandidateRepository.load_cards`), separate cache
  namespace and **separate watermark** (§28) covering cards + versions +
  prices + verified chemistry rules, so a price update can never be served
  stale (§31).
* When a scope has no canonical data the API says so (404 NO_DATA) instead of
  downgrading to the other scope.

## 4. Value, budget, chemistry (§13–§16)

* **Price** exists only as persisted, provenance-backed observations
  (`card_price` → `source_observation`). Missing = UNKNOWN, never 0.
* **VALUE = marginal contextual utility per verified cost**
  (`card_value_service.value_assessment`, tunables in `engine_config.py`:
  `VALUE_PRICE_UNIT`, `VALUE_MIN_PRICE_COINS`). Never OVR/price. Without a
  verified price: `VALUE_UNAVAILABLE` + `BUDGET_UNVERIFIED` — the engine and
  UI never claim "affordable".
* **Chemistry**: architecture only. `chemistry_rule` rows must be
  `verified=TRUE`; none exist for FC26, so every chemistry answer is
  `CHEMISTRY_UNKNOWN` and only **structural fit** (factual club/league/nation
  links) is reported — explicitly labelled `is_chemistry: false`.
* **Squad impact** (§16) combines the engine's contextual utility delta with
  structural links; the unknown chemistry effect is never counted for or
  against.

## 5. Roles (§9)

Roles ≠ archetypes; both are kept. Card-published role familiarity
(`ut_card_role`) maps through the configurable reference table
`CARD_ROLE_FAMILIARITY_SCORES` — only for the **requested** role, never a
generic "has roles" bonus. No role data ⇒ `INSUFFICIENT_EVIDENCE`.
Archetypes remain engine-derived (`archetypes.py`).

## 6. Evolutions (§8)

`card_evolution` stores base→evolution→result links with requirements,
changes, eligibility and provenance. No verified FC26 evolution data has been
ingested; the engine invents no evolution rules — status stays NO_DATA
(visible at `/api/card-data-status`).

## 7. Meta signals (§18/§19)

`meta_signal` is firewalled **by construction**: `backend/ingestion/meta_signals.py`
has no code path into canonical tables; community signals store as
RESEARCH_ONLY, always labelled `kind: META_SIGNAL, is_canonical: false`;
strength/sample_size stay NULL when unpublished (never 0). No meta source is
currently adopted.

## 8. Pipeline & activation (§26/§27)

RAW → STAGING → VALIDATED → PRODUCTION via the existing ingestion pipeline,
extended with: dataset forensics (`ingestion/forensics.py`), run tracking +
quarantine (`ingestion/run_tracker.py`, tables `ingestion_run`,
`ingestion_quarantine`) and the one-command activator
`scripts/activate_card_dataset.py` (legal gate → forensics → normalize →
validate → quarantine → atomic promote → watermark → cache invalidate →
integrity → golden regression → report). Activation of a dataset whose source
is not OFFICIAL/AUTHORIZED/LICENSED is refused (§54).

## 9. API & UI (§41–§44)

Additive endpoints: `GET /api/cards`, `/api/cards/{id}/versions|prices|value`,
`GET /api/card-data-status`; card detail already existed at
`/api/cards/{card_id}`; comparison of cards runs through the existing
`POST /api/compare` (no duplicate endpoint). Frontend: `/cards` discovery +
premium `/cards/:id` page + `DataQualityPanel`; UNKNOWN renders as UNKNOWN.

## 10. Performance (§29/§30)

Precomputed/memoized non-user-specific features (archetype vectors, gameplay
profiles, versatility, interaction features, data-confidence, normalized
weight tables) on the per-candidate `feature_cache` + `ScoringConfig` caches.
Benchmarks: `benchmarks/ENGINE_BENCHMARKS.md` (before/after Phase 3).
