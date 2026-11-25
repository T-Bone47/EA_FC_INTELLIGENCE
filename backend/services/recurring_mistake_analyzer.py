"""Phase 40D: Longitudinal Recurring Mistake Intelligence Engine.

Aggregates observed tactical mistakes across multiple user matches, normalized strictly
by relevant opportunities (never raw misleading frame counts), with multi-hypothesis
root-cause distinction (Gamer Decision / Formation / Instructions / Squad Structure /
Role Suitability / Player Capability / Opponent Behaviour / Observation Uncertainty).

Strictly refuses to infer stress, emotional tilt, controller button inputs, or scripting.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.domain.phase40_models import (
    EvidenceClipRef,
    MatchIntelligenceRecord,
    RecurringMistakePattern,
    RootCauseDimension,
    RootCauseHypothesis,
)


_MISTAKE_CATALOG: Dict[str, Dict[str, Any]] = {
    "UNNECESSARY_CB_DISPLACEMENT": {
        "title": "Centre-Back Displacement & Central Channel Opening",
        "definition": "Centre-back steps >= 6m beyond the defensive line while defending centrally without midfield cover.",
        "required_evidence": "Calibrated backline coordinates + active out-of-possession frames (coverage >= 60%).",
        "contexts": ["OUT_OF_POSSESSION", "CENTRAL_DEFENSE"],
        "opp_key": "transition_opportunities",
        "causes": [
            (RootCauseDimension.GAMER_DECISION, 0.55, "User-controlled CB stepping out early rather than screening with CDM first."),
            (RootCauseDimension.TACTICAL_INSTRUCTIONS, 0.25, "Aggressive step-up or high defensive approach without cover."),
            (RootCauseDimension.PLAYER_ROLE_SUITABILITY, 0.20, "Stopper role vs balanced Defender mismatch."),
        ],
        "interventions": ["Delay manual CB engagement until CDM screens Zone 8.", "Switch CB role to Defender (Balanced)."],
    },
    "EXPOSED_CENTRAL_CHANNEL": {
        "title": "Exposed Central Channel / Counter-Attack Seam",
        "definition": "Zone 8 central spine contains 0 home midfielders during defensive transition while attacker advances.",
        "required_evidence": "Outfield zone occupancy + transition frames with reliable calibration.",
        "contexts": ["DEFENSIVE_TRANSITION", "CENTRAL_MIDFIELD"],
        "opp_key": "transition_opportunities",
        "causes": [
            (RootCauseDimension.FORMATION, 0.42, "Lone pivot or pushing CMs leaves central pocket unscreened."),
            (RootCauseDimension.TACTICAL_INSTRUCTIONS, 0.35, "Both CMs/CDMs pushing up simultaneously in build-up."),
            (RootCauseDimension.PLAYER_CAPABILITY, 0.23, "Insufficient recovery pace / defensive awareness in central pivot."),
        ],
        "interventions": ["Lock at least one pivot to Holding (Defend).", "Consider 4-2-3-1 double pivot."],
    },
    "COUNTER_ATTACK_VULNERABILITY": {
        "title": "Rest-Defense Transition Exposure",
        "definition": "Fewer than 3 defenders positioned behind ball at possession turnover against opponent attackers.",
        "required_evidence": "Possession flip frames with fullback/midfield recovery coordinates.",
        "contexts": ["POSSESSION_TURNOVER", "REST_DEFENSE"],
        "opp_key": "transition_opportunities",
        "causes": [
            (RootCauseDimension.TACTICAL_INSTRUCTIONS, 0.45, "Both fullbacks overlapping simultaneously (Attacking Wingback)."),
            (RootCauseDimension.GAMER_DECISION, 0.35, "Forcing high-risk dribbling/passes before rest defense sets."),
            (RootCauseDimension.FORMATION, 0.20, "Narrow midfield shape vulnerable to diagonal counter lanes."),
        ],
        "interventions": ["Set weak-side Fullback to Defend focus.", "Avoid forcing central passes when only 2 rest defenders stay behind ball."],
    },
    "RISKY_PASSING_DECISION": {
        "title": "Unsafe Central Passing & Contested Corridor Turnovers",
        "definition": "Attempted or targeted pass into congested central lanes (< 2.5m defender clearance) despite open flank/pivot.",
        "required_evidence": "Passing lane geometry + pre-pass ball carrier positioning.",
        "contexts": ["BUILD_UP", "MIDFIELD_PROGRESSION"],
        "opp_key": "central_pass_opportunities",
        "causes": [
            (RootCauseDimension.GAMER_DECISION, 0.60, "Choosing congested Zone 8 corridor over wider half-space outlet."),
            (RootCauseDimension.OPPONENT_BEHAVIOUR, 0.20, "Opponent compact mid-block baiting interior lane traps."),
            (RootCauseDimension.PLAYER_CAPABILITY, 0.20, "Midfielder vision/composure pressed cleanly before release."),
        ],
        "interventions": ["Check touchline winger / deep pivot recycle before central vertical pass."],
    },
    "POOR_DEFENSIVE_COMPACTNESS": {
        "title": "Defensive Block Stretching & Wide Fragmentation",
        "definition": "Out-of-possession block width > 52m or convex hull > 2300 m2 allowing inside pockets to open.",
        "required_evidence": "Outfield coordinates out of possession across >= 2 continuous snapshots.",
        "contexts": ["OUT_OF_POSSESSION", "TEAM_SHAPE"],
        "opp_key": "transition_opportunities",
        "causes": [
            (RootCauseDimension.TACTICAL_INSTRUCTIONS, 0.45, "Defensive width/line settings overly stretched vs opponent attack."),
            (RootCauseDimension.GAMER_DECISION, 0.35, "Dragging weak-side midfielders toward ball side prematurely."),
            (RootCauseDimension.OPPONENT_BEHAVIOUR, 0.20, "Rapid opponent switches forcing delayed lateral shifts."),
        ],
        "interventions": ["Compact out-of-possession shape to 4-4-2 or Balanced 4-2-3-1 depth <= 60."],
    },
    "ISOLATED_STRIKER": {
        "title": "Isolated Lead Forward / Lack of Vertical Support",
        "definition": "Lead forward separated > 24m from nearest teammate without diagonal support channel.",
        "required_evidence": "Attacking phase positions with >= 60% coverage.",
        "contexts": ["ATTACKING_BUILD_UP"],
        "opp_key": "central_pass_opportunities",
        "causes": [
            (RootCauseDimension.FORMATION, 0.45, "Missing CAM or advanced CM connector beneath lone ST."),
            (RootCauseDimension.PLAYER_ROLE_SUITABILITY, 0.35, "Both interior mids held deep; forward running early."),
            (RootCauseDimension.TACTICAL_INSTRUCTIONS, 0.20, "Direct build-up pushing striker away from midfield tempo."),
        ],
        "interventions": ["Assign CAM Shadow Striker or CM Playmaker (Attack) behind ST."],
    },
    "MIDFIELD_RECOVERY_FAILURE": {
        "title": "Delayed Midfield Transition Recovery",
        "definition": "Vertical defense-to-midfield gap exceeds 18m during opponent progression.",
        "required_evidence": "Defensive & midfield centroid coordinates across transition frames.",
        "contexts": ["DEFENSIVE_TRANSITION"],
        "opp_key": "transition_opportunities",
        "causes": [
            (RootCauseDimension.TACTICAL_INSTRUCTIONS, 0.40, "Forward-oriented CM instructions slowing defensive sprint triggers."),
            (RootCauseDimension.PLAYER_CAPABILITY, 0.35, "Central midfield stamina/acceleration drop late in match."),
            (RootCauseDimension.GAMER_DECISION, 0.25, "High manual pressing commitment failing cleanly at first wave."),
        ],
        "interventions": ["Sub fresh Relentless/high-stamina pivot at 65'+; compress line gap below 15m."],
    },
    "EXCESSIVE_PRESSING": {
        "title": "Overcommitted Multi-Player Pressing",
        "definition": "3+ pressers sprint ahead of ball without rear cover intact.",
        "required_evidence": "Speed & positional line geometry out of possession.",
        "contexts": ["PRESSING"],
        "opp_key": "transition_opportunities",
        "causes": [
            (RootCauseDimension.GAMER_DECISION, 0.55, "Second-man press + manual chase pulling both midfielders out."),
            (RootCauseDimension.TACTICAL_INSTRUCTIONS, 0.30, "Aggressive high depth/press trigger active when stamina drains."),
            (RootCauseDimension.OBSERVATION_UNCERTAINTY, 0.15, "Partial off-screen backline visibility possible."),
        ],
        "interventions": ["Use single-man contain/jockey rather than dragging second pivot ahead of ball."],
    },
    "INEFFECTIVE_ATTACKING_WIDTH": {
        "title": "Narrow Congestion / Underutilized Flanks",
        "definition": "Attacking build-up width < 28m leaving flank channels unstretched.",
        "required_evidence": "In-possession attacking coordinates.",
        "contexts": ["ATTACKING_PROGRESSION"],
        "opp_key": "central_pass_opportunities",
        "causes": [
            (RootCauseDimension.PLAYER_ROLE_SUITABILITY, 0.45, "Dual Inside Forwards tucking in simultaneously with narrow fullbacks."),
            (RootCauseDimension.FORMATION, 0.35, "Narrow diamond lacking touchline outlets."),
            (RootCauseDimension.GAMER_DECISION, 0.20, "Ignoring open far-side switch targets."),
        ],
        "interventions": ["Keep one side on Winger / Attacking Wingback to stretch compact opponent CBs."],
    },
    "OVERLAPPING_PLAYER_ROLES": {
        "title": "Adjacent Role Compression / Spatial Overlap",
        "definition": "Two teammates remain within 5m inside the same tactical pocket across attacking phases.",
        "required_evidence": "Inter-player pairwise proximity matrices.",
        "contexts": ["IN_POSSESSION"],
        "opp_key": "central_pass_opportunities",
        "causes": [
            (RootCauseDimension.PLAYER_ROLE_SUITABILITY, 0.60, "Conflicting adjacent FC IQ roles (e.g. dual Playmakers occupying half-space)."),
            (RootCauseDimension.SQUAD_STRUCTURE, 0.25, "Two similar profiles crowding central zone."),
            (RootCauseDimension.FORMATION, 0.15, "Narrow shape compression."),
        ],
        "interventions": ["Pair Inside Forward with overlapping Fullback, never dual interior Roam roles on same wing."],
    },
    "INEFFICIENT_POSSESSION_PROGRESSION": {
        "title": "Stalled Build-Up Without Expected Threat Gain",
        "definition": "Sustained possession sequences yielding zero progressive lane advancement despite open options.",
        "required_evidence": "Spatial passing lane & xT deltas.",
        "contexts": ["BUILD_UP"],
        "opp_key": "central_pass_opportunities",
        "causes": [
            (RootCauseDimension.GAMER_DECISION, 0.55, "Lateral circulation bypassing progressive half-space windows."),
            (RootCauseDimension.OPPONENT_BEHAVIOUR, 0.25, "Low opponent block compacting interior pockets."),
            (RootCauseDimension.TACTICAL_INSTRUCTIONS, 0.20, "Slow build-up restricting forward runner triggers."),
        ],
        "interventions": ["Trigger L1/LB creative runs or use balanced build-up when facing low blocks."],
    },
    "MISSED_PASSING_OPPORTUNITY": {
        "title": "Missed High-xT Progressive Outlet",
        "definition": "High-value open progressive lane (> 0.68 openness, +xT gain) ignored while holding/recycling.",
        "required_evidence": "Pre-action candidate passing lane geometry.",
        "contexts": ["IN_POSSESSION"],
        "opp_key": "central_pass_opportunities",
        "causes": [
            (RootCauseDimension.GAMER_DECISION, 0.65, "Tunnel-vision toward ball-side receiver missing weak-side run."),
            (RootCauseDimension.PLAYER_CAPABILITY, 0.20, "Limited passer angle/vision trait in tight turn."),
            (RootCauseDimension.OBSERVATION_UNCERTAINTY, 0.15, "Camera angle visibility constraint."),
        ],
        "interventions": ["Rehearse freeze-frame progressive scans in Training Academy exercises."],
    },
}


class RecurringMistakeAnalyzer:
    """Aggregates normalized recurring tactical mistakes across a gamer's match history."""

    def analyze(
        self,
        matches: List[MatchIntelligenceRecord],
        *,
        include_synthetic_preview: bool = False,
        diagnostic_filter: Optional[str] = None,
    ) -> List[RecurringMistakePattern]:
        eligible = [
            m for m in matches
            if include_synthetic_preview or m.provenance != "SYNTHETIC_FIXTURE"
        ]
        if not eligible:
            return []

        accum: Dict[str, Dict[str, Any]] = {}
        total_transition_opps = sum(max(1, int((m.feature_metrics or {}).get("transition_opportunities", 4))) for m in eligible)
        total_pass_opps = sum(max(1, int((m.feature_metrics or {}).get("central_pass_opportunities", 6))) for m in eligible)

        for m in eligible:
            for finding in (m.coaching_findings or []):
                code = str(finding.get("code", ""))
                if not code or (diagnostic_filter and code != diagnostic_filter):
                    continue
                bucket = accum.setdefault(
                    code,
                    {
                        "occurrences": 0,
                        "high_count": 0,
                        "clips": [],
                        "low_conf": 0,
                    },
                )
                bucket["occurrences"] += 1
                if finding.get("severity") == "HIGH":
                    bucket["high_count"] += 1
                if finding.get("confidence_level") == "LOW":
                    bucket["low_conf"] += 1
                t0 = float(finding.get("timestamp_start", 0.0))
                t1 = float(finding.get("timestamp_end", t0 + 2.0))
                deep = f"/research/gameplay-studio?video_id={m.video_id}&t={round(t0, 2)}&tab=RADAR_REPLAY" if m.video_id else ""
                bucket["clips"].append(
                    EvidenceClipRef(
                        match_id=m.match_id,
                        video_id=m.video_id,
                        timestamp_start=t0,
                        timestamp_end=t1,
                        title=f"{code.replace('_', ' ')} ({m.formation})",
                        diagnostic_code=code,
                        provenance=m.provenance,
                        confidence=str(finding.get("confidence_level", "MODERATE")),
                        deep_link=deep,
                    )
                )

        patterns: List[RecurringMistakePattern] = []
        for code, stats in accum.items():
            meta = _MISTAKE_CATALOG.get(code, {
                "title": code.replace("_", " ").title(),
                "definition": f"Observed tactical diagnostic {code}.",
                "required_evidence": "Calibrated spatial telemetry frames.",
                "contexts": ["GENERAL"],
                "opp_key": "transition_opportunities",
                "causes": [(RootCauseDimension.GAMER_DECISION, 0.5, "Decision hypothesis."), (RootCauseDimension.TACTICAL_INSTRUCTIONS, 0.5, "Tactical setup hypothesis.")],
                "interventions": ["Review video clip and adjust tactical structure before considering card changes."],
            })
            opp_total = total_transition_opps if meta["opp_key"] == "transition_opportunities" else total_pass_opps
            opp_total = max(stats["occurrences"], opp_total)
            rate = round(min(1.0, stats["occurrences"] / opp_total), 4)

            if stats["high_count"] >= 2 or rate >= 0.28:
                severity = "HIGH"
            elif stats["occurrences"] >= 2 or rate >= 0.14:
                severity = "MEDIUM"
            else:
                severity = "LOW"

            matches_with_err = len({c.match_id for c in stats["clips"]})
            if matches_with_err >= 2 and stats["low_conf"] == 0:
                conf = "HIGH"
            elif stats["occurrences"] >= 1 and stats["low_conf"] < stats["occurrences"]:
                conf = "MODERATE"
            else:
                conf = "LOW"

            hypotheses = [
                RootCauseHypothesis(
                    dimension=dim,
                    plausibility_score=round(score, 2),
                    epistemic_label="CORROBORATED_PATTERN" if matches_with_err >= 2 and i == 0 else "HYPOTHESIS",
                    rationale=rat,
                )
                for i, (dim, score, rat) in enumerate(meta["causes"])
            ]

            patterns.append(
                RecurringMistakePattern(
                    mistake_id=f"REC-{code}",
                    diagnostic_code=code,
                    title=meta["title"],
                    formal_definition=meta["definition"],
                    required_evidence=meta["required_evidence"],
                    applicable_contexts=meta["contexts"],
                    confidence_requirement="MODERATE",
                    total_occurrences=stats["occurrences"],
                    total_opportunities=opp_total,
                    normalized_rate=rate,
                    severity_estimate=severity,  # type: ignore[arg-type]
                    confidence_level=conf,  # type: ignore[arg-type]
                    supporting_clips=stats["clips"][:8],
                    root_cause_hypotheses=hypotheses,
                    suggested_interventions=meta["interventions"],
                )
            )

        patterns.sort(key=lambda p: (0 if p.severity_estimate == "HIGH" else (1 if p.severity_estimate == "MEDIUM" else 2), -p.normalized_rate))
        return patterns
