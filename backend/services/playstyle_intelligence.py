"""Phase 39 Stage 5: Experimental PlayStyle Behavioural Signature Framework.

Evaluates observable gameplay kinematics against expected physical/technical profiles
for 10 EA SPORTS FC PlayStyles+.

Epistemic Safeguard:
Strictly separates:
  1. EXPLICIT_HUD_OBSERVED  -> Exact PlayStyle icon/badge directly detected in decoded HUD.
  2. BEHAVIOUR_CONSISTENT   -> Kinematic / spatial movement curve aligns with PlayStyle profile.
  3. UNKNOWN_ACTIVATION     -> Cannot verify trait firing from video alone (default epistemic guard).
Never claims a PlayStyle activated solely because kinematics match an expectation.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.domain.video_gameplay import TacticalEvent
from backend.domain.video_ingestion import DataProvenance
from backend.services.spatial_intelligence import UncertaintyBand


class PlayStyleEpistemicState(str, Enum):
    EXPLICIT_HUD_OBSERVED = "EXPLICIT_HUD_OBSERVED"
    BEHAVIOUR_CONSISTENT = "BEHAVIOUR_CONSISTENT"
    UNKNOWN_ACTIVATION = "UNKNOWN_ACTIVATION"


SUPPORTED_PLAYSTYLES = [
    "Quick Step+",
    "Rapid+",
    "Anticipate+",
    "Bruiser+",
    "Intercept+",
    "Whipped Pass+",
    "Incisive Pass+",
    "Technical+",
    "First Touch+",
    "Relentless+",
]


class PlayStyleSignatureReport(BaseModel):
    playstyle_name: str
    epistemic_state: PlayStyleEpistemicState
    activation_claim_permitted: bool = False
    observed_signature_count: int = 0
    best_evidence_timestamps: List[float] = Field(default_factory=list)
    measured_metrics: Dict[str, Any] = Field(default_factory=dict)
    explanation: str
    provenance: str


class PlayStyleIntelligenceEngine:
    """Computes conservative behavioural signatures across the 10 tracked PlayStyles+."""

    def analyze(
        self,
        spatial_result: Dict[str, Any],
        events: Optional[List[TacticalEvent]] = None,
        hud_observed_playstyles: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        frames: List[Dict[str, Any]] = spatial_result.get("frames", [])
        usable = [f for f in frames if f.get("uncertainty_band") != UncertaintyBand.UNRELIABLE.value]
        hud_set = {s.strip().casefold() for s in (hud_observed_playstyles or [])}
        events = events or []

        provenance = usable[0].get("provenance", DataProvenance.REAL_VIDEO_DECODED.value) if usable else DataProvenance.SYNTHETIC_FIXTURE.value

        # Aggregate kinematic statistics from reliable tracking frames
        all_kins = [k for f in usable for k in f.get("kinematics", [])]
        max_accel = max((k["accel_mps2"] for k in all_kins if not k.get("kinematic_anomaly")), default=0.0)
        max_speed = max((k["speed_mps"] for k in all_kins if not k.get("kinematic_anomaly")), default=0.0)

        quick_bursts = sorted({round(f["timestamp_sec"], 2) for f in usable if any(k["accel_mps2"] >= 4.5 and not k.get("kinematic_anomaly") for k in f.get("kinematics", []))})
        rapid_runs = sorted({round(f["timestamp_sec"], 2) for f in usable if any(k["speed_mps"] >= 8.2 and k["track_id"] == f.get("ball_carrier_track_id") for k in f.get("kinematics", []))})
        agile_drib = sorted({round(f["timestamp_sec"], 2) for f in usable if any(3.2 <= k["speed_mps"] <= 6.8 and k["accel_mps2"] >= 2.8 and k["track_id"] == f.get("ball_carrier_track_id") for k in f.get("kinematics", []))})
        relentless_late = sorted({round(f["timestamp_sec"], 2) for f in usable if f["timestamp_sec"] >= 15.0 and any(k["speed_mps"] >= 7.0 for k in f.get("kinematics", []))})

        interception_ts = sorted({round(e.timestamp_start, 2) for e in events if e.event_type in ("INTERCEPTION", "TURNOVER")})
        tackle_ts = sorted({round(e.timestamp_start, 2) for e in events if e.event_type == "TACKLE_WON"})
        through_pass_ts = sorted({round(f["timestamp_sec"], 2) for f in usable if any(l["is_progressive"] and l["xt_gain"] >= 0.03 for l in f.get("passing_lanes", []))})
        flank_cross_ts = sorted({round(f["timestamp_sec"], 2) for f in usable if f.get("ball_xy") and (f["ball_xy"][1] <= 12.0 or f["ball_xy"][1] >= 56.0) and f["ball_xy"][0] >= 70.0})

        specs = [
            ("Quick Step+", quick_bursts, {"max_acceleration_mps2": round(max_accel, 2)},
             "Explosive initial acceleration bursts (>= 4.5 m/s^2) observed from low speed."),
            ("Rapid+", rapid_runs, {"peak_carrier_speed_mps": round(max_speed, 2)},
             "High-velocity ball carry (>= 8.2 m/s) over open space."),
            ("Anticipate+", tackle_ts, {"clean_tackles_observed": len(tackle_ts)},
             "Clean ball-winning stand tackles with immediate possession retention."),
            ("Bruiser+", tackle_ts, {"physical_challenge_recoveries": len(tackle_ts)},
             "Shoulder-to-shoulder physical tackle contact winning ground control."),
            ("Intercept+", interception_ts, {"interception_events": len(interception_ts)},
             "Passing-lane disruption and clean interception reactions."),
            ("Whipped Pass+", flank_cross_ts, {"wide_attacking_delivery_windows": len(flank_cross_ts)},
             "Final-third wide delivery posture from flank channels."),
            ("Incisive Pass+", through_pass_ts, {"high_xt_corridor_chances": len(through_pass_ts)},
             "Through-ball line-breaking corridor progression opportunity."),
            ("Technical+", agile_drib, {"controlled_turn_bursts": len(agile_drib)},
             "Controlled medium-speed directional turns under close defense."),
            ("First Touch+", [], {}, "Requires ball deceleration vector on first-contact trap."),
            ("Relentless+", relentless_late, {"late_window_sprints": len(relentless_late)},
             "Sustained high-intensity sprint repeatability later in clip window."),
        ]

        reports: List[PlayStyleSignatureReport] = []
        for name, ts_list, metrics, desc in specs:
            if name.casefold() in hud_set:
                state = PlayStyleEpistemicState.EXPLICIT_HUD_OBSERVED
                claim = True
                note = f"{desc} Explicit HUD badge detected for {name}."
            elif len(ts_list) >= 1 and len(usable) >= 2:
                state = PlayStyleEpistemicState.BEHAVIOUR_CONSISTENT
                claim = False
                note = (
                    f"{desc} Kinematics matched expectations ({len(ts_list)} window(s)), "
                    f"but PlayStyle+ activation cannot be proven solely from movement trajectories."
                )
            else:
                state = PlayStyleEpistemicState.UNKNOWN_ACTIVATION
                claim = False
                note = f"Insufficient verified HUD or kinematic evidence to link gameplay to {name}."

            reports.append(PlayStyleSignatureReport(
                playstyle_name=name,
                epistemic_state=state,
                activation_claim_permitted=claim,
                observed_signature_count=len(ts_list),
                best_evidence_timestamps=ts_list[:6],
                measured_metrics=metrics,
                explanation=note,
                provenance=provenance,
            ))

        return {
            "provenance": provenance,
            "playstyles": [r.model_dump() for r in reports],
            "epistemic_policy": (
                "BEHAVIOUR_CONSISTENT reports kinematic compatibility only. Game engine "
                "PlayStyle+ trait firing requires EXPLICIT_HUD_OBSERVED detection."
            ),
        }
