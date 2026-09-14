# CARD SCORING — Phase 3 (§10/§12/§33/§34/§35)

One engine (`recommendation_engine_v2.py`). Cards are scored by the **same
contextual framework** as players — there is no "card bonus" and no second
scoring path. Card suitability emerges from card-level evidence entering the
existing components.

## 1. What changes for a card candidate

| component | card behaviour |
|---|---|
| `overall_quality` | the CARD's OVR (never the base player's) |
| `position_fit` | card position + link-fact secondary positions (labelled `secondary_positions_source: game_player`) |
| `attribute_fit` | card-published attributes only; unpublished ⇒ excluded from coverage (UNKNOWN, never base-player values, never 0). Coverage gate unchanged (50%) |
| `tactical_fit` | unchanged math over card attributes — a card with fewer published attributes honestly loses coverage, and UNKNOWN never lowers the score (legacy contract) |
| `playstyle_fit` | card PlayStyles only when `playstyle_data_published`; base/plus tiers stay distinct; contextual PS+ evaluation is the v2.1 layer (a mismatched PS+ never auto-beats a contextual base PS) |
| `role_fit` | card-published role familiarity via `CARD_ROLE_FAMILIARITY_SCORES` (engine_config) for the requested role only; unpublished ⇒ INSUFFICIENT_EVIDENCE |
| `team_fit` | unchanged: verified link facts only; chemistry itself is UNKNOWN (§15, see `docs/CARD_CHEMISTRY.md`) |

Every component still exposes value/status/weight/effective_weight/
evidence/unknown_factors (§33). Weights: BASELINE V1 unchanged
(0.15/0.30/0.15/0.15/0.15/0.10, UNKNOWN redistributed); all new tunables
live in `engine_config.py` (`VALUE_*`, `PRICE_*`, `CARD_ROLE_FAMILIARITY_SCORES`,
`BUDGET_COUNTERFACTUAL_STEP`, `VALUE_RANK_TOP_N`).

## 2. §5 separation contract (hard, tested)

`Candidate.from_ut_card(card, gp)`:
attributes = `card.attribute_overrides` only; PlayStyles = card's own and only
when published; OVR = card's; price = card's. The base GamePlayer contributes
ONLY nation/club/league/secondary positions, each labelled in `extra`.
Tests: `test_card_model.py::TestCardAttributeSeparation`,
`test_card_scenarios.py::TestCardScenarios`.

## 3. Value (§14) — separate from suitability

`value = (contextual_utility − pool_reference_floor) / (verified_price / VALUE_PRICE_UNIT)`

* utility = the engine's weighted score for THIS request (value is contextual);
* reference floor = lowest utility among verified-price candidates in the
  ranked set;
* no verified price ⇒ `VALUE_UNAVAILABLE` (never 0, never ranked as free);
* never OVR/price — OVR is not an input to `card_value_service` at all.
Surfaced for `entity_scope=ut_card` as `payload.card_value` +
`pareto.best_value` / `pareto.best_within_budget` (§17), each with an
explicit `unavailable` explanation when the dimension cannot be computed.

## 4. Explanations & counterfactuals (§34/§35)

`explanation_service` names actual differentiators (component deltas with
evidence), never "better stats". For card scope the payload adds
`card_counterfactuals`: budget +100K (`BUDGET_COUNTERFACTUAL_STEP`), top card
without its PlayStyle+, alternative position, removing each of up to 3 squad
members, and — honestly — "verified chemistry rules existed" ⇒ *cannot be
computed* while no verified rules are ingested.

## 5. Comparisons (§12)

`POST /api/compare` accepts card ids alongside player ids. Card columns add a
`card` block (type, rarity_raw, release, canonical id, identity status,
attribute_source, price provenance, roles). Mixed player+card comparisons
carry an explicit `scope_note` — scopes are never mixed silently.

## 6. Determinism (§39)

Randomized pool order ⇒ identical ranking (tested at 1,200 cards);
tie-breaks unchanged (floor-breakers last, −score, −OVR, name, entity_id);
legacy goldens S1–S8 bit-identical after every Phase 3 change
(`scripts/verify_goldens.py`).
