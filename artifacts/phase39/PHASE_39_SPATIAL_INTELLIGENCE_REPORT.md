# Phase 39: Spatial Intelligence Engine Report

## 1. Implemented Spatial Models (`backend/services/spatial_intelligence.py`)

### 1.1 Epistemic Model Mode Distinction
`SpatialIntelligenceEngine` strictly enforces model mode separation:
- `HEURISTIC_GAUSSIAN_INFLUENCE` (default active mode): Vectorized Spearman-inspired anisotropic bivariate Gaussian control over a **21 × 14 grid** (5.0 m × 4.86 m cells across 105 m × 68 m pitch), conditioned on player position + 0.45 s velocity projection + motion alignment stretch and attenuated (`0.75×`) for occluded `INTERPOLATED` tracks.
- `EMPIRICALLY_CALIBRATED_PITCH_CONTROL`: Only activated when empirically fitted probability weights are supplied (`empirically_calibrated=True`). Not asserted on uncalibrated geometry.
- `INSUFFICIENT_OBSERVATION`: Emitted immediately when `calibration_state == REJECTED`, `scene_class != ACTIVE_GAMEPLAY`, or fewer than 6 tracked players hold valid coordinates (`home_pitch_control_pct = None`).

### 1.2 Spatial Metrics Computed Per Snapshot
- **Kinematics:** Central/backward finite-difference velocity $(v_x, v_y, |v|)$ and acceleration $(a_x, a_y, |a|)$ over consecutive timestamps, flagging non-physical jump artifacts (`> 11.8 m/s` -> `kinematic_anomaly=True`).
- **Expected Threat (`xT`):** Positional threat progression mapped on Karun Singh's 12×8 zone matrix oriented toward the active team's attacking goal.
- **Line Integrity & Structure:** Defensive line $X$, midfield line $X$, forward line $X$, `def_to_mid_gap_m`, `mid_to_att_gap_m`, team width, team length, convex hull compactness area ($m^2$), implied band formation when $\ge 8$ outfielders known, and `rest_defense_count` behind the ball.
- **Lateral Occupancy & Overloads:** 5-lane width counters (`LEFT_FLANK`, `LEFT_HALF_SPACE`, `CENTRAL_SPINE`, `RIGHT_HALF_SPACE`, `RIGHT_FLANK`) and 18-zone `(home, away, delta)` overload counts.
- **Passing Lane Corridors:** Shortest orthogonal distance from opposing players onto passing line segments to teammates, scoring `OPEN`, `CONTESTED`, `BLOCKED` status alongside progressive `xt_gain`.

---

## 2. Uncertainty Gating Rules

| Condition | Assigned `UncertaintyBand` | Impact on Downstream Layers |
| :--- | :--- | :--- |
| `GOOD` calibration & coverage $\ge 70\%$ | `LOW` | Full coaching diagnostics permitted |
| Partial coverage ($45\%$–$69\%$) or `COARSE` | `MODERATE` | Confidence capped at `<= 0.78` with coverage caveat |
| Coverage $< 45\%$ ($\ge 6$ players) | `HIGH` | Confidence capped at `<= 0.55` |
| `REJECTED` calibration or `< 6` players | `UNRELIABLE` | Pitch control withheld (`null`); excluded from tactical coaching |
