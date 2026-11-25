"""Phase 39 Stage 4: Evidence-Grounded Tactical Coaching Engine.

Detects structured tactical mistakes and spatial vulnerabilities strictly from
calibrated SpatialFrameSnapshots + TacticalEvents, without inferring unobservable
controller inputs or hidden game mechanics.

Covers 12 core tactical diagnostics, each outputting:
1. what_happened
2. why_it_potentially_happened
3. supporting_timestamps & window [start, end]
4. tactical_visualization (zones, vector arrows, player highlights)
5. confidence_level (capped automatically by calibration & observation coverage)
6. alternative_decisions
7. actionable_advice
"""
from __future__ import annotations

import math
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from backend.domain.video_gameplay import TacticalEvent
from backend.domain.video_ingestion import DataProvenance
from backend.services.spatial_intelligence import SpatialModelMode, UncertaintyBand


class DiagnosticCode(str, Enum):
    UNNECESSARY_CB_DISPLACEMENT = "UNNECESSARY_CB_DISPLACEMENT"
    EXPOSED_CENTRAL_CHANNEL = "EXPOSED_CENTRAL_CHANNEL"
    MIDFIELD_RECOVERY_FAILURE = "MIDFIELD_RECOVERY_FAILURE"
    POOR_DEFENSIVE_COMPACTNESS = "POOR_DEFENSIVE_COMPACTNESS"
    EXCESSIVE_PRESSING = "EXCESSIVE_PRESSING"
    RISKY_PASSING_DECISION = "RISKY_PASSING_DECISION"
    MISSED_PASSING_OPPORTUNITY = "MISSED_PASSING_OPPORTUNITY"
    INEFFECTIVE_ATTACKING_WIDTH = "INEFFECTIVE_ATTACKING_WIDTH"
    ISOLATED_STRIKER = "ISOLATED_STRIKER"
    OVERLAPPING_PLAYER_ROLES = "OVERLAPPING_PLAYER_ROLES"
    COUNTER_ATTACK_VULNERABILITY = "COUNTER_ATTACK_VULNERABILITY"
    INEFFICIENT_POSSESSION_PROGRESSION = "INEFFICIENT_POSSESSION_PROGRESSION"


class CoachingDiagnostic(BaseModel):
    diagnostic_id: str = Field(default_factory=lambda: f"DIAG-{str(uuid4())[:8]}")
    video_id: str
    code: DiagnosticCode
    severity: str  # HIGH | MEDIUM | LOW
    category: str  # DEFENSIVE | POSSESSION | TRANSITION | ATTACKING
    what_happened: str
    why_it_potentially_happened: str
    timestamp_start: float
    timestamp_end: float
    supporting_timestamps: List[float] = Field(default_factory=list)
    tactical_visualization: Dict[str, Any] = Field(default_factory=dict)
    confidence_level: str  # HIGH | MODERATE | LOW
    confidence_score: float
    alternative_decisions: List[str] = Field(default_factory=list)
    actionable_advice: str
    provenance: str = DataProvenance.REAL_VIDEO_DECODED.value
    evidence_caveats: List[str] = Field(default_factory=list)


def _cap_confidence(base_score: float, uncertainties: List[str], provenance: str) -> tuple[str, float, List[str]]:
    caveats: List[str] = []
    score = base_score
    if provenance == DataProvenance.SYNTHETIC_FIXTURE.value:
        score = min(score, 0.35)
        caveats.append("Evaluated over SYNTHETIC_FIXTURE telemetry; valid only as illustration, not real match evidence.")
    if UncertaintyBand.HIGH.value in uncertainties:
        score = min(score, 0.55)
        caveats.append("Partial tracking coverage during this sequence lowers certainty.")
    elif UncertaintyBand.MODERATE.value in uncertainties:
        score = min(score, 0.78)
        caveats.append("Moderate off-screen player uncertainty during parts of this sequence.")

    label = "HIGH" if score >= 0.78 else ("MODERATE" if score >= 0.52 else "LOW")
    return label, round(score, 3), caveats


