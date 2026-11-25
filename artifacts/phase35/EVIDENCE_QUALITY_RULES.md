# EA FC INTELLIGENCE — PHASE 35
# EVIDENCE QUALITY & VALIDATION GOVERNANCE RULES

**Governance Standard:** EQG-2026-v35  
**Engine Baseline:** V3.2.1 Frozen Deterministic Core  
**Enforcement Engine:** `backend/domain/empirical_observation.py`  

---

## 1. Automated Quality Gate Rules

Every incoming empirical observation record is evaluated against seven categorical validation rules before progression to `ACCEPTED`:

| Rule Code | Evaluation Scope | Acceptance Condition | Action on Failure |
|:---|:---|:---|:---|
| **`EQR-001-DNF`** | Match Completion | Final minute reached $\ge 75$ AND `dnf == False` | Immediate transition to `REJECTED` (`MATCH_PREMATURE_TERMINATION`). |
| **`EQR-002-MIN`** | Card Exposure | Subject card `minutes_played >= 60` | Immediate transition to `REJECTED` (`INSUFFICIENT_MINUTES_PLAYED`). |
| **`EQR-003-DEF`** | Controller Mode | `tactical_defending == True` | Immediate transition to `REJECTED` (`CONTROLLER_ASSIST_VIOLATION`). |
| **`EQR-004-PAT`** | Patch Invariance | `patch_version == manifest.patch_version` | Transition to `SUPERSEDED` (`PATCH_VERSION_MISMATCH`). |
| **`EQR-005-NET`** | Network Health | `connection_ping_ms <= 80.0` AND `input_delay != 'SEVERE'` | Transition to `INSUFFICIENT_EVIDENCE` (`LATENCY_LIMIT_EXCEEDED`). |
| **`EQR-006-ROS`** | Teammate Invariance | 100% of surrounding 10 slots match frozen manifest | Immediate transition to `REJECTED` (`ROSTER_INVARIANCE_VIOLATION`). |
| **`EQR-007-INT`** | Cryptographic Digest | SHA-256 hash matches payload attributes | Flag as `REJECTED` (`TAMPER_OR_CORRUPT_PAYLOAD`). |

---

## 2. Reviewer Verification Checklist

Human and automated QA reviewers must confirm the following physical artifacts prior to promoting an observation from `UNDER_REVIEW` to `ACCEPTED`:

1. **Video Timestamp Watermark:** Clip contains uninterrupted on-screen game clock matching recorded events.
2. **Scoreboard Continuity:** Goal count increments match recorded goal events without cuts or missing game time.
3. **Player Identity Display:** Individual player jersey number, name banner, and stamina bar match the recorded subject card.
4. **No Sliders / Modded Chemistry:** Game settings screen confirmed default sliders ($50/50$ User/CPU).

---

## 3. Honest Data Policy & Database Quarantine

- **Zero-Tolerance for Synthesized Production Matches:** No match record may be marked `ACCEPTED` unless backed by verified gameplay telemetry.
- **Current Staging Baseline Notice:** As documented in `BASELINE_REPOSITORY_AUDIT.md`, accepted live matches in `fc27_staging` currently stand at **0**. All downstream recommendation rules remain strictly tagged as `MODELED_HEURISTIC` until the required empirical power thresholds ($N \ge 30$ pairs) are satisfied.
- **Quarantine Store:** Any record failing automated rules is quarantined in the rejected audit log with an immutable timestamp and explanation string, preventing accidental inclusion in statistical aggregations.
