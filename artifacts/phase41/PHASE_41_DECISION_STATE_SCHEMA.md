# PHASE 41B/41C: Decision State Schema & Anti-Hindsight Protocol

**Module:** `backend/domain/phase41_models.py`, `backend/services/decision_state_builder.py`

## 1. Strict Pre-Action / Post-Action Boundary
- Every decision window is indexed by `action_timestamp_sec` ($t_0$) and freezes its `FootballDecisionState` at `pre_action_cutoff_sec` ($t_0 - \Delta t$, strictly prior to action release).
- Ball state (`PreActionBallState`), outfield coordinates/velocities (`PreActionPlayerState`), and structure metrics (`PreActionTeamStructure`) are derived solely from frames $\le t_{\text{cutoff}}$.
- Any observed outcome (`PostActionOutcome`: possession retained at $+3\text{s}$, realized xT delta at $+5\text{s}$, shot/transition conceded within $+8\text{s}$) is quarantined and stripped unconditionally via `strip_hindsight()` before candidate generation, passing physics, EPV/xT evaluation, defensive/shooting logic, or counterfactual ranking runs.

## 2. Decision-Type-Specific Observation Adequacy (`FieldAdequacyReport`)
| Decision Category | Minimum Thresholds | Degradation Mode |
| :--- | :--- | :--- |
| **Short Pass / Retention** | Calibration $\neq$ `REJECTED`, coverage $\ge 45\%$, ball visible, $\ge 1$ local teammate ($\le 22\text{m}$) | Local corridors evaluated (`ADEQUATE` or `PARTIAL_WITH_UNCERTAINTY`) |
| **Long Switch / Cross** | Coverage $\ge 62\%$, $\ge 5$ visible teammates, $\ge 5$ opponents | Falls back to `PARTIAL_WITH_UNCERTAINTY` marking off-screen far wing `UNKNOWN` |
| **Defensive Action** | Coverage $\ge 55\%$, $\ge 8$ positioned players | `INSUFFICIENT_ABSTAIN` below threshold |
| **Shot** | Coverage $\ge 48\%$, ball visible, GK or goalmouth defenders detected | `INSUFFICIENT_ABSTAIN` if goalmouth unobserved |

## 3. Window Clustering (`DecisionOpportunityDetector`)
Consecutive frames sampled at high frequency (e.g. 10 Hz) within `min_window_gap_sec = 2.0` and matching carrier/possession context are assigned shared `cluster_id` identifiers so one slow dribbling/pressing passage is never double-counted into inflated regret counts.
