# Phase 43 N-of-1 Experiment Design Specification

## 1. Eight Supported Experiment Workflows
`ExperimentType` supports:
- `FORMATION_COMPARISON`
- `TACTICAL_PRESET_COMPARISON`
- `PLAYER_ROLE_FOCUS_COMPARISON`
- `DEFENSIVE_HEIGHT_PRESS_COMPARISON`
- `BUILD_UP_STYLE_COMPARISON`
- `PLAYER_PARTNERSHIP_COMPARISON`
- `SINGLE_POSITION_REPLACEMENT`
- `PERSONAL_PLAYSTYLE_COMPATIBILITY`

## 2. CENT 2015 Protocol Versioning, Lifecycle & Assignment Schedule
- **Lifecycle States (`ExperimentStatus` & DB constraint in Migration 020):** `DRAFT`, `READY`, `ACTIVE`, `COLLECTING_EVIDENCE`, `READY_FOR_ANALYSIS`, `COMPLETED`, `INCONCLUSIVE`, `INSUFFICIENT_EVIDENCE`, `PAUSED`, `CANCELLED`, `ARCHIVED`. Transitions managed via `PATCH /api/phase43/experiments/{experiment_id}/status`.
- **Immutable Protocols (`phase43_experiment_protocol_version`):** Captures `version_number`, `hypothesis`, `design_type`, `primary_metric`, `secondary_metrics`, `minimum_meaningful_improvement`, `planned_observations`, `required_coverage_pct`, `stopping_criteria_json`, and `confounder_controls_json`.
- **Seeded Schedules & Adherence (`phase43_experiment_assignment`):**
  - Designs: `CROSSOVER_ABBA` (counterbalanced ABBA/BAAB blocks), `RANDOMIZED_BLOCKED` (seeded permuted blocks), `MATCHED_COMPARISON`, and `DESCRIPTIVE_BEFORE_AFTER`.
  - When a match is linked (`POST /api/phase43/experiments/{id}/matches`), the repository compares played arm/snapshot against the next `PENDING` scheduled assignment, marking `COMPLETED` (`adherent=True`) or `DEVIATED` (`adherent=False`) and tracking overall `adherence_rate`.
- **Read-Only Advisory Creation:** `GET /api/phase43/experiments/suggest` and `POST /api/phase43/experiments/preview` (plus Co-Pilot `create_tactical_experiment(..., confirm=False)`) never mutate saved configurations without explicit user confirmation.