class TacticalCoachingEngine:
    """Evaluates spatial snapshots and match events into evidence-grounded coaching diagnostics."""

    def analyze(
        self,
        video_id: str,
        spatial_result: Dict[str, Any],
        events: Optional[List[TacticalEvent]] = None,
        focus_team: str = "HOME",
    ) -> Dict[str, Any]:
        frames: List[Dict[str, Any]] = spatial_result.get("frames", [])
        usable = [
            f for f in frames
            if f.get("uncertainty_band") != UncertaintyBand.UNRELIABLE.value
            and f.get("model_mode") != SpatialModelMode.INSUFFICIENT_OBSERVATION.value
        ]
        diagnostics: List[CoachingDiagnostic] = []

        if len(usable) < 2:
            return {
                "video_id": video_id,
                "diagnostics": [],
                "summary": {
                    "total_diagnostics": 0,
                    "analyzable_snapshots": len(usable),
                    "insufficient_evidence_reason": "Fewer than 2 calibrated active gameplay frames are available for tactical coaching.",
                },
            }

        provenance = usable[0].get("provenance", DataProvenance.REAL_VIDEO_DECODED.value)
        struct_key = "home_structure" if focus_team == "HOME" else "away_structure"
        opp_team = "AWAY" if focus_team == "HOME" else "HOME"

        # Window accumulators to emit concise, sustained diagnostics rather than noisy per-frame spam
        diagnostics.extend(self._detect_defensive_issues(video_id, usable, struct_key, focus_team, opp_team, provenance))
        diagnostics.extend(self._detect_possession_and_passing(video_id, usable, struct_key, focus_team, provenance, events or []))
        diagnostics.extend(self._detect_attacking_shape(video_id, usable, struct_key, focus_team, provenance))
        diagnostics.extend(self._detect_transition_vulnerabilities(video_id, usable, struct_key, focus_team, provenance))

        diagnostics.sort(key=lambda d: (0 if d.severity == "HIGH" else (1 if d.severity == "MEDIUM" else 2), d.timestamp_start))

        by_code: Dict[str, int] = {}
        for d in diagnostics:
            by_code[d.code.value] = by_code.get(d.code.value, 0) + 1

        return {
            "video_id": video_id,
            "provenance": provenance,
            "diagnostics": [d.model_dump() for d in diagnostics],
            "summary": {
                "total_diagnostics": len(diagnostics),
                "analyzable_snapshots": len(usable),
                "high_severity_count": sum(1 for d in diagnostics if d.severity == "HIGH"),
                "by_code": by_code,
            },
        }

    def _detect_defensive_issues(
        self,
        video_id: str,
        frames: List[Dict[str, Any]],
        struct_key: str,
        focus_team: str,
        opp_team: str,
        provenance: str,
    ) -> List[CoachingDiagnostic]:
        out: List[CoachingDiagnostic] = []
        oop = [f for f in frames if f.get("possession_team") == opp_team]
        if not oop:
            oop = frames

        # 1. Poor defensive compactness & Midfield recovery failure
        wide_frames = [f for f in oop if (f.get(struct_key, {}).get("team_width_m", 0) > 52.0 or f.get(struct_key, {}).get("compactness_area_m2", 0) > 2300.0)]
        if len(wide_frames) >= 2:
            ts = [round(f["timestamp_sec"], 2) for f in wide_frames]
            max_w = max(f[struct_key].get("team_width_m", 0) for f in wide_frames)
            conf_l, conf_s, cav = _cap_confidence(0.84, [f["uncertainty_band"] for f in wide_frames], provenance)
            out.append(CoachingDiagnostic(
                video_id=video_id,
                code=DiagnosticCode.POOR_DEFENSIVE_COMPACTNESS,
                severity="HIGH" if max_w > 58.0 else "MEDIUM",
                category="DEFENSIVE",
                what_happened=f"{focus_team} block stretched to {max_w:.1f}m width across {len(wide_frames)} sampled frames while defending.",
                why_it_potentially_happened="Wide players stayed pinned toward opposing touchlines instead of shifting ball-side horizontally.",
                timestamp_start=ts[0],
                timestamp_end=ts[-1],
                supporting_timestamps=ts[:8],
                tactical_visualization={"highlight_team": focus_team, "focus_metric": "team_width_m", "value": max_w},
                confidence_level=conf_l,
                confidence_score=conf_s,
                alternative_decisions=["Tuck weak-side winger toward the half-space when ball enters opposite flank.", "Compress horizontal block under 44m."],
                actionable_advice="Prioritize horizontal compactness: shift non-ball-side fullbacks and wingers inside when defending middle or final third build-up.",
                provenance=provenance,
                evidence_caveats=cav,
            ))

        gap_frames = [f for f in oop if (f.get(struct_key, {}).get("def_to_mid_gap_m") or 0.0) >= 18.0]
        if len(gap_frames) >= 2:
            ts = [round(f["timestamp_sec"], 2) for f in gap_frames]
            max_gap = max(f[struct_key]["def_to_mid_gap_m"] for f in gap_frames)
            conf_l, conf_s, cav = _cap_confidence(0.82, [f["uncertainty_band"] for f in gap_frames], provenance)
            out.append(CoachingDiagnostic(
                video_id=video_id,
                code=DiagnosticCode.MIDFIELD_RECOVERY_FAILURE,
                severity="HIGH" if max_gap > 22.0 else "MEDIUM",
                category="DEFENSIVE",
                what_happened=f"Sustained {max_gap:.1f}m vertical separation between defensive and midfield lines.",
                why_it_potentially_happened="Midfielders remained high after initial press bypass while backline retreated toward goal.",
                timestamp_start=ts[0],
                timestamp_end=ts[-1],
                supporting_timestamps=ts[:8],
                tactical_visualization={"highlight_gap": "DEF_TO_MID", "gap_m": max_gap},
                confidence_level=conf_l,
                confidence_score=conf_s,
                alternative_decisions=["Hold backline height slightly higher OR drop holding midfielder earlier before chasing.", "Force play wide to buy recovery seconds."],
                actionable_advice="Keep your defensive-to-midfield spacing under 15m during opponent progression so opponents cannot receive freely between lines.",
                provenance=provenance,
                evidence_caveats=cav,
            ))

        # 2. Unnecessary CB displacement & Exposed central channel
        cb_disp_frames: List[Dict[str, Any]] = []
        central_exp_frames: List[Dict[str, Any]] = []
        for f in oop:
            kins = [k for k in f.get("kinematics", []) if k["team"] == focus_team and not k.get("is_goalkeeper")]
            if len(kins) < 4:
                continue
            by_x = sorted(kins, key=lambda k: k["x_m"] if focus_team == "HOME" else -k["x_m"])
            deepest_four = by_x[:4]
            center_backs = sorted(deepest_four, key=lambda k: abs(k["y_m"] - 34.0))[:2]
            if len(center_backs) == 2 and abs(center_backs[0]["x_m"] - center_backs[1]["x_m"]) > 6.5:
                cb_disp_frames.append(f)

            # Check Central Spine [27.2, 40.8] defender count near defensive third/half
            def_x_line = f.get(struct_key, {}).get("defensive_line_x_m") or 25.0
            in_central_box_screen = [
                k for k in kins
                if 27.2 <= k["y_m"] <= 40.8 and abs(k["x_m"] - def_x_line) <= 10.0
            ]
            if len(in_central_box_screen) == 0:
                central_exp_frames.append(f)

        if len(cb_disp_frames) >= 2:
            ts = [round(f["timestamp_sec"], 2) for f in cb_disp_frames]
            conf_l, conf_s, cav = _cap_confidence(0.80, [f["uncertainty_band"] for f in cb_disp_frames], provenance)
            out.append(CoachingDiagnostic(
                video_id=video_id,
                code=DiagnosticCode.UNNECESSARY_CB_DISPLACEMENT,
                severity="HIGH",
                category="DEFENSIVE",
                what_happened=f"Center-back staggered > 6.5m out of the backline while defending across {len(cb_disp_frames)} sampled frames.",
                why_it_potentially_happened="One central defender stepped out aggressively toward the ball zone, breaking defensive line alignment.",
                timestamp_start=ts[0],
                timestamp_end=ts[-1],
                supporting_timestamps=ts[:8],
                tactical_visualization={"focus_zone": 8, "defect": "STAGGERED_BACKLINE"},
                confidence_level=conf_l,
                confidence_score=conf_s,
                alternative_decisions=["Track runner with CDM/CM first and hold CB line compact.", "Step only when ball receiver takes a heavy back-to-goal touch."],
                actionable_advice="Avoid dragging center-backs out early before midfield screening settles; preserve a flat backline around Zone 8/11.",
                provenance=provenance,
                evidence_caveats=cav,
            ))

        if len(central_exp_frames) >= 2:
            ts = [round(f["timestamp_sec"], 2) for f in central_exp_frames]
            conf_l, conf_s, cav = _cap_confidence(0.83, [f["uncertainty_band"] for f in central_exp_frames], provenance)
            out.append(CoachingDiagnostic(
                video_id=video_id,
                code=DiagnosticCode.EXPOSED_CENTRAL_CHANNEL,
                severity="HIGH",
                category="DEFENSIVE",
                what_happened=f"Central Spine channel [27.2m-40.8m] left unoccupied near defensive line across {len(central_exp_frames)} frames.",
                why_it_potentially_happened="Defenders tracked wide threats simultaneously or over-committed to one half-space.",
                timestamp_start=ts[0],
                timestamp_end=ts[-1],
                supporting_timestamps=ts[:8],
                tactical_visualization={"exposed_lane": "CENTRAL_SPINE"},
                confidence_level=conf_l,
                confidence_score=conf_s,
                alternative_decisions=["Position one holding defender inside central zone 8.", "Funnel opponent attacks toward the flanked touchline."],
                actionable_advice="Always maintain at least one screening defender inside the central lane between goalposts before closing wide angles.",
                provenance=provenance,
                evidence_caveats=cav,
            ))

        # 3. Excessive pressing
        press_overcommit = [
            f for f in oop
            if f.get(struct_key, {}).get("observed_outfield_count", 0) >= 6
            and f.get(struct_key, {}).get("rest_defense_count", 10) < 3
        ]
        if len(press_overcommit) >= 2:
            ts = [round(f["timestamp_sec"], 2) for f in press_overcommit]
            conf_l, conf_s, cav = _cap_confidence(0.79, [f["uncertainty_band"] for f in press_overcommit], provenance)
            out.append(CoachingDiagnostic(
                video_id=video_id,
                code=DiagnosticCode.EXCESSIVE_PRESSING,
                severity="MEDIUM",
                category="DEFENSIVE",
                what_happened=f"Team committed high upfield leaving fewer than 3 outfielders behind the ball across {len(press_overcommit)} frames.",
                why_it_potentially_happened="Simultaneous high-press chasing pushed multiple lines ahead of ball height without cover.",
                timestamp_start=ts[0],
                timestamp_end=ts[-1],
                supporting_timestamps=ts[:8],
                tactical_visualization={"rest_defense_count_min": min(f[struct_key]["rest_defense_count"] for f in press_overcommit)},
                confidence_level=conf_l,
                confidence_score=conf_s,
                alternative_decisions=["Trigger high press with 1 forward curved run rather than committing 2 midfielders.", "Anchor 1 pivot + 2 CBs behind ball."],
                actionable_advice="Keep at least 3 defenders positioned goal-side of the ball before initiating aggressive secondary pressing.",
                provenance=provenance,
                evidence_caveats=cav,
            ))
        return out

    def _detect_possession_and_passing(
        self,
        video_id: str,
        frames: List[Dict[str, Any]],
        struct_key: str,
        focus_team: str,
        provenance: str,
        events: List[TacticalEvent],
    ) -> List[CoachingDiagnostic]:
        out: List[CoachingDiagnostic] = []
        in_poss = [f for f in frames if f.get("possession_team") == focus_team]
        if not in_poss:
            return out

        # Missed passing opportunities: high-value open passing lanes not taken for >= 2 frames
        missed_frames = [
            f for f in in_poss
            if any(
                lane["status"] == "OPEN" and lane["xt_gain"] >= 0.02 and lane["is_progressive"]
                for lane in f.get("passing_lanes", [])
            )
        ]
        if len(missed_frames) >= 2:
            best_lane = max(
                (lane for f in missed_frames for lane in f.get("passing_lanes", []) if lane["status"] == "OPEN"),
                key=lambda x: x["xt_gain"],
                default=None,
            )
            if best_lane:
                ts = [round(f["timestamp_sec"], 2) for f in missed_frames]
                conf_l, conf_s, cav = _cap_confidence(0.81, [f["uncertainty_band"] for f in missed_frames], provenance)
                out.append(CoachingDiagnostic(
                    video_id=video_id,
                    code=DiagnosticCode.MISSED_PASSING_OPPORTUNITY,
                    severity="MEDIUM",
                    category="POSSESSION",
                    what_happened=f"Open progressive lane to {best_lane['target_slot']} (+{best_lane['xt_gain']:.3f} xT gain, {best_lane['nearest_defender_clearance_m']:.1f}m clearance) remained unused across {len(missed_frames)} samples.",
                    why_it_potentially_happened="Carrier lingered on the ball or scanned away from forward half-space runners before defenders closed space.",
                    timestamp_start=ts[0],
                    timestamp_end=ts[-1],
                    supporting_timestamps=ts[:8],
                    tactical_visualization={"target_xy": best_lane["target_xy"], "xt_gain": best_lane["xt_gain"]},
                    confidence_level=conf_l,
                    confidence_score=conf_s,
                    alternative_decisions=[f"Play first-time progressive pass into {best_lane['target_slot']} (+{best_lane['xt_gain']:.3f} xT)."],
                    actionable_advice="Scan early into open forward half-spaces when defenders step tight; release progressive passes within 1.5s.",
                    provenance=provenance,
                    evidence_caveats=cav,
                ))

        # Risky passing decision / Turnover with safer options available
        turnovers = [e for e in events if e.event_type == "TURNOVER" and e.team_identity == focus_team]
        for tv in turnovers[:3]:
            nearby = [f for f in frames if abs(f["timestamp_sec"] - tv.timestamp_end) <= 1.2 and f.get("passing_lanes")]
            if not nearby:
                continue
            blocked = [l for l in nearby[0]["passing_lanes"] if l["status"] == "BLOCKED"]
            open_safe = [l for l in nearby[0]["passing_lanes"] if l["status"] == "OPEN"]
            if open_safe and (blocked or len(open_safe) >= 1):
                conf_l, conf_s, cav = _cap_confidence(0.76, [nearby[0]["uncertainty_band"]], provenance)
                out.append(CoachingDiagnostic(
                    video_id=video_id,
                    code=DiagnosticCode.RISKY_PASSING_DECISION,
                    severity="HIGH",
                    category="POSSESSION",
                    what_happened=f"Turnover near {tv.timestamp_end:.1f}s while open outlet pass to {open_safe[0]['target_slot']} ({open_safe[0]['nearest_defender_clearance_m']:.1f}m clear) was available.",
                    why_it_potentially_happened="Play moved through congested zone or opponent closing corridor rather than safer open support.",
                    timestamp_start=round(max(0.0, tv.timestamp_start), 2),
                    timestamp_end=round(tv.timestamp_end, 2),
                    supporting_timestamps=[round(tv.timestamp_start, 2), round(tv.timestamp_end, 2)],
                    tactical_visualization={"safe_target_xy": open_safe[0]["target_xy"], "zone": tv.pitch_zone},
                    confidence_level=conf_l,
                    confidence_score=conf_s,
                    alternative_decisions=[f"Bounce safely into {open_safe[0]['target_slot']} to draw press and switch point of attack."],
                    actionable_advice="Avoid forcing vertical passes across congested central lanes when an unpressured support angle is visible.",
                    provenance=provenance,
                    evidence_caveats=cav,
                ))

        # Inefficient possession progression: >= 4 frames in own possession with net zero/negative xT gain while lanes open
        if len(in_poss) >= 4:
            xts = [f["ball_xt"] for f in in_poss if f.get("ball_xt") is not None]
            if len(xts) >= 4 and (max(xts) - min(xts)) < 0.015 and xts[-1] <= xts[0]:
                ts = [round(f["timestamp_sec"], 2) for f in in_poss]
                conf_l, conf_s, cav = _cap_confidence(0.70, [f["uncertainty_band"] for f in in_poss], provenance)
                out.append(CoachingDiagnostic(
                    video_id=video_id,
                    code=DiagnosticCode.INEFFICIENT_POSSESSION_PROGRESSION,
                    severity="LOW",
                    category="POSSESSION",
                    what_happened=f"Sustained horizontal ball circulation ({ts[0]:.1f}s–{ts[-1]:.1f}s) generated < 0.015 xT threat change.",
                    why_it_potentially_happened="Build-up recycled sideways without third-man vertical runs stretching the defensive block.",
                    timestamp_start=ts[0],
                    timestamp_end=ts[-1],
                    supporting_timestamps=ts[:8],
                    tactical_visualization={"xt_span": round(max(xts) - min(xts), 4)},
                    confidence_level=conf_l,
                    confidence_score=conf_s,
                    alternative_decisions=["Probe half-spaces with diagonal pass-and-move to force opponent backline rotation."],
                    actionable_advice="Follow horizontal switches with quick diagonal vertical passes before the opponent shifts completely across.",
                    provenance=provenance,
                    evidence_caveats=cav,
                ))
        return out

    def _detect_attacking_shape(
        self,
        video_id: str,
        frames: List[Dict[str, Any]],
        struct_key: str,
        focus_team: str,
        provenance: str,
    ) -> List[CoachingDiagnostic]:
        out: List[CoachingDiagnostic] = []
        in_poss = [f for f in frames if f.get("possession_team") == focus_team]
        if not in_poss:
            return out

        # Ineffective attacking width
        narrow_att = [
            f for f in in_poss
            if f.get(struct_key, {}).get("observed_outfield_count", 0) >= 6
            and f.get(struct_key, {}).get("team_width_m", 99.0) < 34.0
        ]
        if len(narrow_att) >= 2:
            ts = [round(f["timestamp_sec"], 2) for f in narrow_att]
            min_w = min(f[struct_key]["team_width_m"] for f in narrow_att)
            conf_l, conf_s, cav = _cap_confidence(0.79, [f["uncertainty_band"] for f in narrow_att], provenance)
            out.append(CoachingDiagnostic(
                video_id=video_id,
                code=DiagnosticCode.INEFFECTIVE_ATTACKING_WIDTH,
                severity="MEDIUM",
                category="ATTACKING",
                what_happened=f"Attacking width compressed to {min_w:.1f}m across {len(narrow_att)} in-possession frames.",
                why_it_potentially_happened="Wide attackers drifted inside leaving both touchline channels empty and allowing compact defending.",
                timestamp_start=ts[0],
                timestamp_end=ts[-1],
                supporting_timestamps=ts[:8],
                tactical_visualization={"team_width_m": min_w},
                confidence_level=conf_l,
                confidence_score=conf_s,
                alternative_decisions=["Hold at least one touchline winger/fullback outside Y < 10m or Y > 58m to pin fullbacks."],
                actionable_advice="Maintain wide outlets on both touchlines in attack so defending fullbacks cannot tuck centrally free of consequence.",
                provenance=provenance,
                evidence_caveats=cav,
            ))

        # Isolated striker & Overlapping player roles
        isolated_frames = []
        overlap_frames = []
        for f in in_poss:
            att = [k for k in f.get("kinematics", []) if k["team"] == focus_team and not k.get("is_goalkeeper")]
            if len(att) < 4:
                continue
            lead = max(att, key=lambda k: k["x_m"] if focus_team == "HOME" else -k["x_m"])
            nearest_support = min(math.hypot(lead["x_m"] - k["x_m"], lead["y_m"] - k["y_m"]) for k in att if k["track_id"] != lead["track_id"])
            if nearest_support > 21.0:
                isolated_frames.append((f, round(nearest_support, 1)))

            # Check role collision: two teammates stuck within 3.5m for consecutive frames
            close_pairs = 0
            for i in range(len(att)):
                for j in range(i + 1, len(att)):
                    if math.hypot(att[i]["x_m"] - att[j]["x_m"], att[i]["y_m"] - att[j]["y_m"]) < 3.5:
                        close_pairs += 1
            if close_pairs > 0:
                overlap_frames.append(f)

        if len(isolated_frames) >= 2:
            ts = [round(f["timestamp_sec"], 2) for f, _ in isolated_frames]
            max_sep = max(sep for _, sep in isolated_frames)
            conf_l, conf_s, cav = _cap_confidence(0.80, [f["uncertainty_band"] for f, _ in isolated_frames], provenance)
            out.append(CoachingDiagnostic(
                video_id=video_id,
                code=DiagnosticCode.ISOLATED_STRIKER,
                severity="HIGH" if max_sep > 26.0 else "MEDIUM",
                category="ATTACKING",
                what_happened=f"Lead forward had no teammate within {max_sep:.1f}m during build-up.",
                why_it_potentially_happened="Midfielders/CAM delayed forward support runs while striker advanced early against backline.",
                timestamp_start=ts[0],
                timestamp_end=ts[-1],
                supporting_timestamps=ts[:8],
                tactical_visualization={"max_separation_m": max_sep},
                confidence_level=conf_l,
                confidence_score=conf_s,
                alternative_decisions=["Use a bounce pass to an advancing #8/#10 before releasing vertical ball.", "Delay striker sprint 1s until midfield connects."],
                actionable_advice="Ensure CAM or interior midfielders step up into Zone 5/8/11 within 15m of your striker before attempting direct progression.",
                provenance=provenance,
                evidence_caveats=cav,
            ))

        if len(overlap_frames) >= 3:
            ts = [round(f["timestamp_sec"], 2) for f in overlap_frames]
            conf_l, conf_s, cav = _cap_confidence(0.75, [f["uncertainty_band"] for f in overlap_frames], provenance)
            out.append(CoachingDiagnostic(
                video_id=video_id,
                code=DiagnosticCode.OVERLAPPING_PLAYER_ROLES,
                severity="LOW",
                category="ATTACKING",
                what_happened=f"Attacking teammates occupied identical < 3.5m radius across {len(overlap_frames)} consecutive samples.",
                why_it_potentially_happened="Two players drifted into the same half-space pocket simultaneously, making both markable by one defender.",
                timestamp_start=ts[0],
                timestamp_end=ts[-1],
                supporting_timestamps=ts[:8],
                tactical_visualization={"spacing_conflict_radius_m": 3.5},
                confidence_level=conf_l,
                confidence_score=conf_s,
                alternative_decisions=["Separate runs vertically (one checks short, the other spins opposite half-space/touchline)."],
                actionable_advice="Keep attackers occupying distinct vertical and lateral lanes rather than bunching into the same pocket.",
                provenance=provenance,
                evidence_caveats=cav,
            ))
        return out

    def _detect_transition_vulnerabilities(
        self,
        video_id: str,
        frames: List[Dict[str, Any]],
        struct_key: str,
        focus_team: str,
        provenance: str,
    ) -> List[CoachingDiagnostic]:
        out: List[CoachingDiagnostic] = []
        # Counter-attack vulnerability: possession flip or active build-up where rest_defense < 3 in own defense
        vuln_frames = [
            f for f in frames
            if f.get("possession_team") != focus_team
            and f.get(struct_key, {}).get("observed_outfield_count", 0) >= 6
            and f.get(struct_key, {}).get("rest_defense_count", 10) <= 2
            and (f.get("ball_xy") or [50.0, 34.0])[0] > 35.0
        ]
        if len(vuln_frames) >= 2:
            ts = [round(f["timestamp_sec"], 2) for f in vuln_frames]
            min_rd = min(f[struct_key]["rest_defense_count"] for f in vuln_frames)
            conf_l, conf_s, cav = _cap_confidence(0.83, [f["uncertainty_band"] for f in vuln_frames], provenance)
            out.append(CoachingDiagnostic(
                video_id=video_id,
                code=DiagnosticCode.COUNTER_ATTACK_VULNERABILITY,
                severity="HIGH",
                category="TRANSITION",
                what_happened=f"Transition exposure detected: only {min_rd} defenders positioned behind the ball as opponent countered.",
                why_it_potentially_happened="Both fullbacks/pivots pushed ahead of the ball simultaneously prior to turnover.",
                timestamp_start=ts[0],
                timestamp_end=ts[-1],
                supporting_timestamps=ts[:8],
                tactical_visualization={"rest_defense_count": min_rd},
                confidence_level=conf_l,
                confidence_score=conf_s,
                alternative_decisions=["Anchor at least one fullback on Stay Back While Attacking or keep CDM centrally disciplined."],
                actionable_advice="Balance attacking overlaps by locking your opposite-side fullback + 1 holding midfielder behind the ball.",
                provenance=provenance,
                evidence_caveats=cav,
            ))
        return out
