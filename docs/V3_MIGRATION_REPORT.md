# V3 MIGRATION REPORT

## What changed, and the measured defect each change closes

| # | v2 behaviour | Measured defect | v3 replacement | Evidence this session |
|---|---|---|---|---|
| 1 | `attribute_fit` uses position profile; `tactical_fit` separate, ~0.15-0.30 combined weight | 10/10 top-10 overlap, PRESSING vs LOW_BLOCK, CB/ST/CM | Single composed demand vector, tactical path default | CB 3/10, ST 2/10 (this session) |
| 2 | Tactical dimension shift `abs(value-0.5)` | Low block and high press pull the *same* attributes, same direction | Signed two-pole affinity (`demand_composition.py`) — **new this session**, not merely specified | CB pair reverses correctly both directions, proven by test and live API call |
| 3 | Missing weight redistributed to remaining components | 1-attribute candidate outranked a fully-documented one (0.89 vs 0.87) | Evidence interval, `C_lo` ranking, P10 charge for missing weight | Thin candidate now `NOT_EVALUABLE`; proven with the exact original numbers |
| 4 | `overall_quality`, `position_fit` scored components | OVR/position dominate under thin evidence | Both deleted; capability over demand vector only | `INV-15`: R invariant to OVR when attributes held fixed |
| 5 | Position: soft component, floor 0.05 | 91 ST scored 0.535 at CB, `excluded_hard=[]` | Engine-level gate (G3/G4), never scored | Striker now excluded at the gate, not ranked |
| 6 | Sort tie-break `(-score, -OVR, name, entity_id)` | OVR and alphabetical order could decide ties | `(-R, -kappa, entity_id)` | `INV-15` tie test: renaming/re-rating tied candidates does not change order |
| 7 | `explanation_service` reads static `COMPONENT_WEIGHTS` | Explained weight (0.15) != scoring weight (0.50) under redistribution | Reads only `ScoringContext`; `reconstruct_score` enforced | `INV-8`, tolerance 1e-9, exact match on every ranked candidate tested |
| 8 | `conflict_resolver` always emits `SOURCE_A_WINS` | Equal-authority ties settled alphabetically, reported as a win | `UNRESOLVED` path added | Proven against the audit's own worked example (91 vs 92, equal tier) |
| 9 | Candidate repository synthetic filter | SQL operator precedence bug — `is_synthetic` never checked in production | Corrected predicate + DB-level CHECK constraint | Adversarial row leaked (1) before, blocked (0) after, at both layers |
| 10 | `compute_canonical_id` falls back to literal `"BASE"` | Two distinct cards with unknown type+rarity would silently merge | Returns `None`; caller marks `REVIEW_REQUIRED` | Constructed the exact collision scenario; confirmed no longer merges |
| 11 | `fit_components.team_fit`: `slot.league == slot.league` | Always true; league link counts meaningless | Compares against the candidate | Constructed fixture with a genuinely non-matching league; count now correctly 0 |

## Preserved, not migrated

`benchmarks/engine_baseline_v2_2026-09-14.json` — untouched. `recommendation_engine_v2.py` and `test_engine_adversarial_phase7.py` — untouched, left as the historical reference the Session 1 decision required. `POSITION_ATTRIBUTE_WEIGHTS`, `TACTICAL_ATTRIBUTE_WEIGHTS`, `PROFILE_DIMENSIONS`, saturation knees, interaction feature definitions, `playstyle_context` tiering, `card_value_service`, squad intelligence's link-counting shape (minus the league bug) — all reused by v3 without modification, because measurement found them sound.

## Removed

`overall_quality` and `position_fit` scored components. OVR and candidate-name tie-breaking. Weight redistribution under missing evidence. The separate `tactical_floor` exclusion mechanism (its job is now done inside demand composition — a tactically unsuitable candidate already scores low because the tactical signal is *in* the single demand vector, not a second, opaque gate on top of it). `test_debug_adversarial.py` (ten `assert False` stubs).

## Compatibility decision

**No dual-engine mode in production.** `v2` and `v3` are both importable (v2 for historical comparison and its own preserved test file; v3 as the only path the new API endpoint reaches), but there is one production recommendation endpoint per engine version, and the v3 endpoint refuses `ut_card` scope outright rather than silently falling back to v2 or degrading. A caller cannot get v2's known-defective behaviour by accident through the new surface.

The nine `test_engine_adversarial_phase7.py` failures are **expected and permanent** under this decision — they assert v2 behaviour that v3 exists to reject. Per the mandate ("do not make the old tests pass merely for compatibility if they encode behaviour the new intelligence contract explicitly rejects"), they are left red, not deleted, not weakened: they are the historical record of exactly what v3 fixed, runnable on demand against the frozen v2 module.

## One test corrected mid-session, and why that's not scope creep

Fixing `conflict_resolver.py`'s `UNRESOLVED` path caused `test_card_scenarios.py::test_equal_authority_conflict_recorded_deterministically` to fail — it asserted the old alphabetical-pick behaviour by name. This is exactly the situation the mandate anticipated: the test encoded the rejected behaviour, so it was corrected to assert the new, specified behaviour (equal authority + material disagreement -> `UNRESOLVED`, value `UNKNOWN`), with the change documented inline in the test itself, not silently patched.

## What v3 does not attempt

Card-scope anything (no permitted data source — `FC26_DATA_BUILD_DECISION.md`). Role scoring (no data). Chemistry (no verified rules). Price/value/budget as a ranking or hard-gate input (no price data at player scope). ML ranking (no labelled data, per Session 1/2's own bar). None of these is stubbed to look more complete than it is — each returns an explicit "unavailable" state where the architecture calls for one.
