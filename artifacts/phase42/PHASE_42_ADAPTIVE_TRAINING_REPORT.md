# Phase 42 Adaptive Training & Continuous Improvement Report

**Core Services:** `backend/services/training_plan_service.py`, `backend/services/performance_progression_service.py`, `backend/api/routes/phase40_coach.py`  
**UI Integration:** `frontend/src/pages/PersonalCoach.tsx`

## 1. Adaptive 8-Category Freeze-Frame Academy (`42H`)
`TrainingPlanService` (`TRAINING_CATEGORIES`) covers all 8 required EA FC decision skill dimensions:
1. `CB_SWITCHING_DISCIPLINE` (`defensive_discipline`)
2. `TRANSITION_REACTION` (`pivot_screening`)
3. `PASSING_SELECTION` (`progression_selection`)
4. `REST_DEFENSE` (`rest_defense`)
5. `PRESSING_TIMING` (`pressing_discipline`)
6. `FINISHING_SHOT_SELECTION` (`finishing_selection`)
7. `WING_OVERLOAD_VS_SWITCH` (`width_switching`)
8. `CONSERVATIVE_BALL_RETENTION` (`ball_retention`)

### Decision-Window Blind-Review Integration
- `/api/phase40/training/plan` and `CoachToolRegistry.generate_training_plan` query non-synthetic Phase 41 Decision Windows via `Phase41Repository.list_decision_windows(..., exclude_synthetic=True)`.
- High-regret windows are converted into `TrainingExercise` items (`EX-WIN-...`, `linked_window_id` populated, `hide_outcome_by_default=True`, difficulty scaled `FUNDAMENTAL / INTERMEDIATE / ADVANCED`).
- `GET /training/plan` withholds match outcome until submission; `POST /training/attempt` reveals `revealed_outcome`, `tactical_reasoning`, and `in_game_drill` only after the user commits an answer.

## 2. Calibrated BKT & Strict Separation (`42H`)
- `bkt_update()` bounds slip `[0.03, 0.25]`, guess `[0.05, 0.35]`, and transit `[0.05, 0.30]`, marking every posterior state `practice_only=True` and `status="EXPERIMENTAL_UNVALIDATED_MASTERY"` so freeze-frame drill mastery never impersonates live match Skill Rating.
- `evaluate_bkt_calibration()` computes sample count, mean predicted probability, observed accuracy, and empirical **Brier score** across recorded attempt logs (`test_phase42_adaptive_training_decision_linkage_and_closed_loop_progression` verified).

## 3. Closed-Loop Progression & Covariate Control (`42I`)
`PerformanceProgressionService.evaluate()` builds `weakness_loop_tracking` and `covariate_summary`:
- Joins each diagnostic weakness (`diagnostic_code`) to its mapped training skill, practice attempts, practice accuracy, latest BKT posterior, and opportunity-normalized early-vs-recent occurrence rate (`rate_delta`).
- Surfaces verdicts (`PROVISIONAL_IMPROVEMENT`, `PROVISIONAL_REGRESSION`, `NO_MATERIAL_SHIFT`, `INSUFFICIENT_COMPARABLE_MATCHES`).
- Explicitly stratifies and warns on `patches`, `formations`, `gameplay_modes`, `squad_strata`, and `opponent_quality_buckets`, accompanied by mandatory `causal_disclaimer` separating within-person observational correlation from causal proof.
- Verified in `PersonalCoach.tsx` live UI and `test_phase42_copilot_cv_training.py`.
