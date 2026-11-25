"""Phase 40C: Explainable, Uncertainty-Aware Gamer DNA Engine.

Strictly separates:
  1. Playing Style (what the gamer tends to do)
  2. Playing Proficiency (how effectively actions execute)
  3. Tactical Suitability (compatible formations & FC IQ roles)
  4. Improvement Potential (highest-leverage growth areas)

Enforces strict synthetic exclusion (`SYNTHETIC_FIXTURE` never updates real Gamer DNA),
within-match cluster adjustment (frames are not independent samples), recency-quality
decay weighting w_i = exp(-lambda * age_days_i) * quality_i, Kish effective sample size,
and Bayesian Beta-Binomial uncertainty intervals with suppression under sparse evidence.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.domain.phase40_models import (
    ArchetypeAssessment,
    ArchetypeWeight,
    ColdStartPreferences,
    DimensionEstimate,
    GamerDNAProfile,
    ImprovementPotentialItem,
    MatchIntelligenceRecord,
    TacticalSuitabilityOption,
)


STYLE_DIMENSIONS: List[Tuple[str, str]] = [
    ("attacking_directness", "Proportion of progressive passing/carry opportunities attacking vertically toward opponent goal."),
    ("possession_preference", "Share of active observable frames controlled in possession adjusted for opponent block."),
    ("passing_tempo", "Mean transition speed of candidate passing progressions per possession sequence."),
    ("passing_risk", "Share of passing intentions targeting tight or obstructed central corridors (< 2.5m clearance)."),
    ("wing_utilization", "Width-channel occupancy (Left/Right flank share relative to 68m pitch width)."),
    ("central_progression", "Share of forward progressions sustaining through Zone 8 / half-spaces without turnover."),
    ("dribbling_tendency", "Frequency of sustained ball-carrier drives relative to early passing releases."),
    ("pressing_intensity", "Out-of-possession engagement line height and number of high pressers ahead of ball."),
]

PROFICIENCY_DIMENSIONS: List[Tuple[str, str]] = [
    ("chance_creation", "Expected Threat (xT) progression delta created across calibrated attacking sequences."),
    ("finishing_decisions", "Quality and location separation of shooting opportunities when attacking Zone 14/box."),
    ("defensive_compactness", "Ability to sustain compact team area (< 2300 m2) and horizontal block integrity out of possession."),
    ("defensive_transition_management", "Rate of defending transitions without yielding exposed central channels (1 - exposure rate)."),
    ("tactical_discipline", "Backline integrity score reflecting absence of unforced CB displacement and role overlaps."),
    ("adaptability", "Stability/recovery of tactical structure across second-half or formation state changes."),
    ("decision_making_under_pressure", "Clean ball retention / safe outlet execution under tight defensive pressure."),
    ("match_to_match_consistency", "Cross-match dispersion consistency score across 3+ independent non-synthetic matches."),
]

ARCHETYPES: Dict[str, Tuple[Dict[str, float], str]] = {
    "Possession Controller": (
        {"possession_preference": 0.85, "attacking_directness": 0.30, "passing_tempo": 0.40, "central_progression": 0.72, "wing_utilization": 0.55},
        "Prioritizes ball retention, short circulation triangles, and structured territorial build-up.",
    ),
    "Vertical Playmaker": (
        {"possession_preference": 0.62, "attacking_directness": 0.80, "passing_tempo": 0.75, "central_progression": 0.78, "passing_risk": 0.62},
        "Threads line-breaking vertical passes rapidly between opponent midfield and defensive lines.",
    ),
    "Counter-Attack Specialist": (
        {"possession_preference": 0.35, "attacking_directness": 0.88, "passing_tempo": 0.85, "wing_utilization": 0.68, "pressing_intensity": 0.42},
        "Absorbs pressure in mid/low blocks and springs fast multi-lane transitions after turnovers.",
    ),
    "High-Press Aggressor": (
        {"pressing_intensity": 0.90, "passing_tempo": 0.72, "attacking_directness": 0.70, "defensive_compactness": 0.58},
        "Commits multiple high pressers immediately out of possession to force high-zone recoveries.",
    ),
    "Technical Dribbler": (
        {"dribbling_tendency": 0.86, "passing_tempo": 0.50, "central_progression": 0.68, "possession_preference": 0.66},
        "Creates separation via close-control carries and 1v1 ball-carrier isolations.",
    ),
    "Wing Play Specialist": (
        {"wing_utilization": 0.88, "attacking_directness": 0.65, "passing_risk": 0.38, "possession_preference": 0.55},
        "Stretches defensive blocks along touchlines via overlaps, switches, and wide delivery.",
    ),
    "Central Combination Player": (
        {"central_progression": 0.86, "wing_utilization": 0.30, "passing_tempo": 0.68, "possession_preference": 0.70},
        "Concentrates quick give-and-go combinations through Zone 8 and half-spaces.",
    ),
    "Defensive Organizer": (
        {"defensive_compactness": 0.86, "defensive_transition_management": 0.84, "tactical_discipline": 0.85, "pressing_intensity": 0.38},
        "Prioritizes compact rest defense, disciplined CB tracking, and low counter exposure.",
    ),
    "Balanced Tactical Player": (
        {"possession_preference": 0.52, "attacking_directness": 0.52, "wing_utilization": 0.52, "pressing_intensity": 0.52, "passing_tempo": 0.52},
        "Maintains symmetrical equilibrium between direct progression, patience, and block height.",
    ),
    "Direct Attacking Specialist": (
        {"attacking_directness": 0.90, "passing_tempo": 0.82, "passing_risk": 0.68, "possession_preference": 0.40},
        "Pushes forward aggressively on first progressive cues with higher-variance vertical outlets.",
    ),
}


_QUALITY_WEIGHT = {"HIGH": 1.0, "MODERATE": 0.82, "LOW": 0.58, "INSUFFICIENT": 0.25}


def _parse_age_days(iso_ts: str, now_dt: datetime) -> float:
    if not iso_ts:
        return 0.0
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (now_dt - dt).total_seconds() / 86400.0)
    except ValueError:
        return 0.0


def _beta_interval(weighted_mean: float, n_eff: float, alpha0: float = 2.0, beta0: float = 2.0) -> Tuple[float, float, float]:
    """Computes Bayesian Beta-Binomial posterior mean & 95% credible interval."""
    p = max(0.0, min(1.0, weighted_mean))
    k_eff = p * n_eff
    alpha = alpha0 + k_eff
    beta = beta0 + max(0.0, n_eff - k_eff)
    total = alpha + beta
    post_mean = alpha / total
    var = (alpha * beta) / ((total ** 2) * (total + 1.0))
    se = math.sqrt(max(0.0, var))
    ci_lo = max(0.0, post_mean - 1.96 * se)
    ci_hi = min(1.0, post_mean + 1.96 * se)
    return round(post_mean, 4), round(ci_lo, 4), round(ci_hi, 4)


def _metric_from_match(match: MatchIntelligenceRecord, dim: str) -> Optional[float]:
    fm = match.feature_metrics or {}
    if dim == "possession_preference" and "possession_share" in fm:
        return float(fm["possession_share"])
    if dim in fm and isinstance(fm[dim], (int, float)):
        return max(0.0, min(1.0, float(fm[dim])))
    # Conservative fallback derived directly from verified tactical findings counts if metric missing
    findings = match.coaching_findings or []
    if dim == "defensive_compactness":
        bad = sum(1 for f in findings if f.get("code") == "POOR_DEFENSIVE_COMPACTNESS")
        return max(0.20, 0.78 - 0.22 * bad)
    if dim == "defensive_transition_management":
        bad = sum(1 for f in findings if f.get("code") in ("COUNTER_ATTACK_VULNERABILITY", "EXPOSED_CENTRAL_CHANNEL"))
        return max(0.20, 0.80 - 0.22 * bad)
    if dim == "tactical_discipline":
        bad = sum(1 for f in findings if f.get("code") in ("UNNECESSARY_CB_DISPLACEMENT", "OVERLAPPING_PLAYER_ROLES"))
        return max(0.20, 0.82 - 0.20 * bad)
    return None


class GamerDNAEngine:
    """Computes uncertainty-aware multi-dimensional Gamer DNA from verified match evidence."""

    MODEL_VERSION = "gamer_dna.v1"

    def __init__(self, recency_lambda: float = 0.035) -> None:
        self.recency_lambda = recency_lambda

    def build_profile(
        self,
        user_id: str,
        matches: List[MatchIntelligenceRecord],
        *,
        cold_start: Optional[ColdStartPreferences] = None,
        patch_scope: str = "ALL",
        now_dt: Optional[datetime] = None,
    ) -> GamerDNAProfile:
        now = now_dt or datetime.now(timezone.utc)

        # STRICT EPISTEMIC FIREWALL: synthetic fixtures never feed Gamer DNA
        synthetic_count = sum(1 for m in matches if m.provenance == "SYNTHETIC_FIXTURE")
        eligible = [
            m for m in matches
            if m.provenance != "SYNTHETIC_FIXTURE"
            and m.observation_quality != "INSUFFICIENT"
            and (patch_scope == "ALL" or m.game_patch == patch_scope)
        ]

        style_ests = [self._estimate_dimension(name, desc, "STYLE", eligible, now) for name, desc in STYLE_DIMENSIONS]
        prof_ests = [self._estimate_dimension(name, desc, "PROFICIENCY", eligible, now) for name, desc in PROFICIENCY_DIMENSIONS]

        style_map = {e.dimension: e.estimated_value for e in style_ests if e.estimated_value is not None}
        prof_map = {e.dimension: e.estimated_value for e in prof_ests if e.estimated_value is not None}
        combined_map = {**style_map, **prof_map}

        archetype = self._classify_archetype(combined_map, len(eligible), cold_start)
        suitability = self._recommend_tactical_suitability(style_map, prof_map, cold_start)
        improvements = self._rank_improvements(prof_ests, style_ests)

        cold_hints = self._cold_start_hints(cold_start) if cold_start else []

        return GamerDNAProfile(
            user_id=user_id,
            model_version=self.MODEL_VERSION,
            eligible_match_count=len(eligible),
            synthetic_excluded_count=synthetic_count,
            recency_lambda_per_day=self.recency_lambda,
            patch_scope=patch_scope,
            has_cold_start_preferences=cold_start is not None,
            cold_start_preferences=cold_start,
            cold_start_style_hints=cold_hints,
            style_dimensions=style_ests,
            proficiency_dimensions=prof_ests,
            tactical_suitability=suitability,
            improvement_potential=improvements,
            archetype=archetype,
        )

    def _estimate_dimension(
        self,
        name: str,
        definition: str,
        category: str,
        eligible: List[MatchIntelligenceRecord],
        now_dt: datetime,
    ) -> DimensionEstimate:
        if name == "match_to_match_consistency":
            return self._estimate_consistency(name, definition, eligible, now_dt)

        obs_values: List[float] = []
        weights: List[float] = []
        raw_samples = 0
        evidence_refs: List[str] = []
        patches: set[str] = set()
        coverages: List[float] = []

        for m in eligible:
            val = _metric_from_match(m, name)
            if val is None:
                continue
            age = _parse_age_days(m.created_at, now_dt)
            q_base = _QUALITY_WEIGHT.get(m.observation_quality, 0.7)
            cov_factor = max(0.4, min(1.0, (m.tracking_coverage_pct or 70.0) / 100.0))
            duration_factor = 0.7 if m.is_partial_match else 1.0
            clusters = max(1, int((m.feature_metrics or {}).get("sequence_clusters", 3)))
            # Within-match correlation cap: cap weight boost cleanly rather than treating frames as independent
            w = math.exp(-self.recency_lambda * age) * q_base * cov_factor * duration_factor * min(4.0, math.sqrt(clusters))
            obs_values.append(val)
            weights.append(w)
            raw_samples += clusters
            evidence_refs.append(m.match_id)
            patches.add(f"{m.game_version}:{m.game_patch}")
            coverages.append(m.tracking_coverage_pct)

        if not obs_values:
            return DimensionEstimate(
                dimension=name,
                axis_category=category,  # type: ignore[arg-type]
                status="INSUFFICIENT_EVIDENCE",
                estimated_value=None,
                measurement_definition=definition,
                sample_count=0,
                effective_sample_size=0.0,
                relevant_match_count=0,
                observation_coverage=0.0,
                model_version=self.MODEL_VERSION,
            )

        w_sum = sum(weights)
        w_sq_sum = sum(w * w for w in weights)
        kish_neff = (w_sum * w_sum / w_sq_sum) if w_sq_sum > 0 else 0.0
        # Account conservatively for cluster scale so CI isn't artificially narrow on 1 match
        effective_n = round(max(1.0, min(float(raw_samples), kish_neff * 3.0)), 2)
        w_mean = sum(v * w for v, w in zip(obs_values, weights)) / w_sum

        post_mean, ci_lo, ci_hi = _beta_interval(w_mean, effective_n)
        avg_cov = round(sum(coverages) / len(coverages), 1)

        if len(obs_values) < 1 or effective_n < 1.2:
            status = "INSUFFICIENT_EVIDENCE"
            est_val = None
            ci_lo_out, ci_hi_out, width_out = None, None, None
        elif len(obs_values) == 1:
            status = "LOW_SAMPLE_PROVISIONAL"
            est_val = post_mean
            ci_lo_out, ci_hi_out = ci_lo, ci_hi
            width_out = round(ci_hi - ci_lo, 4)
        else:
            status = "OBSERVED"
            est_val = post_mean
            ci_lo_out, ci_hi_out = ci_lo, ci_hi
            width_out = round(ci_hi - ci_lo, 4)

        return DimensionEstimate(
            dimension=name,
            axis_category=category,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            estimated_value=est_val,
            measurement_definition=definition,
            sample_count=raw_samples,
            effective_sample_size=effective_n,
            relevant_match_count=len(obs_values),
            observation_coverage=avg_cov,
            ci_low=ci_lo_out,
            ci_high=ci_hi_out,
            uncertainty_width=width_out,
            evidence_references=evidence_refs,
            model_version=self.MODEL_VERSION,
            applicable_editions_patches=sorted(patches),
        )

    def _estimate_consistency(
        self,
        name: str,
        definition: str,
        eligible: List[MatchIntelligenceRecord],
        now_dt: datetime,
    ) -> DimensionEstimate:
        if len(eligible) < 3:
            return DimensionEstimate(
                dimension=name,
                axis_category="PROFICIENCY",
                status="INSUFFICIENT_EVIDENCE",
                estimated_value=None,
                measurement_definition=definition,
                sample_count=len(eligible),
                effective_sample_size=float(len(eligible)),
                relevant_match_count=len(eligible),
                observation_coverage=round(sum(m.tracking_coverage_pct for m in eligible) / max(1, len(eligible)), 1) if eligible else 0.0,
                evidence_references=[m.match_id for m in eligible],
                model_version=self.MODEL_VERSION,
            )

        match_composites = []
        for m in eligible:
            vals = [v for k in ("defensive_compactness", "central_progression", "tactical_discipline") if (v := _metric_from_match(m, k)) is not None]
            if vals:
                match_composites.append(sum(vals) / len(vals))
        mean_c = sum(match_composites) / len(match_composites)
        mad = sum(abs(x - mean_c) for x in match_composites) / len(match_composites)
        raw_consistency = max(0.05, min(0.98, 1.0 - mad * 2.5))
        post_mean, ci_lo, ci_hi = _beta_interval(raw_consistency, float(len(match_composites) * 2))
        return DimensionEstimate(
            dimension=name,
            axis_category="PROFICIENCY",
            status="OBSERVED",
            estimated_value=post_mean,
            measurement_definition=definition,
            sample_count=len(match_composites),
            effective_sample_size=float(len(match_composites)),
            relevant_match_count=len(eligible),
            observation_coverage=round(sum(m.tracking_coverage_pct for m in eligible) / len(eligible), 1),
            ci_low=ci_lo,
            ci_high=ci_hi,
            uncertainty_width=round(ci_hi - ci_lo, 4),
            evidence_references=[m.match_id for m in eligible],
            model_version=self.MODEL_VERSION,
            applicable_editions_patches=sorted({f"{m.game_version}:{m.game_patch}" for m in eligible}),
        )

    @staticmethod
    def _classify_archetype(
        observed: Dict[str, float],
        match_count: int,
        cold_start: Optional[ColdStartPreferences],
    ) -> ArchetypeAssessment:
        if match_count == 0 or not observed:
            if cold_start:
                hint_map = {
                    "SLOW_POSSESSION": "Possession Controller",
                    "FAST_DIRECT": "Direct Attacking Specialist",
                    "BALANCED": "Balanced Tactical Player",
                }
                primary = hint_map.get(cold_start.preferred_tempo, "Balanced Tactical Player")
                return ArchetypeAssessment(
                    status="UNCERTAIN_COLD_START",
                    primary_archetype=primary,
                    secondary_archetype=None,
                    weights=[ArchetypeWeight(archetype=primary, affinity_score=0.5, rationale="Self-reported cold-start preference only (zero observed gameplay).")],
                    summary="Provisional cold-start style hint from questionnaire; upload or import real gameplay to confirm archetype.",
                )
            return ArchetypeAssessment(
                status="INSUFFICIENT_EVIDENCE",
                primary_archetype="Undetermined (Cold Start)",
                secondary_archetype=None,
                weights=[],
                summary="Zero verified non-synthetic matches observed yet. No archetype classification fabricated.",
            )

        scores: List[ArchetypeWeight] = []
        for arch_name, (proto, rationale) in ARCHETYPES.items():
            overlap = [k for k in proto if k in observed]
            if not overlap:
                continue
            dist = sum(abs(observed[k] - proto[k]) for k in overlap) / len(overlap)
            affinity = round(max(0.0, min(1.0, 1.0 - dist)), 3)
            scores.append(ArchetypeWeight(archetype=arch_name, affinity_score=affinity, rationale=rationale))

        scores.sort(key=lambda w: w.affinity_score, reverse=True)
        top = scores[0]
        sec = scores[1] if len(scores) > 1 else None
        is_mixed = bool(sec and (top.affinity_score - sec.affinity_score) <= 0.10)
        return ArchetypeAssessment(
            status="MIXED_PROFILE" if is_mixed else "SINGLE_DOMINANT",
            primary_archetype=top.archetype,
            secondary_archetype=sec.archetype if is_mixed and sec else None,
            weights=scores[:4],
            summary=(
                f"Mixed {top.archetype} / {sec.archetype} signature"
                if is_mixed and sec
                else f"Primary alignment: {top.archetype}"
            ) + (f" (provisional, n={match_count})" if match_count < 2 else f" (n={match_count} matches)"),
        )

    @staticmethod
    def _recommend_tactical_suitability(
        style: Dict[str, float],
        prof: Dict[str, float],
        cold_start: Optional[ColdStartPreferences],
    ) -> List[TacticalSuitabilityOption]:
        poss = style.get("possession_preference", 0.50)
        direct = style.get("attacking_directness", 0.50)
        width = style.get("wing_utilization", 0.50)
        press = style.get("pressing_intensity", 0.50)
        trans_mgmt = prof.get("defensive_transition_management", 0.65)
        compact = prof.get("defensive_compactness", 0.65)

        if not style and cold_start:
            poss = 0.72 if cold_start.preferred_tempo == "SLOW_POSSESSION" else (0.38 if cold_start.preferred_tempo == "FAST_DIRECT" else 0.55)
            width = 0.75 if cold_start.width_preference == "WIDE_WINGPLAY" else (0.35 if cold_start.width_preference == "NARROW_CENTRAL" else 0.55)
            press = 0.78 if cold_start.pressing_comfort == "HIGH_PRESS" else (0.30 if cold_start.pressing_comfort == "LOW_BLOCK" else 0.50)

        candidates = [
            TacticalSuitabilityOption(
                formation="4-2-3-1",
                tactical_profile="BALANCED" if trans_mgmt < 0.65 else ("HIGH_PRESS" if press >= 0.65 else "POSSESSION"),
                suitability_score=round(0.68 + (0.20 if trans_mgmt < 0.65 else 0.08) + 0.10 * poss - 0.05 * max(0.0, width - 0.75), 3),
                rationale="Double pivot stabilizes counter-attack transitions while preserving CAM central triangles.",
                recommended_roles=["LDM/RDM: Holding (Defend)", "CAM: Playmaker or Shadow Striker", "LB/RB: Fullback Balanced"],
            ),
            TacticalSuitabilityOption(
                formation="4-3-3",
                tactical_profile="POSSESSION" if poss >= 0.58 else "COUNTER_ATTACK",
                suitability_score=round(0.62 + 0.22 * width + 0.12 * direct, 3),
                rationale="Maximizes touchline width channels (LW/RW) while maintaining a single Holding CDM anchor.",
                recommended_roles=["CDM: Holding", "CM: Box-to-Box", "LW/RW: Inside Forward or Winger"],
            ),
            TacticalSuitabilityOption(
                formation="4-4-2",
                tactical_profile="COUNTER_ATTACK" if direct >= 0.60 else "MID_BLOCK",
                suitability_score=round(0.60 + 0.18 * (1.0 - compact) + 0.14 * direct, 3),
                rationale="Flat two-bank mid-block reduces horizontal stretching and supports dual-striker transitions.",
                recommended_roles=["LCM: Holding", "RCM: Deep-Lying Playmaker", "LST/RST: Poacher + False 9"],
            ),
        ]
        candidates.sort(key=lambda c: c.suitability_score, reverse=True)
        return candidates

    @staticmethod
    def _rank_improvements(
        prof: List[DimensionEstimate],
        style: List[DimensionEstimate],
    ) -> List[ImprovementPotentialItem]:
        items: List[ImprovementPotentialItem] = []
        focus_hints = {
            "defensive_transition_management": "Maintain 2+ rest-defense anchors ahead of counter channels; switch to CDM before engaging wide carriers.",
            "defensive_compactness": "Pull weak-side wide midfielders inward and keep defensive block height <= 60 until ball triggers activate.",
            "tactical_discipline": "Eliminate early CB step-outs; maintain central line alignment with Fullbacks recovering inside.",
            "decision_making_under_pressure": "Scan touchline/half-space outlets early rather than forcing passes into < 2.5m contested Zone 8 lanes.",
            "chance_creation": "Trigger third-man half-space runs beneath ST to elevate progressive passing xT gain.",
            "passing_risk": "Reduce central turnover exposure by recycling via deep-lying pivot when central corridors are blocked.",
        }
        for est in prof + [s for s in style if s.dimension == "passing_risk"]:
            if est.estimated_value is None:
                continue
            gap = (est.estimated_value if est.dimension == "passing_risk" else (1.0 - est.estimated_value))
            conf_factor = min(1.0, max(0.35, est.effective_sample_size / 8.0))
            prio = round(gap * conf_factor, 3)
            if prio >= 0.14:
                items.append(
                    ImprovementPotentialItem(
                        dimension=est.dimension,
                        priority_score=prio,
                        current_estimate=est.estimated_value,
                        reason=f"Observed {est.dimension.replace('_', ' ')} = {est.estimated_value:.2f} (n_eff={est.effective_sample_size:.1f}).",
                        recommended_focus=focus_hints.get(est.dimension, "Targeted situational drill review recommended."),
                    )
                )
        items.sort(key=lambda x: x.priority_score, reverse=True)
        return items[:5]

    @staticmethod
    def _cold_start_hints(prefs: ColdStartPreferences) -> List[str]:
        hints = [f"SOURCE: SELF_REPORTED_COLD_START (no verified gameplay yet; edition={prefs.game_version})"]
        if prefs.preferred_tempo == "FAST_DIRECT":
            hints.append("Self-reported fast/vertical tempo leans toward 4-4-2 or 4-2-3-1 Counter-Attack setups.")
        elif prefs.preferred_tempo == "SLOW_POSSESSION":
            hints.append("Self-reported patient build-up fits 4-3-3 Holding or 4-2-3-1 Possession triangles.")
        if prefs.pressing_comfort == "HIGH_PRESS":
            hints.append("High-press preference requires high stamina/interception midfielders and disciplined rest defense.")
        return hints
