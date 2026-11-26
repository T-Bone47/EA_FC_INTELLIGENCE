# Phase 44 Style Evolution & Experiment-Attributed Drift

## 1. Longitudinal Windowing & EWMA (`backend/services/style_evolution_engine.py`)
`StyleEvolutionEngine.analyze()` evaluates chronological non-synthetic matches (`game_version`-filtered) across adaptive windows:
- Tracks 6 core style dimensions (`possession_retention_preference`, `direct_progression`, `pressing_tendency`, `wide_attacking_preference`, `central_attacking_preference`, `risk_taking_preference`) with Exponentially Weighted Moving Average (`alpha = 0.45`).
- Computes window stability score (`1 - 2.2 * mean_SE`, bounded `[0.1, 0.98]`), archetype transitions (`Window i -> i+1`), and mean-shift detection (`shift_detected = True` when max EWMA delta across endpoints `>= 0.12` or an archetype transition occurred).

## 2. Phase 43 Tactical Experiment Attribution
Links windows to non-draft `Phase43Repository.list_experiments()` records (`READY`, `ACTIVE`, `READY_FOR_COMPARISON`, `INCONCLUSIVE`, `COMPLETED`) when match IDs appear in `linked_matches`, formations match analyzed arms, or the active experiment overlaps the window — separating deliberate tactical testing from organic playstyle drift cleanly.
