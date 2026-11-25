# PHASE 41H/41I/41J: Defensive Decision, Shooting & Off-Ball Intelligence Specification

**Module:** `backend/services/defensive_and_chance_intelligence.py`

## 1. Defensive Decision Intelligence (41H)
- Compares 7 defensive response families across central Zone-14 protection, ball-carrier pressure, defensive-to-midfield line gap delta, and defender displacement risk.
- Enforces **team-shape framing** (`controlled_player_known = False`) whenever video/telemetry lacks active player-cursor confirmation, preventing false blame on manual vs AI defender movement.

## 2. Shooting & Chance-Creation Intelligence (41I)
- Quantifies Euclidean shot distance, goalmouth subtended angle ($\text{deg}$ across $7.32\text{m}$ posts), defender blocker cone count, and goalkeeper line proximity.
- Compares shot heuristic utility directly against the highest-scoring non-shot pass/carry alternative (`shot_advantage_delta`).
- Enforces `is_calibrated_xg = False` and `evaluation_mode = "HEURISTIC_CHANCE_UTILITY"` so shot estimates are never mislabeled as empirically calibrated expected goals (xG).

## 3. Off-Ball Opportunity & Run Detection (41J)
- Identifies teammates accelerating at $\ge 2.2\text{ m/s}$ into `DEPTH_STRETCH`, `OVERLAP`, `HALF_SPACE_POCKET`, or `SUPPORT_ANGLE` lanes, plus defenders dragged out of position.
- Preserves explicit controller distinction (`GAMER_CONTROLLED`, `AI_TEAMMATE`, `TACTICAL_INSTRUCTION_HYPOTHESIS`, defaulting safely to `UNKNOWN` without input telemetry).
