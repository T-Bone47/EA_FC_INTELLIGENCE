# PHASE 41: Blind-Review Decision Annotation Protocol

**Modules:** `backend/domain/phase41_models.py` (`DecisionAnnotationRequest`), `db/migrations/016_phase41_decision_intelligence.sql` (`phase41_decision_annotation`)

## 1. Core Annotation Rules
1. **Blind Review First:** `GET /api/phase41/windows` and `/research/decision-lab` default to `reveal_outcome=false` (`blind_review_completed=True`) so annotators evaluate the pre-action freeze frame without seeing whether a risky pass succeeded or failed.
2. **Multi-Answer Ground Truth:** Both `best_option_id` and `defensible_option_ids` (`List[str]`) are persisted so closely balanced tactical options (within uncertainty tolerance) remain accepted rather than forcing artificial single-choice labels.
3. **Controller Discipline:** Annotators and automated extractors leave manual cursor/off-ball triggers `UNKNOWN` unless explicitly corroborated by input or verified HUD telemetry.
4. **Disagreement Notes:** Qualitative disagreement justifications are stored alongside model rankings to support future calibration/error audits without altering pre-action historical fixtures.
