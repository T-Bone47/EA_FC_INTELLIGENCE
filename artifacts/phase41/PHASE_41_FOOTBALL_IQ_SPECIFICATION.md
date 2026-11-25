# PHASE 41M: Multi-Dimensional Football IQ Profiling Specification

**Module:** `backend/services/football_iq_engine.py`

## 1. 10 Core Decision Dimensions
1. `passing_risk_balance` — Passing Risk & Progression Balance
2. `line_breaking_awareness` — Line-Breaking Pass Recognition
3. `pressing_resistance_choices` — Pressing Resistance & Retention
4. `switching_play_timing` — Switching Play & Width Timing
5. `final_third_chance_selection` — Final-Third Shot vs Pass Selection
6. `defensive_patience_vs_diving` — Defensive Patience vs Diving In
7. `central_channel_protection` — Central Channel Protection
8. `transition_recovery_decisions` — Transition Recovery Decisions
9. `rest_defense_discipline` — Rest-Defense Discipline
10. `off_ball_spacing_and_runs` — Off-Ball Spacing & Run Timing

## 2. Four-Way Analytic Separation
For each dimension, `FootballIQDimensionScore` tracks separately:
- `preference_value` (frequency/tendency share)
- `execution_error_rate` (post-action turnovers occurring on low-regret `<= 0.035` defensible choices)
- `decision_quality_score` ($0\text{–}100$ cluster-deduplicated score derived purely from pre-action normalized regret)
- `outcome_success_rate` (observed post-action retention fraction, decoupled cleanly from pre-action decision grading)

## 3. Epistemic Safeguards
- Any window marked `SYNTHETIC_FIXTURE` is strictly filtered out prior to dimension clustering and surfaced transparently in `synthetic_excluded_count`.
- Dimensions with zero verified clusters return `score_0_100 = None` and `confidence = "INSUFFICIENT"`.
