"""Phase 43C: Empirical Match Tactical Fingerprint Engine.

Computes phase-separated match metrics across all four football phases:
1. IN_POSSESSION
2. OUT_OF_POSSESSION
3. ATTACKING_TRANSITION
4. DEFENSIVE_TRANSITION

Preserves explicit distinction between nominal pre-match formation labels and
actual observed in-possession vs out-of-possession spatial shapes. Unsupported
metrics remain None (never fabricated). Compares intended tactical configuration
against observed match behavior when a TacticalConfigurationSnapshot is linked.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.domain.phase40_models import MatchIntelligenceRecord
from backend.domain.phase43_models import (
    EvidenceGrade,
    FingerprintMetricDetail,
    IntendedVsObservedDelta,
    PhaseMetricBlock,
    TacticalConfigurationSnapshot,
    TacticalFingerprint,
)
from backend.repositories.phase43_repository import Phase43Repository, get_phase43_repository


class TacticalFingerprintEngine:
    """Extracts uncertainty-bounded, phase-separated tactical fingerprints from verified matches."""

    def __init__(self, repo: Optional[Phase43Repository] = None) -> None:
        self.repo = repo or get_phase43_repository()

    def build_fingerprint(
        self,
        user_id: str,
        match: MatchIntelligenceRecord,
        *,
        snapshot: Optional[TacticalConfigurationSnapshot] = None,
        save: bool = True,
    ) -> TacticalFingerprint:
        fm = match.feature_metrics or {}
        tel = match.telemetry_summary or {}
        cov = float(match.tracking_coverage_pct or 0.0)
        cal_state = str(tel.get("calibration_state") or ("MODERATE" if cov >= 70.0 else "COARSE" if cov >= 40.0 else "INSUFFICIENT"))
        visible_players = tel.get("visible_outfield_players")
        if visible_players is None:
            visible_players = fm.get("visible_outfield_players")
        vis_int = int(visible_players) if isinstance(visible_players, (int, float)) else None

        team_compactness_abstained = False
        abstention_reason: Optional[str] = None
        if vis_int is not None and vis_int < 14:
            team_compactness_abstained = True
            abstention_reason = (
                f"ABSTAINED_VISIBLE_PLAYERS_BELOW_14: only {vis_int} outfield players visible; "
                "broadcast camera crops off-screen defenders, making team compactness/width invalid."
            )
        elif cal_state == "INSUFFICIENT" or cov < 35.0:
            team_compactness_abstained = True
            abstention_reason = f"ABSTAINED_INSUFFICIENT_COVERAGE_OR_CALIBRATION: coverage={cov:.1f}%, calibration={cal_state}."

        adequacy_ok = cov >= 35.0 and not team_compactness_abstained

        uncertainty_notes: List[str] = []
        unsupported: List[str] = []
        if not adequacy_ok and abstention_reason:
            uncertainty_notes.append(abstention_reason)
        if match.provenance == "SYNTHETIC_FIXTURE":
            uncertainty_notes.append("SYNTHETIC_FIXTURE source: permitted for pipeline/method demo only, never real tactical evidence.")

        obs_frames = int(tel.get("frames_analyzed") or fm.get("frames_analyzed") or 0)
        cov_ratio = round(max(0.0, min(1.0, cov / 100.0)), 3)
        conf_base = round(max(0.10, min(0.95, 0.25 + 0.65 * cov_ratio)), 3) if not team_compactness_abstained else round(min(0.30, cov_ratio * 0.4), 3)
        metric_details: Dict[str, FingerprintMetricDetail] = {}

        def _reg_detail(
            name: str,
            val: Optional[float],
            definition: str,
            units: str,
            criteria: str,
            abstain_note: Optional[str] = None,
        ) -> Optional[float]:
            if abstain_note is not None:
                val = None
            if val is None and name not in unsupported:
                unsupported.append(name)
            metric_details[name] = FingerprintMetricDetail(
                name=name,
                value=val,
                mathematical_definition=definition,
                units=units,
                eligible_observation_criteria=criteria,
                observation_count=obs_frames,
                match_count=1,
                coverage=cov_ratio,
                confidence=0.0 if val is None else conf_base,
                model_version="phase43.fingerprint.v1",
                evidence_references=[f"match:{match.match_id}"] + ([f"snapshot:{snapshot.snapshot_id}"] if snapshot else []),
                abstained_reason=abstain_note or (f"Metric {name} unavailable in verified telemetry." if val is None else None),
            )
            return val

        def _val(key: str, *, fallback_key: Optional[str] = None) -> Optional[float]:
            v = fm.get(key)
            if not isinstance(v, (int, float)) and fallback_key:
                v = fm.get(fallback_key)
            if isinstance(v, (int, float)):
                return round(float(v), 4)
            return None

        # Phase 1: In-possession metrics (only supported fields + explicit abstention/provenance)
        poss_share = _reg_detail("possession_share", _val("possession_share"), "User possession frames / total live play frames", "ratio_0_1", "Live play possession-labeled frames")
        central_prog = _reg_detail("central_progression", _val("central_progression", fallback_key="central_progression_share"), "Progressive central third-lane actions / all progressive actions", "ratio_0_1", "Possession progression events")
        wing_util = _reg_detail("wing_utilization", _val("wing_utilization"), "Flank corridor occupation & wide progression share", "ratio_0_1", "Observed ball/player flank occupancy", abstain_note=abstention_reason if team_compactness_abstained and _val("wing_utilization") is None else None)
        passing_risk = _reg_detail("passing_risk", _val("passing_risk"), "Mean inverse option safety / risky central pass density", "ratio_0_1", "Decision/pass frames in possession")
        chance_creation = _reg_detail("chance_creation", _val("chance_creation"), "Expected-threat (xT) zone-entry uplift proxy per possession", "ratio_0_1", "Final-third entries")
        att_depth = _reg_detail("attacking_depth", _val("attacking_depth", fallback_key="line_height_att_proxy"), "Highest outfield attacker x-coordinate depth proxy", "ratio_0_1", "Broadcast/minimap attacking frames", abstain_note=abstention_reason if team_compactness_abstained else None)
        half_space = _reg_detail("half_space_occupation", _val("half_space_occupation"), "Half-space lane share (14m-23m from touchline) in possession", "ratio_0_1", "Possession lane occupancy frames", abstain_note=abstention_reason if team_compactness_abstained else None)
        outlet_avail = _reg_detail("passing_outlet_availability", _val("passing_outlet_availability"), "Mean count of unblocked forward/diagonal pass angles >= 15 deg", "normalized_score", "Decision freeze-frame geometry")
        fwd_support = _reg_detail("forward_support", _val("forward_support"), "Proportion of attacking entries with >= 2 advanced runners ahead of ball", "ratio_0_1", "Final-third attack entries")
        overlap_mvt = _reg_detail("overlapping_movement", _val("overlapping_movement"), "Fullback/wide-mid overlap runs past wide receiver line", "ratio_0_1", "Wide third build-up frames")
        width_proxy_m = round(float(wing_util * 62.0), 2) if (wing_util is not None and not team_compactness_abstained) else None

        in_poss_metrics = {
            "possession_share": poss_share,
            "central_progression": central_prog,
            "wing_utilization": wing_util,
            "passing_risk": passing_risk,
            "chance_creation_xt_proxy": chance_creation,
            "attacking_depth": att_depth,
            "half_space_occupation": half_space,
            "passing_outlet_availability": outlet_avail,
            "forward_support": fwd_support,
            "overlapping_movement": overlap_mvt,
            "width_proxy_m": width_proxy_m,
        }
        in_poss = PhaseMetricBlock(
            phase="IN_POSSESSION",
            metrics=in_poss_metrics,
            unsupported_metrics=[k for k, v in in_poss_metrics.items() if v is None],
            notes=["Computed purely from observable possession frames; unmeasured proxies remain null with abstained_reason."],
        )

        # Phase 2: Out-of-possession metrics (abstain compactness/width when visible_outfield_players < 14)
        def_compact = _reg_detail("defensive_compactness", _val("defensive_compactness"), "1 - normalized inter-line defensive spread", "ratio_0_1", "Out-of-possession frames with >= 14 visible outfield players", abstain_note=abstention_reason if team_compactness_abstained else None)
        press_int = _reg_detail("pressing_intensity", _val("pressing_intensity"), "Proportion of defensive frames with active ball-carrier pressure < 4.5m", "ratio_0_1", "Defending frames near ball carrier")
        tac_disc = _reg_detail("tactical_discipline", _val("tactical_discipline"), "Adherence to zone-restoration distances out of possession", "ratio_0_1", "Defensive shape frames")
        def_mid_gap = _reg_detail("def_to_mid_gap_m", _val("def_to_mid_gap_m"), "Mean longitudinal distance between defensive line and midfield line", "meters", "Full-pitch or minimap calibrated frames >= 14 outfield players", abstain_note=abstention_reason if team_compactness_abstained else None)
        def_width = _reg_detail("defensive_width", _val("defensive_width"), "Lateral span between wide-most out-of-possession defenders", "ratio_0_1", "Defensive frames >= 14 outfield players", abstain_note=abstention_reason if team_compactness_abstained else None)
        def_line_depth = _reg_detail("defensive_line_depth", _val("defensive_line_depth"), "Normalized back-four height relative to own goal line", "ratio_0_1", "Defensive frames >= 14 outfield players", abstain_note=abstention_reason if team_compactness_abstained else None)
        central_cov = _reg_detail("central_coverage", _val("central_coverage"), "Defender occupation ratio inside Zone 14 / central corridor", "ratio_0_1", "Defensive phase frames")
        recovery_pos = _reg_detail("recovery_positioning", _val("recovery_positioning"), "Share of turnovers where midfielders recover goal-side within 3s", "ratio_0_1", "Defensive transition frames")
        def_overloads = _reg_detail("defensive_overloads", _val("defensive_overloads"), "Numerical superiority near ball zone during defensive blocks", "ratio_0_1", "Out-of-possession frames")

        out_poss_metrics = {
            "defensive_compactness": def_compact,
            "pressing_intensity": press_int,
            "tactical_discipline": tac_disc,
            "def_to_mid_gap_m": def_mid_gap,
            "defensive_width": def_width,
            "defensive_line_depth": def_line_depth,
            "central_coverage": central_cov,
            "recovery_positioning": recovery_pos,
            "defensive_overloads": def_overloads,
        }
        out_poss = PhaseMetricBlock(
            phase="OUT_OF_POSSESSION",
            metrics=out_poss_metrics,
            unsupported_metrics=[k for k, v in out_poss_metrics.items() if v is None],
            notes=["Out-of-possession structure separated strictly from nominal pre-match formation shape; team compactness abstains when <14 players visible."],
        )

        # Phase 3: Attacking transition metrics
        att_direct = _reg_detail("attacking_directness", _val("attacking_directness"), "Vertical velocity ratio toward opponent goal within 5s of recovery", "ratio_0_1", "Regain-to-attack transition windows")
        pass_tempo = _reg_detail("passing_tempo", _val("passing_tempo"), "Normalized pass cadence per possession minute", "ratio_0_1", "Possession sequences >= 2 passes")
        att_trans = PhaseMetricBlock(
            phase="ATTACKING_TRANSITION",
            metrics={
                "attacking_directness": att_direct,
                "passing_tempo": pass_tempo,
            },
            unsupported_metrics=[k for k, v in [("attacking_directness", att_direct), ("passing_tempo", pass_tempo)] if v is None],
            notes=["Measures vertical outlet speed & progression cues after ball recovery."],
        )

        # Phase 4: Defensive transition metrics (opportunity-normalized!)
        trans_opps = fm.get("transition_opportunities")
        exp_trans = fm.get("exposed_transitions")
        conceded_rate: Optional[float] = None
        if isinstance(trans_opps, (int, float)) and trans_opps > 0 and isinstance(exp_trans, (int, float)):
            conceded_rate = round(float(exp_trans) / float(trans_opps), 4)
        _reg_detail(
            "conceded_transition_rate",
            conceded_rate,
            "exposed_transitions / transition_opportunities",
            "rate_per_opportunity",
            "Matches with >= 1 transition_opportunity",
        )
        def_trans_mgmt = _reg_detail("defensive_transition_management", _val("defensive_transition_management"), "1 - weighted transition exposure penalty", "ratio_0_1", "Defensive transition sequences")
        def_trans = PhaseMetricBlock(
            phase="DEFENSIVE_TRANSITION",
            metrics={
                "transition_opportunities": float(trans_opps) if isinstance(trans_opps, (int, float)) else None,
                "exposed_transitions": float(exp_trans) if isinstance(exp_trans, (int, float)) else None,
                "conceded_transition_rate": conceded_rate,
                "defensive_transition_management": def_trans_mgmt,
            },
            unsupported_metrics=[] if conceded_rate is not None else ["conceded_transition_rate"],
            notes=["Transition vulnerability normalized by defensive transition opportunities, never raw counts alone."],
        )

        # Separate observed phase shapes from nominal pre-match formation
        obs_in_shape = "UNKNOWN_INSUFFICIENT_SPATIAL_DATA"
        obs_out_shape = "UNKNOWN_INSUFFICIENT_SPATIAL_DATA"
        if adequacy_ok:
            if wing_util is not None and central_prog is not None:
                if wing_util >= 0.65:
                    obs_in_shape = "WIDE_3_2_5_OR_OVERLAPPING_WING_SHAPE"
                elif central_prog >= 0.65:
                    obs_in_shape = "CENTRAL_BOX_OVERLOAD_SHAPE"
                else:
                    obs_in_shape = "BALANCED_BUILD_UP_SHAPE"
            if press_int is not None and def_compact is not None:
                if press_int >= 0.65 and def_compact < 0.55:
                    obs_out_shape = "STRETCHED_HIGH_PRESS_WITH_CENTRAL_GAP"
                elif press_int >= 0.65:
                    obs_out_shape = "COMPACT_HIGH_PRESS_4_4_2_OR_4_2_3_1"
                elif def_compact >= 0.62:
                    obs_out_shape = "COMPACT_MID_LOW_BLOCK"
                else:
                    obs_out_shape = "LOOSE_MID_BLOCK"

        # Intended configuration vs observed reality deltas
        deltas: List[IntendedVsObservedDelta] = []
        if snapshot:
            if snapshot.line_height is not None and press_int is not None:
                exp_press = round(snapshot.line_height / 100.0, 3)
                d_val = round(press_int - exp_press, 3)
                deltas.append(
                    IntendedVsObservedDelta(
                        dimension="press_intensity_vs_line_height",
                        intended_spec=f"line_height={snapshot.line_height} ({snapshot.defensive_approach or snapshot.tactical_profile})",
                        observed_measure=press_int,
                        expected_range=f"{max(0.0, exp_press - 0.15):.2f}..{min(1.0, exp_press + 0.15):.2f}",
                        delta=d_val,
                        alignment_status="ALIGNED" if abs(d_val) <= 0.16 else "DRIFTED",
                        explanation="Compares configured defensive line/approach against observed out-of-possession engagement.",
                    )
                )
            if snapshot.width_setting is not None and wing_util is not None:
                exp_w = round(snapshot.width_setting / 100.0, 3)
                dw = round(wing_util - exp_w, 3)
                deltas.append(
                    IntendedVsObservedDelta(
                        dimension="wing_utilization_vs_width_setting",
                        intended_spec=f"width={snapshot.width_setting}",
                        observed_measure=wing_util,
                        expected_range=f"{max(0.0, exp_w - 0.15):.2f}..{min(1.0, exp_w + 0.15):.2f}",
                        delta=dw,
                        alignment_status="ALIGNED" if abs(dw) <= 0.16 else "DRIFTED",
                        explanation="Checks whether actual flank usage matched configured width setting.",
                    )
                )
            if snapshot.tactical_profile in ("HIGH_PRESS", "PRESSING") and conceded_rate is not None:
                deltas.append(
                    IntendedVsObservedDelta(
                        dimension="press_rest_defense_cost",
                        intended_spec=f"tactical_profile={snapshot.tactical_profile}",
                        observed_measure=conceded_rate,
                        expected_range="0.00..0.28",
                        delta=round(conceded_rate - 0.28, 3),
                        alignment_status="ALIGNED" if conceded_rate <= 0.28 else "DRIFTED",
                        explanation="High press increases rest-defense counter-attack exposure when > 28% of transitions yield open lanes.",
                    )
                )

        fp = TacticalFingerprint(
            user_id=str(user_id),
            match_id=match.match_id,
            snapshot_id=snapshot.snapshot_id if snapshot else None,
            game_version=match.game_version,
            game_patch=match.game_patch,
            nominal_formation=match.formation,
            observed_in_possession_shape=obs_in_shape,
            observed_out_of_possession_shape=obs_out_shape,
            provenance=match.provenance,
            phases=[in_poss, out_poss, att_trans, def_trans],
            metric_details=metric_details,
            intended_vs_observed_deltas=deltas,
            coverage_pct=round(cov, 1),
            calibration_state=cal_state,
            visible_outfield_players=vis_int,
            team_compactness_abstained=team_compactness_abstained,
            abstention_reason=abstention_reason,
            uncertainty_notes=uncertainty_notes,
            unsupported_metrics=sorted(set(unsupported)),
            evidence_grade=EvidenceGrade.OBSERVED_ASSOCIATION if match.provenance != "SYNTHETIC_FIXTURE" else EvidenceGrade.UNSUPPORTED_CAUSAL_INFERENCE,
        )
        if save:
            self.repo.save_fingerprint(fp)
        return fp
