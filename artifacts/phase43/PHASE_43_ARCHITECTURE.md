# Phase 43 Architecture Overview

## 1. Closed-Loop System Flow
Phase 43 closes the loop between theoretical tactical modeling, multi-objective squad selection, match-level N-of-1 experimentation, computer vision telemetry, and personal meta tracking:

1. **Immutable Tactical Snapshot Layer (`TacticalSnapshotService`)**
   - Persists versioned `TacticalConfigurationSnapshot` (`phase43_tactical_snapshot`), hashing configuration payloads (`compute_config_hash`), recording mid-match shifts (`mid_match_changes`), preserving explicit `unknown_fields`, computing configuration diffs (`diff_snapshots`), and enforcing `FC26`/`FC27` edition walls.
2. **4-Phase Empirical Fingerprint Layer (`TacticalFingerprintEngine`)**
   - Separates nominal pre-match formation from observed in-possession, out-of-possession, attacking-transition, and defensive-transition structures (`phase43_tactical_fingerprint`).
   - Attaches per-metric `FingerprintMetricDetail` provenance and enforces explicit abstention when `visible_outfield_players < 14` or tracking calibration/coverage is insufficient.
3. **Personal Formation Intelligence (`PersonalFormationEngine`)**
   - Evaluates all 12 formations in `FORMATION_SLOTS` across three explicitly separated evidentiary signals: `theoretical_fit`, `observed_performance`, and `controlled_experiment_evidence`.
4. **Constrained Multi-Objective Squad Optimizer (`MultiObjectiveSquadOptimizer`)**
   - Optimizes 11-player lineups across 7 objectives using `scipy.optimize.linear_sum_assignment`, exact combinatorial small-pool parity checks, and `compute_whole_xi_synergy` without modifying frozen V3.2.1 player weights.
5. **Counterfactual & Replacement Lab (`TacticalCounterfactualService`, `ReplacementExperimentService`)**
   - Performs zone-geometry deltas, epistemic labeling, parameter sensitivity sweeps, and behavior-before-coins replacement triage while keeping `MARKET_PRICE_UNAVAILABLE` uninvented.
6. **N-of-1 Experiment Engine & Statistical Inference (`TacticalExperimentEngine`, `ExperimentAnalysisService`)**
   - Manages protocol versioning (`phase43_experiment_protocol_version`), seeded schedule assignments (`phase43_experiment_assignment`), adherence tracking, match-clustered SciPy + conjugate Bayesian inference (`phase43_experiment_analysis`), sample-size planning, and confounder auditing.
7. **Patch-Isolated Personal Meta & Feedback Ledger (`PersonalMetaService`)**
   - Aggregates patch-isolated user findings (`phase43_personal_meta`) and records user adoption/rejection feedback (`phase43_recommendation_feedback`).
8. **Context-Aware Co-Pilot (`CoachToolRegistry` + `PersonalCoachOrchestrator`)**
   - Exposes 12 core Phase 43 tools (plus confirmation-gated creation and advisory aliases) to Gemini/OpenRouter free tiers with deterministic fallback and `/tactical-lab` Stadium 3.0 UI.
