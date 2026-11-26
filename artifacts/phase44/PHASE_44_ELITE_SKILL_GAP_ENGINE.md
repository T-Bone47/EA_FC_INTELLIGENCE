# Phase 44 Elite Skill-Gap & Execution-Differential Engine

## 1. Architectural Separation (`backend/services/elite_skill_gap_engine.py`)
`EliteSkillGapEngine.analyze(user_profile, reference_pro=None)` operates strictly over the **7 Group G Technical Execution & Decision IQ features** (`PROFICIENCY_FEATURE_IDS`) plus telemetry mappings (`pass_accuracy -> pass_success_rate`, `defensive_transition_management -> defensive_recovery_success`):
- `pass_success_rate` (higher is better)
- `possession_loss_rate` (lower is better)
- `shooting_execution_quality` (higher is better)
- `defensive_recovery_success` (higher is better)
- `decision_regret_inverse` (higher is better)
- `execution_consistency` (higher is better)
- `opportunity_conversion_rate` (higher is better)

## 2. Verified Benchmark vs Internal Target Mode
- When a rights-verified (`RIGHTS_VERIFIED` or `RESEARCH_ONLY`) pro profile matching the user's `FC26`/`FC27` edition provides `proficiency_values`, `reference_population_verified = True` and `reference_scope = "AUTHORIZED_PRO:<alias>"`.
- Otherwise sets `reference_population_verified = False`, `reference_scope = "INTERNAL_EXECUTION_TARGET_BENCHMARK"`, and attaches explicit caveats clarifying that tournament execution benchmarks await authorized pro ingestion.
- Outputs prioritized `gaps` (sorted by magnitude), `strengths` / `INSUFFICIENT_EVIDENCE` items, drill objectives mapped to Training Academy categories, and non-purchase tactical adjustments.
