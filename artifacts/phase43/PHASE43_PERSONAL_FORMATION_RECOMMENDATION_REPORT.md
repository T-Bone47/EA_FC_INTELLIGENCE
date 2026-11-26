# Phase 43F Personal Formation Recommendation Engine Report

## 1. Hybrid Theoretical + Empirical Ranking Architecture
`PersonalFormationEngine` (`backend/services/personal_formation_engine.py`) ranks formations across `_FORMATION_TRAITS` (`4-2-3-1`, `4-3-3`, `4-4-2`, `4-2-2-2`, `4-1-2-1-2`, `3-5-2`) cross-checked against `FORMATION_SLOTS`, strictly partitioned by `(user_id, game_version, game_patch)`.

### Scoring Composition
For each formation:
1. **Theoretical Fit (`theo`):** Combines `GamerDNAEngine` style/proficiency estimates (`wing_utilization`, `central_progression`, `pressing_intensity`, and `defensive_transition_management`) against formation traits (`width_bias`, `central_bias`, `rest_defense`, `press_support`) using weights `0.30`, `0.30`, `0.25`, `0.15`.
2. **Observed Personal Match Stability:** Aggregates non-synthetic patch matches per formation (`1 - exposed_transitions / transition_opportunities` or fallback `defensive_compactness`).
3. **Validated Experiment Adjustments:** Counts user experiments reaching `SUPPORTED_IMPROVEMENT` (crediting `arm_b.formation`) or `SUPPORTED_REGRESSION` (crediting `arm_a.formation`), adding `+0.06 * experiment_wins` + `+0.04 * (observed_avg - 0.5)`.
4. **Sort & Epistemic Grade Hierarchy:** Sorted by `(experiment_wins, theoretical_score)` descending; labels each row accurately as `CONTROLLED_EXPERIMENT_EVIDENCE` (`experiment_wins > 0`), `OBSERVED_ASSOCIATION` (`>=2` observed matches), or `THEORETICAL_SUITABILITY` (cold-start / sparse formations).

## 2. Preserved Platform Invariants
- `frozen_v321_preserved=True` is preserved cleanly (`V3.2.1` card weights/scoring are never altered).
- Every formation row includes concrete role guidance (`recommended_roles`, e.g., `LDM Holding (Defend)`, `RDM Deep-Lying Playmaker (Build-Up)`, `CAM Playmaker`), `strengths`, `risks`, and an explicit advisory `caveat` refusing guaranteed match wins.
- **Verified Outputs:**
  - Zero-match live browser user (`phase43qa@example.com`, `FC26`): ranked all 6 formations cleanly (`4-4-2` `81%`, `4-3-3` `79%`, etc.) tagged `THEORETICAL_SUITABILITY`.
  - Benchmark closed-loop user (`bench-phase43-gamer`, `FC27`): elevated `4-2-3-1` to #1 (`theoretical_score=0.8899`, `observed_match_count=3`, `experiment_wins=1`, grade `CONTROLLED_EXPERIMENT_EVIDENCE`).
