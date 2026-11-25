# PHASE 41P/41Q: Player Capability Bridge & Squad Decision Support Integration

**Modules:** `backend/services/personal_gameplay_fit.py`, `backend/api/routes/phase41_decisions.py`, `frontend/src/pages/CardSquadLab.tsx`

## 1. Decision Bottleneck vs Player Capability Isolation (`41P`)
`PersonalGameplayFitService.evaluate_decision_capability_bottleneck(...)` inspects non-synthetic high-regret (`regret >= 0.06`) decision windows and separates:
- **Gamer Decision Choice Bottlenecks:** High regret where safe local alternatives (`SHORT_PASS`, `RETAIN_AND_RESET`, `PRESERVE_CENTRAL_COVER`) already existed regardless of player rating.
- **Mixed Choice & Capability Constraints:** High regret on demanding counterfactual options (`SWITCH_PLAY`, `THROUGH_BALL`, `SHOOT`) that require specialized attributes (`long_passing`, `vision`, `finishing`) or PlayStyles+.

## 2. Squad Decision Support Simulation (`41Q`)
`PersonalGameplayFitService.simulate_squad_decision_support(...)` computes structural indicators surfaced in **Squad Lab -> Personal Coach & Fit**:
- `passing_outlets_score` (central hubs + wide outlet breadth)
- `midfield_press_resistance` (pivot count + slot rating signal)
- `transition_vulnerability_index` (rest-defense CB/CDM anchors vs pressing posture)
- Explicitly stamped `STRUCTURAL_ROLE_HEURISTIC` and leaves **Frozen V3.2.1** (`recommendation_engine_v3.py`, `v3_config.py`) untouched (`frozen_v321_untouched = True`).
