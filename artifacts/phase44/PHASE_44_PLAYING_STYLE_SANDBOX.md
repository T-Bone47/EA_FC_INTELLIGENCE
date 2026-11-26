# Phase 44 Playing Style Sandbox

## 1. Five Interactive Non-Mutating Modes (`PlayingStyleSandbox`)
Implemented in `backend/services/style_squad_training_bridge.py`:
1. `SUPPORT_NATURAL_POSSESSION` (`POSSESSION`, default `4-2-3-1`)
2. `SHIFT_COUNTER_ATTACK` (`COUNTER_ATTACK`, default `4-4-2`)
3. `BALANCE_STABILITY_CREATIVITY` (`BALANCED`, default `4-2-3-1`)
4. `PRO_INSPIRED_TEMPLATE` (`PERSONALIZED`, structural template mapped safely to `4-2-3-1`; zero fabricated pro telemetry)
5. `NATURAL_VS_BALANCED` (`PERSONALIZED`, default `4-3-3`)

## 2. Dry-Run Isolation & Optional Phase 43 Experiment Handoff
- Uses Phase 43 `MultiObjectiveSquadOptimizer` (`scipy.optimize.linear_sum_assignment` exact slot assignment) under strict hard constraints (`exact_11_players`, `single_gk`, `all_players_unique`, `position_slots_valid`, `edition_isolated`, `budget_verified_only`).
- Default calls leave saved squads and Phase 43 snapshots completely untouched (`non_mutating_preview = True`).
- When user explicitly sets `convert_to_experiment = True`, builds Baseline vs Variant `TacticalConfigurationSnapshot` pairs via `TacticalSnapshotService` and initializes an `ABBA` `FORMATION_COMPARISON` experiment in `TacticalExperimentEngine`.
