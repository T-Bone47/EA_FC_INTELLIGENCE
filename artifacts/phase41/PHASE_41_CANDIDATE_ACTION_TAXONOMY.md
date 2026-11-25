# PHASE 41D: Candidate Action Taxonomy & Feasibility Rules

**Module:** `backend/services/candidate_action_generator.py`

## 1. Attacking Action Families (In-Possession)
1. `SHORT_PASS` / `LATERAL_OR_BACKWARD_PASS` (`ATTACKING_PASS` / `POSSESSION_RETENTION`)
2. `PROGRESSIVE_PASS` (`ATTACKING_PASS`, forward gain $\ge 6.0\text{m}$)
3. `THROUGH_BALL` (`THROUGH_BALL`, lead trajectory $> 17.5\text{m}$)
4. `SWITCH_PLAY` (`SWITCH_OR_CROSS`, distance $\ge 26\text{m}$ and lateral $\ge 18\text{m}$)
5. `CROSS_OR_CUTBACK` (`SWITCH_OR_CROSS`, final-third wide delivery)
6. `CARRY_INTO_SPACE` (`CARRY_OR_DRIBBLE`, unobstructed carrier advance $+7.5\text{m}$)
7. `RETAIN_AND_RESET` (`POSSESSION_RETENTION`, conservative ball shield/reset)
8. `SHOOT` (`SHOT`, unlocked when within $29.5\text{m}$ of target goal)

## 2. Defensive Action Families (Out-of-Possession)
1. `HOLD_LINE`
2. `RECOVER_WITH_CM_CDM`
3. `CONTAIN_BALL_CARRIER`
4. `CLOSE_PASSING_LANE`
5. `PRESS_BALL_CARRIER`
6. `TRACK_RUNNER`
7. `PRESERVE_CENTRAL_COVER`

## 3. Feasibility & Controller Honesty
- Each option explicitly declares `CandidateFeasibility` (`FEASIBLE`, `POSSIBLY_FEASIBLE`, `UNSUPPORTED`, `UNKNOWN`).
- Off-ball and controller tags remain `ControllerAttribution.UNKNOWN` whenever video/telemetry lacks button-stream verification.
- Epistemic classification stamps player/ball coords as `OBSERVED`, kinematic/xT counterfactual scores as `MODELLED`, and unexecuted counterfactual trajectories as `HYPOTHETICAL`.
