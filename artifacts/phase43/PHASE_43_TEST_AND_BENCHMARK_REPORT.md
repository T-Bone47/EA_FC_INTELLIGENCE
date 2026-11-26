# Phase 43 Automated Testing & Benchmark Evaluation Report

## 1. Backend Pytest Suite (Observed Post-Final-Edit Run `488.96s`)
Command:
```powershell
$env:DATABASE_URL='postgresql://eafc:eafc_dev_only@127.0.0.1:5432/eafc_intelligence'
C:\Python315\python.exe -m pytest backend/tests -q --tb=short
```
Exact Summary:
- **`937 passed`**, **`90 subtests passed`**, **`11 skipped`**, **`13 failed`**, **`0 errors`**
- Resolved `2` baseline fixture errors (`backend/tests/test_phase30_card_lab.py` now passes `6/6`).
- Zero Phase 40/41/41.5/42/43 regressions (`test_phase42_copilot_cv_training.py`, `test_phase43_tactical_lab.py`, `test_security.py`, `test_phase30_card_lab.py`, `test_zero_budget_research.py`, `test_golden_fixtures_v3_2.py` passed `45 passed in 77.96s`).
- Preserved `13` pre-existing failures honestly documented (`9` in `test_engine_adversarial_phase7.py` legacy V2 expectations + `4` in `test_engine_v3_real_data.py` empirical V3 threshold bands) so frozen V3.2.1 weights remain strictly unaltered.

## 2. Frontend Build, TypeScript & Vitest Suite
Command: `npx tsc --noEmit && npm run build && npm test -- --run` (`frontend/`)
- `tsc --noEmit`: `0` errors
- `vite build`: `95` modules transformed, built cleanly in `3.56s` (`TacticalLab-*.js` cleanly bundled)
- `vitest run --run`: **`Test Files 21 passed | 1 skipped (22)`**, **`Tests 111 passed | 3 skipped (114)`** (`e2e.live.test.tsx` skipped for live server separation)

## 3. Comprehensive Benchmark (`verification/fc_tactical_experiment_bench_v1.py`)
`FC_TACTICAL_EXPERIMENT_BENCH_V1`: **`7 / 7 categories passed` (`overall_passed: true`)**:
- **Category A (`A_TACTICAL_FINGERPRINT_AND_ABSTENTION`):** `full_compactness=0.74`, `partial_abstained=true` (`ABSTAINED_VISIBLE_PLAYERS_BELOW_14`), `metric_details` populated.
- **Category B (`B_STATISTICAL_INFERENCE`):** `pos_verdict=SUPPORTED_IMPROVEMENT` (`pos_prob_meaningful=0.999`), `null_verdict=INCONCLUSIVE` (`relative_improvement=None` zero-guarded), `confound_verdict=INCONCLUSIVE` under patch drift.
- **Category C (`C_FORMATION_RECOMMENDATION_12_SHAPES`):** `formation_count=12`, `compare_formations` returns head-to-head winner and structural diffs cleanly.
- **Category D (`D_REPLACEMENT_TRIAGE`):** `TACTICAL_OR_ROLE_ADJUSTMENT_FIRST`, 4 comparisons (`CURRENT_PLAYER`, `NO_COIN_TACTICAL_ADJUSTMENT`, `CANDIDATE_ALT_A`, `CANDIDATE_ALT_B`), `MARKET_PRICE_UNAVAILABLE`.
- **Category E (`E_MULTI_OBJECTIVE_SQUAD_OPTIMIZER`):** `SCIPY_LINEAR_SUM_ASSIGNMENT`, `exact_parity_checked=true`, `exact_optimal_gap=0.0`, `utility=0.65725`, all 11-player/GK/uniqueness/position/budget constraints verified.
- **Category F (`F_COPILOT_TOOLS_AND_ROUTING`):** `12` Phase 43 tools verified; `TACTICAL_LAB` query `"Compare 4-3-3 and 4-2-3-1 for my playstyle"` routed to `TACTICAL_RECOMMENDATION` and executed `compare_formations`.
- **Category G (`G_CV_RUNTIME_AND_CALIBRATION`):** `NO_TRAINED_WEIGHTS_PRESENT`, `SYNTHETIC_CALIBRATED_GEOMETRY_PROXY` calibration `ECE=0.0643`, `Brier=0.0042`.

## 4. Database Idempotency Check
Ran `C:\Python315\python.exe scripts/setup_database.py` twice sequentially: `020_phase43_complete_experiment_lab.sql` applied on pass 1 and reported `skip (applied)` on pass 2 cleanly.
