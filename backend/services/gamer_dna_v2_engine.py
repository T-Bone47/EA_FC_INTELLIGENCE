"""Phase 44C-F: Canonical Gamer DNA V2 Feature Architecture, Context Normalization & Dual-Layer Archetypes.

Enforces strict scientific principles:
- Separates 7 feature groups cleanly; Group G (Technical Execution) is NEVER mixed into playing-style distance.
- Missing observations remain `None` (never defaulted to `0.0`).
- Excludes `SYNTHETIC_FIXTURE` records cleanly from gamer identity.
- Separates Layer 1 interpretable heuristic archetype affinity from Layer 2 unsupervised clustering
  (which requires >= 20 independent profiles and evaluates silhouette, Davies-Bouldin & bootstrap stability).
- Fits scalers strictly on training/reference splits only to prevent data leakage.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.mixture import GaussianMixture

from backend.domain.phase40_models import ColdStartPreferences, MatchIntelligenceRecord
from backend.domain.phase43_models import TacticalFingerprint
from backend.domain.phase44_models import (
    ArchetypeAffinityItem,
    ArchetypeAssessmentV2,
    FeatureGroup,
    FeatureSourceType,
    GamerStyleVectorV2,
    StyleFeatureObservationV2,
)


def _def(
    fid: str,
    group: FeatureGroup,
    defn: str,
    *,
    units: str = "ratio_0_1",
    prof_only: bool = False,
    weight: float = 1.0,
) -> Dict[str, Any]:
    return {
        "feature_id": fid,
        "feature_group": group,
        "mathematical_definition": defn,
        "units": units,
        "is_proficiency_only": prof_only,
        "weight": weight,
    }


FEATURE_CATALOG_V2: Dict[str, Dict[str, Any]] = {
    # Group A: Possession and build-up identity (10)
    "possession_duration_norm": _def("possession_duration_norm", FeatureGroup.POSSESSION_BUILDUP, "Mean possession spell duration / benchmark 18s window"),
    "pass_frequency": _def("pass_frequency", FeatureGroup.POSSESSION_BUILDUP, "User passes per active possession minute normalized [0,1]"),
    "short_pass_preference": _def("short_pass_preference", FeatureGroup.POSSESSION_BUILDUP, "Short passes (< 12m) / total attempted passes"),
    "long_pass_preference": _def("long_pass_preference", FeatureGroup.POSSESSION_BUILDUP, "Long progressive switches (> 28m) / total attempted passes"),
    "backward_pass_frequency": _def("backward_pass_frequency", FeatureGroup.POSSESSION_BUILDUP, "Backward recycling passes / total passes"),
    "lateral_circulation": _def("lateral_circulation", FeatureGroup.POSSESSION_BUILDUP, "Horizontal passes (|dx| < 6m, |dy| > 8m) / total passes"),
    "progressive_passing_preference": _def("progressive_passing_preference", FeatureGroup.POSSESSION_BUILDUP, "Forward progressive passes (> 10m gain) / total passes"),
    "direct_progression": _def("direct_progression", FeatureGroup.POSSESSION_BUILDUP, "Direct forward vertical velocity ratio during build-up"),
    "possession_retention_preference": _def("possession_retention_preference", FeatureGroup.POSSESSION_BUILDUP, "Adjusted possession share controlled across active play frames"),
    "build_up_speed": _def("build_up_speed", FeatureGroup.POSSESSION_BUILDUP, "Normalized ball progression tempo from own third into final third"),
    # Group B: Attacking identity (10)
    "central_attacking_preference": _def("central_attacking_preference", FeatureGroup.ATTACKING_IDENTITY, "Central Zone 14 / half-space entries / total final-third entries"),
    "wide_attacking_preference": _def("wide_attacking_preference", FeatureGroup.ATTACKING_IDENTITY, "Flank touchline entries / total final-third entries"),
    "through_ball_preference": _def("through_ball_preference", FeatureGroup.ATTACKING_IDENTITY, "Line-breaking through-ball attempts / final-third actions"),
    "crossing_preference": _def("crossing_preference", FeatureGroup.ATTACKING_IDENTITY, "Box-entry crosses / wide attacking actions"),
    "carrying_frequency": _def("carrying_frequency", FeatureGroup.ATTACKING_IDENTITY, "Sustained ball-carrier carries (> 8m) / possession sequences"),
    "counter_attacking_behaviour": _def("counter_attacking_behaviour", FeatureGroup.ATTACKING_IDENTITY, "Fast vertical attacks within 6s of ball regain / total attacks"),
    "attacking_transition_speed": _def("attacking_transition_speed", FeatureGroup.ATTACKING_IDENTITY, "Mean forward x-velocity during attacking transitions"),
    "shot_selection_preference": _def("shot_selection_preference", FeatureGroup.ATTACKING_IDENTITY, "Early/distant vs patient box shot tendency [0=patient,1=early]"),
    "chance_creation_pattern_directness": _def("chance_creation_pattern_directness", FeatureGroup.ATTACKING_IDENTITY, "Average passes per shot-creating sequence inverted"),
    "risk_taking_preference": _def("risk_taking_preference", FeatureGroup.ATTACKING_IDENTITY, "Share of progressive actions choosing <2.5m clearance lanes"),
    # Group C: Defensive identity (10)
    "defensive_line_depth": _def("defensive_line_depth", FeatureGroup.DEFENSIVE_IDENTITY, "Normalized back-four height out of possession (1=high line)"),
    "defensive_compactness_shape": _def("defensive_compactness_shape", FeatureGroup.DEFENSIVE_IDENTITY, "Preferred horizontal/vertical block tightness (requires >=14 visible players)"),
    "pressing_tendency": _def("pressing_tendency", FeatureGroup.DEFENSIVE_IDENTITY, "Proportion of defensive frames applying active ball pressure <4.5m"),
    "containment_behaviour": _def("containment_behaviour", FeatureGroup.DEFENSIVE_IDENTITY, "Lane-jockey containment ratio vs immediate tackle step-ins"),
    "midfield_recovery": _def("midfield_recovery", FeatureGroup.DEFENSIVE_IDENTITY, "Midfielders recovering goal-side within 3s of turnover"),
    "centre_back_displacement_tendency": _def("centre_back_displacement_tendency", FeatureGroup.DEFENSIVE_IDENTITY, "Frequency of aggressive forward CB step-outs out of back line"),
    "central_protection": _def("central_protection", FeatureGroup.DEFENSIVE_IDENTITY, "Proportion of defensive blocks anchored in Zone 8/14"),
    "wide_defensive_coverage": _def("wide_defensive_coverage", FeatureGroup.DEFENSIVE_IDENTITY, "Flank defensive engagements normalized by wide opponent entries"),
    "transition_recovery_speed": _def("transition_recovery_speed", FeatureGroup.DEFENSIVE_IDENTITY, "Mean retreat speed toward own goal line on counter turnovers"),
    "defensive_player_selection_activity": _def("defensive_player_selection_activity", FeatureGroup.DEFENSIVE_IDENTITY, "Observable active-defender switch frequency proxy"),
    # Group D: Spatial and tactical identity (10)
    "attacking_width": _def("attacking_width", FeatureGroup.SPATIAL_TACTICAL, "Lateral attacker span in possession normalized to 68m width"),
    "average_team_depth": _def("average_team_depth", FeatureGroup.SPATIAL_TACTICAL, "Team centroid longitudinal height normalized [0,1]"),
    "midfield_spacing": _def("midfield_spacing", FeatureGroup.SPATIAL_TACTICAL, "Mean inter-midfielder spread ratio"),
    "half_space_occupation": _def("half_space_occupation", FeatureGroup.SPATIAL_TACTICAL, "Share of possession frames occupying left/right half-spaces"),
    "preferred_progression_central_zone": _def("preferred_progression_central_zone", FeatureGroup.SPATIAL_TACTICAL, "Zone 8 central progression share"),
    "passing_network_density": _def("passing_network_density", FeatureGroup.SPATIAL_TACTICAL, "Multi-outlet passing triangle availability score"),
    "overload_creation": _def("overload_creation", FeatureGroup.SPATIAL_TACTICAL, "Rate of achieving >=2v1 local superiority near ball zone"),
    "formation_fluidity": _def("formation_fluidity", FeatureGroup.SPATIAL_TACTICAL, "Variance between nominal slots and in-possession coordinates"),
    "in_possession_width_expansion": _def("in_possession_width_expansion", FeatureGroup.SPATIAL_TACTICAL, "Positive delta from out-of-possession to in-possession width"),
    "out_of_possession_block_height": _def("out_of_possession_block_height", FeatureGroup.SPATIAL_TACTICAL, "Backline x-height when opponent establishes sustained possession"),
    # Group E: Decision preference (6)
    "safer_alternative_preference": _def("safer_alternative_preference", FeatureGroup.DECISION_PREFERENCE, "Share of pre-action decision windows selecting high-retention safe outlet"),
    "progressive_action_preference": _def("progressive_action_preference", FeatureGroup.DECISION_PREFERENCE, "Share of windows selecting vertical progression over lateral recycle"),
    "pass_vs_shoot_preference": _def("pass_vs_shoot_preference", FeatureGroup.DECISION_PREFERENCE, "Passing selection ratio in final-third ambiguous windows [0=shoot,1=pass]"),
    "risk_reward_tendency": _def("risk_reward_tendency", FeatureGroup.DECISION_PREFERENCE, "Propensity toward high-xT / lower-completion options"),
    "maintain_possession_preference": _def("maintain_possession_preference", FeatureGroup.DECISION_PREFERENCE, "Preference for POSSESSION_RETENTION / RECYCLE actions"),
    "defensive_contain_vs_step_preference": _def("defensive_contain_vs_step_preference", FeatureGroup.DECISION_PREFERENCE, "Share of defensive decision windows selecting HOLD_SHAPE over ENGAGE_PRESS"),
    # Group F: Tactical adaptability (7)
    "pressure_response_shift": _def("pressure_response_shift", FeatureGroup.TACTICAL_ADAPTABILITY, "Behavioral delta when facing opponent pressing_intensity >= 0.65"),
    "leading_state_control": _def("leading_state_control", FeatureGroup.TACTICAL_ADAPTABILITY, "Possession retention adjustment observed when leading in match"),
    "trailing_state_directness": _def("trailing_state_directness", FeatureGroup.TACTICAL_ADAPTABILITY, "Direct progression shift observed when trailing"),
    "compact_block_patience": _def("compact_block_patience", FeatureGroup.TACTICAL_ADAPTABILITY, "Circulation patience when opponent defensive compactness >= 0.65"),
    "vs_high_press_adaptation": _def("vs_high_press_adaptation", FeatureGroup.TACTICAL_ADAPTABILITY, "Escape efficiency ratio against high-pressing opponents"),
    "confirmed_formation_switching_rate": _def("confirmed_formation_switching_rate", FeatureGroup.TACTICAL_ADAPTABILITY, "Share of matches with confirmed mid-match tactical formation adjustment"),
    "cross_match_tactical_variance": _def("cross_match_tactical_variance", FeatureGroup.TACTICAL_ADAPTABILITY, "Normalized behavioral dispersion across comparable patch matches"),
    # Group G: Technical execution profile (7 — STRICTLY SEPARATED from playing style!)
    "pass_success_rate": _def("pass_success_rate", FeatureGroup.TECHNICAL_EXECUTION, "Completed passes / total attempted passes", prof_only=True),
    "possession_loss_rate": _def("possession_loss_rate", FeatureGroup.TECHNICAL_EXECUTION, "Unforced/forced turnovers per possession opportunity", prof_only=True),
    "shooting_execution_quality": _def("shooting_execution_quality", FeatureGroup.TECHNICAL_EXECUTION, "Finishing execution proxy in box windows", prof_only=True),
    "defensive_recovery_success": _def("defensive_recovery_success", FeatureGroup.TECHNICAL_EXECUTION, "Successful transition/tackle containment share", prof_only=True),
    "decision_regret_inverse": _def("decision_regret_inverse", FeatureGroup.TECHNICAL_EXECUTION, "1 - clamp(mean_decision_regret, 0, 1)", prof_only=True),
    "execution_consistency": _def("execution_consistency", FeatureGroup.TECHNICAL_EXECUTION, "Cross-match execution stability across verified matches", prof_only=True),
    "opportunity_conversion_rate": _def("opportunity_conversion_rate", FeatureGroup.TECHNICAL_EXECUTION, "Final-third xT / shot conversion proficiency", prof_only=True),
}

STYLE_FEATURE_IDS: List[str] = [k for k, v in FEATURE_CATALOG_V2.items() if not v["is_proficiency_only"]]
PROFICIENCY_FEATURE_IDS: List[str] = [k for k, v in FEATURE_CATALOG_V2.items() if v["is_proficiency_only"]]

# Exact 10 Provisional Playing Style Archetypes (Phase 44F)
ARCHETYPES_V2: Dict[str, Tuple[Dict[str, float], str]] = {
    "Possession Architect": (
        {"possession_retention_preference": 0.85, "short_pass_preference": 0.82, "direct_progression": 0.32, "safer_alternative_preference": 0.78, "passing_network_density": 0.78},
        "Controls match tempo with patient short circulation, triangle support, and low-risk ball retention.",
    ),
    "Direct Attacking Specialist": (
        {"direct_progression": 0.88, "build_up_speed": 0.84, "long_pass_preference": 0.76, "risk_taking_preference": 0.72, "possession_retention_preference": 0.42},
        "Drives vertically toward opponent goal immediately upon gaining possession with rapid forward outlets.",
    ),
    "Counter-Attacking Specialist": (
        {"counter_attacking_behaviour": 0.88, "attacking_transition_speed": 0.86, "defensive_line_depth": 0.36, "pressing_tendency": 0.40, "possession_retention_preference": 0.38},
        "Absorbs territorial pressure cleanly in structured blocks before launching fast transition counters.",
    ),
    "High-Pressing Aggressor": (
        {"pressing_tendency": 0.90, "defensive_line_depth": 0.84, "out_of_possession_block_height": 0.82, "build_up_speed": 0.72, "defensive_contain_vs_step_preference": 0.25},
        "Engages relentlessly high up the pitch with aggressive counter-pressing immediately after ball loss.",
    ),
    "Defensive Controller": (
        {"central_protection": 0.86, "containment_behaviour": 0.84, "defensive_compactness_shape": 0.84, "pressing_tendency": 0.38, "risk_taking_preference": 0.30},
        "Prioritizes compact rest-defense shape, lane screening, and disciplined central box protection.",
    ),
    "Wing-Based Creator": (
        {"wide_attacking_preference": 0.86, "attacking_width": 0.84, "crossing_preference": 0.76, "central_attacking_preference": 0.35},
        "Stretches opposing blocks along touchline channels using flank overloads, switches, and deliveries.",
    ),
    "Central Combination Specialist": (
        {"central_attacking_preference": 0.86, "preferred_progression_central_zone": 0.85, "half_space_occupation": 0.80, "wide_attacking_preference": 0.34, "pass_vs_shoot_preference": 0.74},
        "Exploits narrow half-spaces and Zone 14 pockets via tight quick combinations and third-man runs.",
    ),
    "Balanced Tactical Generalist": (
        {"possession_retention_preference": 0.52, "direct_progression": 0.52, "wide_attacking_preference": 0.52, "pressing_tendency": 0.52, "central_attacking_preference": 0.52},
        "Adapts symmetrically between central circulation, flank switches, and controlled mid-block pressing.",
    ),
    "High-Risk Creative Attacker": (
        {"risk_taking_preference": 0.86, "through_ball_preference": 0.84, "carrying_frequency": 0.78, "safer_alternative_preference": 0.28, "risk_reward_tendency": 0.82},
        "Accepts higher turnover variance in exchange for defense-splitting through balls and 1v1 take-ons.",
    ),
    "Adaptive Tactical Strategist": (
        {"cross_match_tactical_variance": 0.78, "confirmed_formation_switching_rate": 0.74, "pressure_response_shift": 0.76, "vs_high_press_adaptation": 0.78},
        "Shifts formations, pressing triggers, and build-up patterns intentionally based on opponent state.",
    ),
}

_QUALITY_W = {"HIGH": 1.0, "MODERATE": 0.82, "LOW": 0.58, "INSUFFICIENT": 0.25}


def _extract_feature_from_match(
    m: MatchIntelligenceRecord,
    fp: Optional[TacticalFingerprint],
    windows_for_match: List[Dict[str, Any]],
) -> Tuple[Dict[str, Tuple[float, float, FeatureSourceType]], Dict[str, Dict[str, float]]]:
    """Extracts ONLY observed/derived numeric features from a single match + context normalization.

    Returns `{feature_id: (value, opp_denom, source_type)}` and distributional maps; absent metrics are NEVER filled with 0.
    """
    fm = dict(m.feature_metrics or {})
    opp_ctx = dict(m.opponent_context or {})
    opp_press = float(opp_ctx.get("pressing_intensity") or 0.5)
    feats: Dict[str, Tuple[float, float, FeatureSourceType]] = {}

    def _put(fid: str, val: Optional[float], denom: float = 1.0, src: FeatureSourceType = FeatureSourceType.OBSERVED) -> None:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return
        feats[fid] = (round(max(0.0, min(1.0, float(val))), 4), max(1.0, float(denom)), src)

    # Pull non-abstained Phase 43 fingerprint metrics cleanly when attached
    fp_flat: Dict[str, float] = {}
    if fp:
        for blk in fp.phases:
            for k, v in (blk.metrics or {}).items():
                if isinstance(v, (int, float)):
                    fp_flat[k] = float(v)

    poss = fm.get("possession_share") if isinstance(fm.get("possession_share"), (int, float)) else fp_flat.get("possession_share")
    if isinstance(poss, (int, float)):
        # Context adjustment: facing aggressive press (>0.65) suppresses raw possession ~4-7% without changing underlying retention intent
        adj_poss = float(poss) + max(0.0, (opp_press - 0.55) * 0.14)
        _put("possession_retention_preference", adj_poss, 100.0)
        _put("possession_duration_norm", min(1.0, adj_poss * 1.15), 10.0, FeatureSourceType.INFERRED)

    c_prog = fm.get("central_progression") or fm.get("central_progression_share") or fp_flat.get("central_progression")
    wing = fm.get("wing_utilization") or fp_flat.get("wing_utilization")
    direct = fm.get("attacking_directness") or fp_flat.get("attacking_directness")
    tempo = fm.get("passing_tempo") or fp_flat.get("passing_tempo")
    p_risk = fm.get("passing_risk") or fp_flat.get("passing_risk")
    press = fm.get("pressing_intensity") or fp_flat.get("pressing_intensity")
    dribble = fm.get("dribbling_tendency")
    chance = fm.get("chance_creation") or fp_flat.get("chance_creation_xt_proxy")
    compact = fm.get("defensive_compactness") if not (fp and fp.team_compactness_abstained) else fp_flat.get("defensive_compactness")
    disc = fm.get("tactical_discipline") or fp_flat.get("tactical_discipline")

    # Context normalize direct progression if opponent pressed high
    if isinstance(direct, (int, float)):
        ctx_direct = float(direct) - max(0.0, (opp_press - 0.65) * 0.10)
        _put("direct_progression", ctx_direct, 20.0)
        _put("long_pass_preference", min(1.0, ctx_direct * 0.85), 20.0, FeatureSourceType.INFERRED)
        _put("short_pass_preference", max(0.05, 1.0 - ctx_direct * 0.72), 20.0, FeatureSourceType.INFERRED)
        _put("counter_attacking_behaviour", min(1.0, ctx_direct * (1.1 - 0.35 * (float(poss) if isinstance(poss, (int, float)) else 0.5))), 10.0, FeatureSourceType.INFERRED)

    if isinstance(tempo, (int, float)):
        _put("build_up_speed", float(tempo), 15.0)
        _put("pass_frequency", min(1.0, 0.35 + 0.55 * float(tempo)), 20.0, FeatureSourceType.INFERRED)
        _put("attacking_transition_speed", min(1.0, float(tempo) * 1.05), 10.0, FeatureSourceType.INFERRED)
    if isinstance(c_prog, (int, float)):
        _put("central_attacking_preference", float(c_prog), 20.0)
        _put("preferred_progression_central_zone", float(c_prog), 20.0)
        _put("progressive_passing_preference", min(1.0, 0.25 + 0.65 * float(c_prog)), 20.0, FeatureSourceType.INFERRED)
        _put("half_space_occupation", fp_flat.get("half_space_occupation", float(c_prog) * 0.88), 20.0, FeatureSourceType.INFERRED)
    if isinstance(wing, (int, float)):
        _put("wide_attacking_preference", float(wing), 20.0)
        _put("attacking_width", float(wing), 20.0)
        if not (fp and fp.team_compactness_abstained):
            _put("in_possession_width_expansion", max(0.0, float(wing) - 0.35), 10.0, FeatureSourceType.INFERRED)
    if isinstance(p_risk, (int, float)):
        _put("risk_taking_preference", float(p_risk), 15.0)
        _put("through_ball_preference", min(1.0, float(p_risk) * 0.95), 15.0, FeatureSourceType.INFERRED)
    if isinstance(dribble, (int, float)):
        _put("carrying_frequency", float(dribble), 15.0)
    if isinstance(press, (int, float)):
        _put("pressing_tendency", float(press), 20.0)
        _put("defensive_line_depth", float(fm.get("defensive_line_depth") or press), 20.0, FeatureSourceType.INFERRED)
        _put("out_of_possession_block_height", float(press), 20.0, FeatureSourceType.INFERRED)
        _put("containment_behaviour", max(0.0, 1.0 - float(press) * 0.72), 15.0, FeatureSourceType.INFERRED)
    if isinstance(compact, (int, float)):
        _put("defensive_compactness_shape", float(compact), 20.0)
    if isinstance(disc, (int, float)):
        _put("central_protection", float(disc), 15.0)
        _put("centre_back_displacement_tendency", max(0.0, 1.0 - float(disc)), 15.0, FeatureSourceType.INFERRED)
    if isinstance(chance, (int, float)):
        _put("opportunity_conversion_rate", float(chance), 10.0)

    # Opportunity-normalized transition recovery (Group G proficiency vs defensive identity)
    opps = fm.get("transition_opportunities")
    exp_t = fm.get("exposed_transitions")
    if isinstance(opps, (int, float)) and opps > 0 and isinstance(exp_t, (int, float)):
        rec_success = max(0.0, 1.0 - float(exp_t) / float(opps))
        _put("defensive_recovery_success", rec_success, float(opps))
        _put("transition_recovery_speed", min(1.0, rec_success * 0.9 + 0.05), float(opps), FeatureSourceType.INFERRED)
    if isinstance(fm.get("pass_accuracy"), (int, float)):
        _put("pass_success_rate", float(fm["pass_accuracy"]), 25.0)
    if "defensive_recovery_success" not in feats and isinstance(fm.get("defensive_transition_management"), (int, float)):
        _put("defensive_recovery_success", float(fm["defensive_transition_management"]), 10.0)

    # Direct overrides from fm if already present in telemetry
    for direct_fid in FEATURE_CATALOG_V2:
        if direct_fid not in feats and isinstance(fm.get(direct_fid), (int, float)):
            _put(direct_fid, float(fm[direct_fid]), 10.0)

    # Decision Windows -> Group E Decision Preferences & Group G Regret
    if windows_for_match:
        evaluated = [w for w in windows_for_match if w.get("status") == "EVALUATED"]
        if evaluated:
            n_w = float(len(evaluated))
            regrets = [float(w.get("regret_estimate") or 0.0) for w in evaluated]
            _put("decision_regret_inverse", 1.0 - min(1.0, sum(regrets) / len(regrets)), n_w)
            pass_cnt = sum(1 for w in evaluated if w.get("decision_type") in ("ATTACKING_PASS", "THROUGH_BALL", "POSSESSION_RETENTION", "SWITCH_OR_CROSS"))
            shot_cnt = sum(1 for w in evaluated if w.get("decision_type") == "SHOT")
            if pass_cnt + shot_cnt > 0:
                _put("pass_vs_shoot_preference", pass_cnt / (pass_cnt + shot_cnt), float(pass_cnt + shot_cnt))
            retain_cnt = sum(1 for w in evaluated if w.get("decision_type") == "POSSESSION_RETENTION")
            _put("maintain_possession_preference", retain_cnt / n_w, n_w)
            prog_cnt = sum(1 for w in evaluated if w.get("decision_type") in ("THROUGH_BALL", "ATTACKING_PASS"))
            _put("progressive_action_preference", prog_cnt / n_w, n_w)
            safe_cnt = sum(1 for w in evaluated if float(w.get("regret_estimate") or 0.0) <= 0.05)
            _put("safer_alternative_preference", safe_cnt / n_w, n_w)

    # Compositional simplex distributions when component cues are available
    dists: Dict[str, Dict[str, float]] = {}
    if isinstance(direct, (int, float)) or isinstance(wing, (int, float)) or isinstance(c_prog, (int, float)):
        raw_short = max(0.05, 1.0 - float(direct or 0.5) * 0.65)
        raw_wide = max(0.05, float(wing or 0.45))
        raw_long = max(0.05, float(direct or 0.5) * 0.85)
        raw_back = max(0.05, 0.45 * (float(poss or 0.5)))
        tot = raw_short + raw_wide + raw_long + raw_back
        dists["pass_direction_distribution"] = {
            "short_central": round(raw_short / tot, 4),
            "wide_flank": round(raw_wide / tot, 4),
            "long_direct": round(raw_long / tot, 4),
            "backward_recycle": round(raw_back / tot, 4),
        }
    if isinstance(poss, (int, float)) and isinstance(tempo, (int, float)):
        sb = max(0.05, float(tempo) * 0.85)
        mb = 0.45
        lb = max(0.05, float(poss) * (1.1 - 0.5 * float(tempo)))
        tot_d = sb + mb + lb
        dists["possession_duration_distribution"] = {
            "short_burst": round(sb / tot_d, 4),
            "medium_build": round(mb / tot_d, 4),
            "sustained_spell": round(lb / tot_d, 4),
        }

    return feats, dists


class StyleArchetypeEngine:
    """Dual-layer archetype classifier: Layer 1 interpretable rules + Layer 2 sklearn clustering validation."""

    def classify_layer1(
        self,
        style_features: Dict[str, StyleFeatureObservationV2],
        *,
        eligible_match_count: int,
        cold_start: Optional[ColdStartPreferences] = None,
    ) -> ArchetypeAssessmentV2:
        obs = {fid: ob.raw_value for fid, ob in style_features.items() if ob.raw_value is not None}
        if eligible_match_count == 0 or not obs:
            if cold_start:
                tmap = {
                    "SLOW_POSSESSION": "Possession Architect",
                    "FAST_DIRECT": "Direct Attacking Specialist",
                    "BALANCED": "Balanced Tactical Generalist",
                }
                prim = tmap.get(cold_start.preferred_tempo, "Balanced Tactical Generalist")
                return ArchetypeAssessmentV2(
                    layer_used="ABSTAINED",
                    status="COLD_START_HINT",
                    primary_archetype=prim,
                    archetypes=[ArchetypeAffinityItem(archetype=prim, affinity_score=0.5, rationale="Self-reported cold-start preference only (zero matches).")],
                    summary="Cold-start self-reported hint only; upload real EA FC gameplay to measure observed DNA.",
                )
            return ArchetypeAssessmentV2(
                layer_used="ABSTAINED",
                status="INSUFFICIENT_EVIDENCE",
                primary_archetype="Undetermined (Cold Start)",
                archetypes=[],
                summary="Zero verified non-synthetic matches present. No playing-style archetype fabricated.",
            )

        items: List[ArchetypeAffinityItem] = []
        for arch_name, (proto, rationale) in ARCHETYPES_V2.items():
            overlap = [k for k in proto if k in obs]
            if not overlap:
                continue
            l1_dist = sum(abs(obs[k] - proto[k]) for k in overlap) / len(overlap)
            aff = round(max(0.0, min(1.0, 1.0 - l1_dist)), 4)
            items.append(ArchetypeAffinityItem(archetype=arch_name, affinity_score=aff, supporting_features=overlap, rationale=rationale))

        if not items:
            return ArchetypeAssessmentV2(
                layer_used="LAYER1_INTERPRETABLE_RULE",
                status="INSUFFICIENT_EVIDENCE",
                primary_archetype="Undetermined (Low Overlap)",
                summary="Observed feature overlap insufficient to map tactical archetype reliably.",
            )

        items.sort(key=lambda x: x.affinity_score, reverse=True)
        # Softmax over temperature-scaled affinities for heuristic probability weights
        temps = [math.exp(it.affinity_score * 6.0) for it in items]
        z_sum = max(1e-9, sum(temps))
        for it, t_v in zip(items, temps):
            it.membership_probability = round(t_v / z_sum, 4)

        top = items[0]
        sec = items[1] if len(items) > 1 else None
        if top.affinity_score < 0.52:
            return ArchetypeAssessmentV2(
                layer_used="LAYER1_INTERPRETABLE_RULE",
                status="OUT_OF_DISTRIBUTION",
                primary_archetype="Unclassified / Out-of-Distribution",
                secondary_archetype=top.archetype,
                archetypes=items[:4],
                summary=f"Top heuristic affinity ({top.affinity_score:.2f}) falls below 0.52 OOD floor; preserving honest uncertainty.",
            )

        is_mixed = bool(sec and (top.affinity_score - sec.affinity_score) <= 0.08)
        return ArchetypeAssessmentV2(
            layer_used="LAYER1_INTERPRETABLE_RULE",
            status="MIXED_PROFILE" if is_mixed else "SINGLE_DOMINANT",
            primary_archetype=top.archetype,
            secondary_archetype=sec.archetype if is_mixed and sec else None,
            archetypes=items[:4],
            summary=(
                f"Mixed {top.archetype} / {sec.archetype}" if is_mixed and sec else f"Primary archetype: {top.archetype}"
            ) + f" (n={eligible_match_count} verified match(es); Layer 1 heuristic rules).",
        )

    @staticmethod
    def evaluate_unsupervised_clusters(
        feature_matrix: np.ndarray,
        *,
        k_range: Sequence[int] = (2, 3, 4, 5),
        random_state: int = 44,
    ) -> Dict[str, Any]:
        """Layer 2 empirical cluster evaluation across KMeans, GMM & Hierarchical (never assumes fixed k)."""
        n_samples = int(feature_matrix.shape[0]) if feature_matrix.ndim == 2 else 0
        if n_samples < 20 or feature_matrix.shape[1] < 2:
            return {
                "status": "INSUFFICIENT_PROFILES_FOR_EMPIRICAL_CLUSTERING",
                "n_profiles": n_samples,
                "minimum_required": 20,
                "best_algorithm": None,
                "caveat": "Empirical cluster discovery requires >= 20 independent gameplay profiles; Layer 1 heuristic rules remain active.",
            }

        # Robust median/IQR scaling fit strictly within passed training matrix
        med = np.nanmedian(feature_matrix, axis=0)
        q75 = np.nanpercentile(feature_matrix, 75, axis=0)
        q25 = np.nanpercentile(feature_matrix, 25, axis=0)
        iqr = np.where((q75 - q25) > 1e-6, q75 - q25, 1.0)
        X = np.nan_to_num((feature_matrix - med) / iqr, nan=0.0)

        n_comp = min(X.shape[1], max(2, min(8, n_samples // 4)))
        X_pca = PCA(n_components=n_comp, random_state=random_state).fit_transform(X)

        candidates: List[Dict[str, Any]] = []
        rng = np.random.default_rng(random_state)
        for k in k_range:
            if k >= n_samples - 1 or k < 2:
                continue
            for algo_name, factory in (
                ("KMeans", lambda kk=k: KMeans(n_clusters=kk, n_init=10, random_state=random_state).fit_predict(X_pca)),
                ("GMM", lambda kk=k: GaussianMixture(n_components=kk, random_state=random_state).fit_predict(X_pca)),
                ("Agglomerative", lambda kk=k: AgglomerativeClustering(n_clusters=kk).fit_predict(X_pca)),
            ):
                labels = factory()
                if len(set(labels)) < 2:
                    continue
                sil = float(silhouette_score(X_pca, labels))
                db_idx = float(davies_bouldin_score(X_pca, labels))
                # Quick 5-subsample bootstrap Adjusted Rand / label agreement stability proxy
                agrees: List[float] = []
                for _ in range(5):
                    idx = rng.choice(n_samples, size=max(10, int(0.8 * n_samples)), replace=False)
                    sub_lbl = KMeans(n_clusters=k, n_init=5, random_state=random_state).fit_predict(X_pca[idx])
                    # Pairwise co-clustering agreement on sampled subset
                    m_full = labels[idx][:, None] == labels[idx][None, :]
                    m_sub = sub_lbl[:, None] == sub_lbl[None, :]
                    agrees.append(float(np.mean(m_full == m_sub)))
                stab = float(np.mean(agrees))
                candidates.append(
                    {
                        "algorithm": algo_name,
                        "k": int(k),
                        "silhouette_score": round(sil, 4),
                        "davies_bouldin_index": round(db_idx, 4),
                        "bootstrap_stability": round(stab, 4),
                    }
                )

        if not candidates:
            return {"status": "NO_SEPARABLE_CLUSTERS_FOUND", "n_profiles": n_samples}
        candidates.sort(key=lambda c: (c["silhouette_score"], c["bootstrap_stability"]), reverse=True)
        return {
            "status": "VALIDATED_EMPIRICAL_CLUSTERING",
            "n_profiles": n_samples,
            "best": candidates[0],
            "all_evaluated": candidates[:9],
            "note": "Dimensionality reduction (PCA) aids noise filtering only and never substitutes for silhouette/bootstrap validation.",
        }


class GamerDNAV2Engine:
    """Builds versioned, context-normalized, leak-free GamerStyleVectorV2 profiles."""

    def __init__(self, archetype_engine: Optional[StyleArchetypeEngine] = None) -> None:
        self.archetype_engine = archetype_engine or StyleArchetypeEngine()

    @staticmethod
    def fit_robust_scaler_stats(train_vectors: List[Dict[str, Optional[float]]]) -> Dict[str, Tuple[float, float]]:
        """Fits median & IQR scaling strictly on training/reference profiles ONLY (prevents data leakage)."""
        stats_map: Dict[str, Tuple[float, float]] = {}
        for fid in FEATURE_CATALOG_V2:
            vals = [float(v[fid]) for v in train_vectors if isinstance(v.get(fid), (int, float))]
            if len(vals) >= 3:
                arr = np.asarray(vals, dtype=np.float64)
                med = float(np.median(arr))
                iqr = float(np.percentile(arr, 75) - np.percentile(arr, 25))
                stats_map[fid] = (med, iqr if iqr > 1e-4 else max(0.08, float(np.std(arr))))
            else:
                # Documented fallback unit range center/spread when reference cohort unavailable
                stats_map[fid] = (0.5, 0.25)
        return stats_map

    def build_profile(
        self,
        user_id: str,
        matches: List[MatchIntelligenceRecord],
        *,
        game_version: str = "FC27",
        game_patch: str = "ALL",
        gameplay_mode: str = "ALL",
        fingerprints: Optional[List[TacticalFingerprint]] = None,
        decision_windows: Optional[List[Dict[str, Any]]] = None,
        cold_start: Optional[ColdStartPreferences] = None,
        fit_scaler_stats: Optional[Dict[str, Tuple[float, float]]] = None,
        scaler_fit_split: str = "NONE",
    ) -> GamerStyleVectorV2:
        uid = str(user_id)
        gv = "FC26" if game_version.upper() == "FC26" else "FC27"
        now_dt = datetime.now(timezone.utc)

        synth_excl = 0
        eligible: List[MatchIntelligenceRecord] = []
        for m in matches:
            if m.provenance == "SYNTHETIC_FIXTURE":
                synth_excl += 1
                continue
            if m.game_version != gv:
                continue
            if game_patch != "ALL" and m.game_patch != game_patch:
                continue
            if gameplay_mode != "ALL" and m.gameplay_mode != gameplay_mode:
                continue
            eligible.append(m)

        fp_by_match = {fp.match_id: fp for fp in (fingerprints or []) if fp.provenance != "SYNTHETIC_FIXTURE"}
        wins_by_match: Dict[str, List[Dict[str, Any]]] = {}
        for w in (decision_windows or []):
            if w.get("provenance") == "SYNTHETIC_FIXTURE":
                continue
            mid = str(w.get("match_id") or "")
            if mid:
                wins_by_match.setdefault(mid, []).append(w)

        scaler = fit_scaler_stats or self.fit_robust_scaler_stats([])

        # Accumulate match-level observations weighted cleanly by quality * recency decay
        obs_acc: Dict[str, List[Tuple[float, float, float, FeatureSourceType, str]]] = {}
        dist_acc: Dict[str, Dict[str, List[float]]] = {}
        confirmed_switches = 0
        formations_seen: set[str] = set()

        for m in eligible:
            try:
                dt = datetime.fromisoformat(m.created_at.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age_days = max(0.0, (now_dt - dt).total_seconds() / 86400.0)
            except Exception:
                age_days = 0.0
            q_w = _QUALITY_W.get(m.observation_quality, 0.7) * math.exp(-0.02 * age_days)
            fp = fp_by_match.get(m.match_id)
            m_feats, m_dists = _extract_feature_from_match(m, fp, wins_by_match.get(m.match_id, []))
            formations_seen.add(m.formation)
            if (m.opponent_context or {}).get("mid_match_switch_confirmed"):
                confirmed_switches += 1

            for fid, (val, opp_d, src) in m_feats.items():
                obs_acc.setdefault(fid, []).append((val, q_w, opp_d, src, m.match_id))
            for dn, dm in m_dists.items():
                b = dist_acc.setdefault(dn, {})
                for dk, dv in dm.items():
                    b.setdefault(dk, []).append(dv)

        # Group F adaptability aggregates derived across multi-match cohort
        if len(eligible) >= 2:
            if "confirmed_formation_switching_rate" not in obs_acc:
                obs_acc["confirmed_formation_switching_rate"] = [
                    (confirmed_switches / len(eligible), 1.0, float(len(eligible)), FeatureSourceType.OBSERVED, m.match_id)
                    for m in eligible[:1]
                ]
            press_vals = [x[0] for x in obs_acc.get("pressing_tendency", [])]
            if len(press_vals) >= 2 and "cross_match_tactical_variance" not in obs_acc:
                var_score = min(1.0, float(np.std(press_vals)) * 3.0)
                obs_acc["cross_match_tactical_variance"] = [
                    (var_score, 1.0, float(len(press_vals)), FeatureSourceType.INFERRED, m.match_id)
                    for m in eligible[:1]
                ]

        style_features: Dict[str, StyleFeatureObservationV2] = {}
        proficiency_features: Dict[str, StyleFeatureObservationV2] = {}
        n_eligible = len(eligible)

        for fid, meta in FEATURE_CATALOG_V2.items():
            entries = obs_acc.get(fid, [])
            med, spread = scaler.get(fid, (0.5, 0.25))
            if not entries:
                obs_obj = StyleFeatureObservationV2(
                    feature_id=fid,
                    feature_group=meta["feature_group"],
                    mathematical_definition=meta["mathematical_definition"],
                    units=meta["units"],
                    game_version=gv,  # type: ignore[arg-type]
                    game_patch=game_patch,
                    gameplay_mode=gameplay_mode,
                    raw_value=None,
                    normalized_value=None,
                    match_count=0,
                    coverage=0.0,
                    uncertainty=None,
                    source_type=FeatureSourceType.UNKNOWN,
                    is_proficiency_only=meta["is_proficiency_only"],
                )
            else:
                vals = np.asarray([e[0] for e in entries], dtype=np.float64)
                ws = np.asarray([e[1] for e in entries], dtype=np.float64)
                w_sum = max(1e-8, float(np.sum(ws)))
                w_mean = float(np.sum(vals * ws) / w_sum)
                # Kish effective sample size + conservative spread uncertainty
                n_eff = float((w_sum ** 2) / max(1e-8, float(np.sum(ws ** 2))))
                std_val = float(np.std(vals, ddof=1)) if len(vals) >= 2 else 0.14
                se = round(max(0.02, std_val / math.sqrt(max(1.0, n_eff))), 4)
                z_norm = round((w_mean - med) / max(1e-4, spread), 4)
                opp_sum = sum(e[2] for e in entries)
                cov_ratio = round(min(1.0, len(entries) / max(1, n_eligible)), 3)
                src_type = FeatureSourceType.OBSERVED if any(e[3] == FeatureSourceType.OBSERVED for e in entries) else entries[0][3]
                obs_obj = StyleFeatureObservationV2(
                    feature_id=fid,
                    feature_group=meta["feature_group"],
                    mathematical_definition=meta["mathematical_definition"],
                    units=meta["units"],
                    game_version=gv,  # type: ignore[arg-type]
                    game_patch=game_patch,
                    gameplay_mode=gameplay_mode,
                    raw_value=round(w_mean, 4),
                    normalized_value=z_norm,
                    eligible_observations=len(entries),
                    opportunity_denominator=round(opp_sum, 1),
                    match_count=len({e[4] for e in entries}),
                    coverage=cov_ratio,
                    uncertainty=se,
                    source_type=src_type,
                    is_proficiency_only=meta["is_proficiency_only"],
                    evidence_references=sorted({f"match:{e[4]}" for e in entries})[:8],
                )
            if meta["is_proficiency_only"]:
                proficiency_features[fid] = obs_obj
            else:
                style_features[fid] = obs_obj

        observed_style_cnt = sum(1 for v in style_features.values() if v.raw_value is not None)
        overall_cov = round(observed_style_cnt / max(1, len(style_features)), 3)
        maturity = (
            "COLD_START"
            if n_eligible == 0
            else ("PRELIMINARY" if n_eligible < 3 else ("EMERGING" if n_eligible < 6 else "STABLE"))
        )

        archetype = self.archetype_engine.classify_layer1(
            style_features, eligible_match_count=n_eligible, cold_start=cold_start
        )
        distributions = {
            dn: {dk: round(sum(vs) / len(vs), 4) for dk, vs in dm.items()}
            for dn, dm in dist_acc.items()
        }
        lims = [
            "Group G technical execution/proficiency features are isolated strictly from Groups A-F style matching.",
            "Missing observations remain null (never imputed as 0.0).",
            "Controller inputs and skill-move intents are not inferred without explicit button/input evidence.",
        ]
        if synth_excl:
            lims.append(f"Excluded {synth_excl} SYNTHETIC_FIXTURE record(s) before computing playing identity.")

        return GamerStyleVectorV2(
            user_id=uid,
            game_version=gv,  # type: ignore[arg-type]
            game_patch=game_patch,
            gameplay_mode=gameplay_mode,
            eligible_match_count=n_eligible,
            synthetic_excluded_count=synth_excl,
            profile_maturity=maturity,  # type: ignore[arg-type]
            overall_coverage=overall_cov,
            style_features=style_features,
            proficiency_features=proficiency_features,
            distributions=distributions,
            context_summary={
                "formations_observed": sorted(formations_seen),
                "patch_filter": game_patch,
                "mode_filter": gameplay_mode,
                "observed_style_features": observed_style_cnt,
                "total_style_features": len(style_features),
            },
            scaler_fit_split=scaler_fit_split,
            archetype=archetype,
            limitations=lims,
        )
