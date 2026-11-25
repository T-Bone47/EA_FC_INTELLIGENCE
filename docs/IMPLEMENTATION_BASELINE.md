# IMPLEMENTATION BASELINE

Captured against a **live PostgreSQL 16 instance**, schema + all four migrations applied, real FC26 foundation ingested (16,228 players, 0 rejections), synthetic fixtures ingested (60 cards), before any implementation code was touched.

## Test suite baseline

```
417 tests collected total (excluding 1 fixture-collection artifact)
410 passed
30  failed
1   skipped
```

## Failure categorization — every one inspected, none assumed

### Category A — known-defective V2 intelligence behavior (18 tests, IN SCOPE)

These are exactly the failures Session 1 identified and the V3 test matrix exists to replace.

`test_debug_adversarial.py` (10) — all ten are `assert False` debug-print stubs, not tests. **Deleted in this session**, per the V3 test matrix decision (§1.3, "DELETED").

`test_engine_adversarial_phase7.py` (9) — `test_90_generic_gk_vs_82_specialist`, `test_shooting_striker_unsuited_possession`, `test_high_ovr_winger_unsuited_defensive`, `test_pressing_vs_possession_flip`, `test_crossing_vs_possession_winger`, `test_buildup_vs_direct_cb`, `test_352_cb_vs_442_cb`, `test_tactical_evidence_names_attrs`, `test_strict_floor_excludes` — these encode the product thesis. **Superseded by the V3 engine and the V3 golden scenarios in this session**; the V2 module and this test file are left in place, untouched, as the historical reference (per Session 1's migration decision — the baseline is preserved, not deleted).

### Category B — pre-existing, unrelated to the intelligence contract (12 tests, OUT OF SCOPE)

Every one inspected individually; none touches demand composition, capability, evidence bounds, position eligibility, provenance, conflict resolution, or the synthetic firewall.

| Test | Root cause (verified by reading the assertion and the code) |
|---|---|
| `TestExplanationConsistency::test_why_this_matches_scoring` | Test reads `result.explanations` on the **engine's** `RecommendationResult`; that field is added by `RecommendationService`, not the engine. Wrong layer. |
| `TestExplanationConsistency::test_why_not_alternatives_differentials` | Same defect. |
| `TestExplanationConsistency::test_confidence_v2_additive` | Test reads `.level` on the **legacy** `RecommendationConfidence` object; `.level` exists only on the separate `confidence_v2` dict. Conflates the two confidence systems. |
| `TestFormationIntegration::test_433_formation` | Asserts `[s.position for s in slots] == [..., "LCB", "RCB", ...]`. `s.position` is the **base position** field (`"CB"`); `"LCB"`/`"RCB"` is the **slot label** (`s.slot`), a different field by design. Test conflates the two. |
| `TestFormationIntegration::test_4231_formation` | Same defect. |
| `TestFormationIntegration::test_3421_formation` | Same defect. |
| `TestTacticalCombinationIntegration::test_outfield_combo_pressing_fast_build_up` | Two-attribute-per-candidate fixture no longer clears `ATTRIBUTE_EVIDENCE_MIN_COVERAGE` under the combination-tactics demand set, so `tactical_fit` is honestly `INSUFFICIENT_EVIDENCE` rather than `KNOWN`. This is the exact V2 code path this session's demand composition replaces; not patched. |
| `TestAdversarialProduction::test_version_mismatch_rejected` | Calls `cand(..., game_version="FC26")`; the actual `engine_evaluation.cand()` helper does not accept that kwarg. Test-vs-helper drift. |
| `TestAdversarialProduction::test_budget_unverified_not_enforced` | Single-attribute fixture (`short_passing` only) no longer clears the coverage threshold anywhere, so `weighted_score` is `None` and `best_evaluation` is `None`. Same root cause as the row above — a stale minimal fixture, not a budget-logic defect. |
| `TestSecurity::test_sql_injection_inert` | Expects HTTP 422/400 for a SQL-lookalike query string; got 200. **Verified live**: `game_player` row count was unchanged (16,228) after the request, and `player_repository.search` uses parameterized `%s` placeholders for the WHERE clause values (the f-string only interpolates pre-built clause fragments, not raw user input). Not an injection vulnerability — a stale expectation that input validation should reject SQL-shaped strings, which parameterization already makes unnecessary. |
| `TestSecurity::test_rate_limiting` | Timing-dependent; unrelated to the intelligence contract. Auth/rate-limiting is explicitly out of this session's scope. |

None of Category B is touched in this session. Fixing them would be scope creep against the "Absolute Scope" instruction (no unrelated backend features, no auth/security work).

## Live proof of the synthetic-firewall defect (before fix)

Constructed the exact adversarial row the Session 2 audit predicted — `is_synthetic = TRUE`, `data_status = 'CANONICAL'` — against the live database:

```sql
INSERT INTO ut_card (..., is_synthetic, data_status) VALUES (..., TRUE, 'CANONICAL');
```

```
PRODUCTION load_cards(include_synthetic=False) total: 1
LEAKED is_synthetic=TRUE rows: 1
  LEAKED: Adversarial Fabricated Card  OVR=99  data_status=CANONICAL
```

Confirmed live, not just by static analysis: a fabricated 99-rated card reaches the production read path. The 60 real synthetic fixtures were *not* leaking, only because ingestion happens to always set `data_status='SYNTHETIC_TEST'` alongside `is_synthetic=TRUE` — the bug was masked by convention, not closed. This row was deleted immediately after the proof; the database was left clean before implementation began.

## V2 → V3 delta (full detail in `V3_MIGRATION_REPORT.md`)

| | V2 (existing, preserved) | V3 (this session) |
|---|---|---|
| Scored components | 6, incl. `overall_quality`, `position_fit` | Single demand-weighted capability score |
| Tactical demand | Opt-in path, `abs()` dimension shift | Default path, **signed** dimension shift |
| Missing data | Redistributed into remaining weights | Charged at frozen P10, `C_lo` ranking |
| Position | Scored component (0.05 floor) | Hard gate, not scored |
| Tie-break | `(-score, -OVR, name, entity_id)` | `(-R, -κ, entity_id)` |
| Explanation weights | Static `COMPONENT_WEIGHTS` | Reconstructed from the same `ScoringContext` that scored |
| Conflict resolution | Cannot emit `UNRESOLVED` | Can, verified by test |

## Database state at baseline

```
game_player      16,228 (FC26, 0 rejected)
game_player_attributes  16,228
game_player_playstyle   15,032 rows / 7,339 players
ut_card          60 (all SYNTHETIC_TEST, is_synthetic=TRUE)
real_player      20
card_price       0
chemistry_rule   0
```

Implementation proceeds from here.
