"""Phase 43F: Personal Formation Recommendation Engine.

Evaluates formation suitability strictly per-user & edition/patch by combining:
1. Theoretical alignment against Gamer DNA style/proficiency dimensions & Whole-XI roles
2. Observed personal match performance per formation (when available)
3. Validated Phase 43 experiment outcomes (when completed cleanly)

Preserves frozen V3.2.1 math and explicitly refuses to claim guaranteed wins.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.domain.phase43_models import (
    EvidenceGrade,
    FormationComparisonReport,
    FormationSuitabilityItem,
    PersonalFormationRecommendation,
)
from backend.repositories.phase40_repository import Phase40Repository, get_phase40_repository
from backend.repositories.phase41_repository import Phase41Repository, get_phase41_repository
from backend.repositories.phase43_repository import Phase43Repository, get_phase43_repository
from backend.services.football_iq_engine import FootballIQEngine
from backend.services.formations import FORMATION_SLOTS, slots_for
from backend.services.gamer_dna_engine import GamerDNAEngine
from backend.services.recurring_mistake_analyzer import RecurringMistakeAnalyzer


_FORMATION_TRAITS: Dict[str, Dict[str, Any]] = {
    "4-2-3-1": {
        "profile": "POSSESSION / BALANCED",
        "roles": ["LDM Holding (Defend)", "RDM Deep-Lying Playmaker (Build-Up)", "CAM Playmaker"],
        "strengths": ["Double pivot shields counter-attacks", "Central triangle progression"],
        "risks": ["Lone ST can become isolated if LAM/RAM stay wide"],
        "rest_defense": 0.88,
        "width_bias": 0.62,
        "central_bias": 0.78,
        "press_support": 0.68,
    },
    "4-3-3": {
        "profile": "BALANCED / HIGH_PRESS",
        "roles": ["CDM Holding (Defend)", "RCM Playmaker (Attack)", "LW/RW Inside Forward"],
        "strengths": ["High pressing front-three triggers", "Wide touchline stretching"],
        "risks": ["Single pivot exposed when both CMs push high"],
        "rest_defense": 0.64,
        "width_bias": 0.85,
        "central_bias": 0.62,
        "press_support": 0.84,
    },
    "4-4-2": {
        "profile": "COUNTER_ATTACK / DIRECT_PLAY",
        "roles": ["LCM/RCM Box-to-Box or Holding", "LM/RM Inside Forward or Wide Midfielder", "LST/RST Dual Strikers"],
        "strengths": ["Dual strikers stretch CB pairs", "Two compact banks of four out of possession"],
        "risks": ["Can be outnumbered in Zone 8 against 3-midfield shapes"],
        "rest_defense": 0.78,
        "width_bias": 0.76,
        "central_bias": 0.56,
        "press_support": 0.72,
    },
    "4-3-2-1": {
        "profile": "DIRECT_PLAY / HALF_SPACE_OVERLOAD",
        "roles": ["CM Holding (Middle)", "LCM/RCM Box-to-Box", "LAM/RAM Half-Space Shadow Strikers"],
        "strengths": ["Dense central & half-space combinations behind ST", "Smooth conversion between 4-3-2-1 attack and 4-4-2 mid-block"],
        "risks": ["Needs overlapping fullbacks to prevent predictability against low blocks"],
        "rest_defense": 0.72,
        "width_bias": 0.48,
        "central_bias": 0.88,
        "press_support": 0.78,
    },
    "4-5-1": {
        "profile": "POSSESSION / CONTROLLED_BLOCK",
        "roles": ["CM Holding Anchor", "LCAM/RCAM Half-Space Creators", "LM/RM Track-Back Wide Midfielders"],
        "strengths": ["5-player midfield screen disrupts opposition central lanes", "Two CAMs occupy half-spaces"],
        "risks": ["Single striker risks isolation during fast clearances"],
        "rest_defense": 0.76,
        "width_bias": 0.70,
        "central_bias": 0.74,
        "press_support": 0.66,
    },
    "4-2-2-2": {
        "profile": "COUNTER_ATTACK / BALANCED",
        "roles": ["LDM/RDM Holding + DLP", "LAM/RAM Half-Space Playmaker", "Two Mobile Strikers"],
        "strengths": ["Strong rest defense + rapid vertical dual-striker transitions"],
        "risks": ["Requires fullbacks or wide CAMs for flank width"],
        "rest_defense": 0.86,
        "width_bias": 0.58,
        "central_bias": 0.80,
        "press_support": 0.70,
    },
    "4-1-2-1-2": {
        "profile": "POSSESSION / DIRECT_PLAY",
        "roles": ["CDM Holding", "CAM Shadow Striker / Playmaker", "Wingbacks for width"],
        "strengths": ["Dense central passing triangles"],
        "risks": ["Exposed flanks if narrow LCM/RCM fail to shuffle wide"],
        "rest_defense": 0.68,
        "width_bias": 0.35,
        "central_bias": 0.92,
        "press_support": 0.74,
    },
    "3-5-2": {
        "profile": "HIGH_PRESS / COUNTER_ATTACK",
        "roles": ["3 CBs (Ball-Playing + Stopper)", "CDM Holding", "RM/LM Winger Track-Back"],
        "strengths": ["Central numerical overload + counter-attack outlets"],
        "risks": ["Wide channels vulnerable behind wingbacks on turnovers"],
        "rest_defense": 0.66,
        "width_bias": 0.82,
        "central_bias": 0.76,
        "press_support": 0.78,
    },
    "3-4-2-1": {
        "profile": "HIGH_PRESS / BOX_MIDFIELD",
        "roles": ["3 CBs (Sweep + Wide Stoppers)", "LCM/RCM Pivot", "LCAM/RCAM Inside Forwards", "LM/RM Wingbacks"],
        "strengths": ["3-2-5 in-possession box midfield superiority", "Multiple diagonal outlets"],
        "risks": ["Exposed flank transition channels if both LM/RM push high simultaneously"],
        "rest_defense": 0.65,
        "width_bias": 0.80,
        "central_bias": 0.82,
        "press_support": 0.82,
    },
    "3-4-3": {
        "profile": "WING_OVERLOAD / HIGH_PRESS",
        "roles": ["3 CBs", "LCM/RCM Pivot", "LM/RM Wingbacks + LW/RW Wide Forwards"],
        "strengths": ["Double-width flank triangles overwhelm 4-back defenses", "Aggressive high counter-press"],
        "risks": ["2-man central midfield can be played through centrally on transitions"],
        "rest_defense": 0.58,
        "width_bias": 0.92,
        "central_bias": 0.54,
        "press_support": 0.86,
    },
    "5-3-2": {
        "profile": "LOW_BLOCK / COUNTER_ATTACK",
        "roles": ["LWB/RWB Transition Wingbacks", "CM Holding + Box-to-Box", "Dual Counter Strikers"],
        "strengths": ["5-defender backline compactness", "Safe two-striker counter outlets"],
        "risks": ["Low sustained final-third territory unless wingbacks join early"],
        "rest_defense": 0.92,
        "width_bias": 0.64,
        "central_bias": 0.58,
        "press_support": 0.52,
    },
    "5-2-1-2": {
        "profile": "REST_DEFENSE / VERTICAL_COUNTER",
        "roles": ["3 CBs + Fullback Defensive Coverage", "CAM Playmaker", "Dual Strikers"],
        "strengths": ["Tight central defensive screen", "Direct triangle between CAM and two STs"],
        "risks": ["2-CM line relies heavily on stamina to cover horizontal width"],
        "rest_defense": 0.90,
        "width_bias": 0.56,
        "central_bias": 0.76,
        "press_support": 0.55,
    },
}


class PersonalFormationEngine:
    """Ranks formations using Gamer DNA, fingerprints, Football IQ, empirical match evidence & experiments."""

    def __init__(
        self,
        p40_repo: Optional[Phase40Repository] = None,
        p43_repo: Optional[Phase43Repository] = None,
        p41_repo: Optional[Phase41Repository] = None,
    ) -> None:
        self.p40_repo = p40_repo or get_phase40_repository()
        self.p43_repo = p43_repo or get_phase43_repository()
        self.p41_repo = p41_repo or get_phase41_repository()
        self.dna_engine = GamerDNAEngine()
        self.mistake_analyzer = RecurringMistakeAnalyzer()
        self.iq_engine = FootballIQEngine()

    def recommend_formations(
        self,
        user_id: str,
        *,
        game_version: str = "FC27",
        game_patch: str = "PATCH_1.04",
        top_k: int = 12,
    ) -> PersonalFormationRecommendation:
        uid = str(user_id)
        gv = "FC26" if game_version.upper() == "FC26" else "FC27"
        matches = self.p40_repo.list_matches(uid, game_version=gv, exclude_synthetic=True, limit=100)
        patch_matches = [m for m in matches if m.game_patch == game_patch] or matches
        cold = self.p40_repo.get_cold_start_preferences(uid)
        dna = self.dna_engine.build_profile(uid, patch_matches, cold_start=cold, patch_scope=game_patch)
        mistakes = self.mistake_analyzer.analyze(patch_matches)
        decision_wins = self.p41_repo.list_decision_windows(uid, exclude_synthetic=True, limit=60)
        iq_profile = self.iq_engine.compute_profile(uid, decision_wins) if decision_wins else None
        fingerprints = self.p43_repo.list_fingerprints(uid, game_version=gv, limit=40)
        exps = self.p43_repo.list_experiments(uid, game_version=gv, limit=30)
        snapshots = self.p43_repo.list_snapshots(uid, game_version=gv, limit=25)

        style = {d.dimension: float(d.estimated_value) for d in dna.style_dimensions if d.estimated_value is not None}
        prof = {d.dimension: float(d.estimated_value) for d in dna.proficiency_dimensions if d.estimated_value is not None}

        wing_pref = style.get("wing_utilization", 0.50)
        central_pref = style.get("central_progression", 0.50)
        press_pref = style.get("pressing_intensity", 0.50)
        trans_def_prof = prof.get("defensive_transition_management", 0.60)
        transition_weakness = any(getattr(w, "weakness_type", "") == "TRANSITION_EXPOSURE" for w in mistakes)
        avg_iq = float(iq_profile.overall_football_iq) if (iq_profile and iq_profile.overall_football_iq is not None) else None

        # Role familiarity bonus from user's saved tactical snapshots per formation
        form_role_bonus: Dict[str, float] = {}
        for sn in snapshots:
            if not sn.slots:
                continue
            plus_cnt = sum(1 for sl in sn.slots if sl.role_familiarity in ("ROLE_PLUS", "ROLE_PLUS_PLUS"))
            form_role_bonus[sn.formation] = max(form_role_bonus.get(sn.formation, 0.0), round(plus_cnt / max(1, len(sn.slots)) * 0.05, 4))

        # Group observed matches & tactical fingerprints by formation
        by_form: Dict[str, List[float]] = {}
        for m in patch_matches:
            fm = m.feature_metrics or {}
            opps = fm.get("transition_opportunities")
            exp_t = fm.get("exposed_transitions")
            if isinstance(opps, (int, float)) and opps > 0 and isinstance(exp_t, (int, float)):
                by_form.setdefault(m.formation, []).append(max(0.0, 1.0 - float(exp_t) / float(opps)))
            elif isinstance(fm.get("defensive_compactness"), (int, float)):
                by_form.setdefault(m.formation, []).append(float(fm["defensive_compactness"]))

        fp_by_form: Dict[str, List[float]] = {}
        for fp in fingerprints:
            if fp.provenance == "SYNTHETIC_FIXTURE" or fp.coverage_pct < 35.0:
                continue
            out_m = next((p.metrics for p in fp.phases if p.phase == "OUT_OF_POSSESSION"), {})
            comp = out_m.get("defensive_compactness")
            if isinstance(comp, (int, float)):
                fp_by_form.setdefault(fp.nominal_formation, []).append(float(comp))

        # Track controlled experiment outcomes per formation cleanly
        exp_wins: Dict[str, int] = {}
        exp_trials: Dict[str, int] = {}
        for e in exps:
            if e.analysis:
                for af in (e.analysis.arm_a.formation, e.analysis.arm_b.formation):
                    exp_trials[af] = exp_trials.get(af, 0) + 1
                if e.analysis.verdict.value == "SUPPORTED_IMPROVEMENT":
                    win_form = e.analysis.arm_b.formation
                    exp_wins[win_form] = exp_wins.get(win_form, 0) + 1
                elif e.analysis.verdict.value == "SUPPORTED_REGRESSION":
                    win_form = e.analysis.arm_a.formation
                    exp_wins[win_form] = exp_wins.get(win_form, 0) + 1

        ranked: List[FormationSuitabilityItem] = []
        for fname, meta in _FORMATION_TRAITS.items():
            if fname not in FORMATION_SLOTS:
                continue
            rest_need = 0.88 if (trans_def_prof < 0.55 or transition_weakness) else 0.58
            theo = (
                0.30 * (1.0 - abs(wing_pref - meta["width_bias"]))
                + 0.30 * (1.0 - abs(central_pref - meta["central_bias"]))
                + 0.25 * (1.0 - abs(rest_need - meta["rest_defense"]))
                + 0.15 * (1.0 - abs(press_pref - meta["press_support"]))
                + form_role_bonus.get(fname, 0.0)
            )
            if cold and cold.preferred_formation == fname:
                theo += 0.04
            theo = round(max(0.05, min(0.99, theo)), 4)

            obs_list = by_form.get(fname, []) + fp_by_form.get(fname, [])
            obs_avg = round(sum(obs_list) / len(obs_list), 3) if obs_list else None
            w_cnt = exp_wins.get(fname, 0)
            t_cnt = exp_trials.get(fname, 0)
            exp_signal = round(min(0.98, 0.55 + 0.18 * w_cnt), 3) if w_cnt > 0 else (0.50 if t_cnt > 0 else None)

            if w_cnt > 0:
                grade = EvidenceGrade.CONTROLLED_EXPERIMENT_EVIDENCE
            elif len(obs_list) >= 2:
                grade = EvidenceGrade.OBSERVED_ASSOCIATION
            else:
                grade = EvidenceGrade.THEORETICAL_SUITABILITY

            composite = theo + (0.06 * w_cnt) + (0.04 * (obs_avg - 0.5) if obs_avg is not None else 0.0)
            conf = min(0.95, 0.35 + 0.07 * len(obs_list) + 0.14 * w_cnt)
            rationale = (
                f"Theoretical fit={theo:.2f} for {dna.archetype.primary_archetype}"
                + (f" (Football IQ avg={avg_iq:.1f})" if avg_iq is not None else "")
                + (f"; observed across {len(obs_list)} record(s) (stability={obs_avg:.2f})" if obs_list else "; no personal matches logged in this shape yet")
                + (f"; {w_cnt} validated experiment win(s)." if w_cnt else ".")
            )
            ranked.append(
                FormationSuitabilityItem(
                    formation=fname,
                    tactical_profile=meta["profile"],
                    theoretical_score=round(max(0.05, min(0.99, composite)), 4),
                    theoretical_fit=theo,
                    observed_performance=obs_avg,
                    controlled_experiment_evidence=exp_signal,
                    observed_match_count=len(by_form.get(fname, [])),
                    observed_avg_delta=obs_avg,
                    experiment_wins=w_cnt,
                    confidence=round(conf, 3),
                    recommended_roles=list(meta["roles"]),
                    strengths=list(meta["strengths"]),
                    risks=list(meta["risks"]),
                    signal_notes={
                        "THEORETICAL_SUITABILITY": f"Derived from Gamer DNA ({dna.archetype.primary_archetype}), slot familiarity, and transition needs.",
                        "OBSERVED_PERFORMANCE": f"{len(obs_list)} match/fingerprint stability points." if obs_list else "Not observed in personal matches yet.",
                        "CONTROLLED_EXPERIMENT_EVIDENCE": f"{w_cnt} win(s) across {t_cnt} experiment(s)." if t_cnt else "No completed controlled experiment yet.",
                    },
                    evidence_grade=grade,
                    rationale=rationale,
                )
            )

        ranked.sort(key=lambda x: (x.experiment_wins, x.theoretical_score), reverse=True)
        return PersonalFormationRecommendation(
            user_id=uid,
            game_version=gv,  # type: ignore[arg-type]
            game_patch=game_patch,
            frozen_v321_preserved=True,
            eligible_match_count=len(patch_matches),
            ranked_formations=ranked[:top_k],
            caveat=(
                "Formation recommendations remain advisory estimates combining Gamer DNA style fit and available "
                "match/experiment observations; they never alter frozen V3.2.1 player weights or guarantee match outcomes."
            ),
        )

    def compare_formations(
        self,
        user_id: str,
        formation_a: str,
        formation_b: str,
        *,
        game_version: str = "FC27",
        game_patch: str = "PATCH_1.04",
    ) -> FormationComparisonReport:
        uid = str(user_id)
        fa = formation_a.strip()
        fb = formation_b.strip()
        if fa not in FORMATION_SLOTS or fb not in FORMATION_SLOTS:
            raise ValueError(f"Unsupported formation comparison ({fa} vs {fb}); valid formations: {sorted(FORMATION_SLOTS)}")

        rec = self.recommend_formations(uid, game_version=game_version, game_patch=game_patch, top_k=len(FORMATION_SLOTS))
        by_name = {f.formation: f for f in rec.ranked_formations}
        item_a = by_name[fa]
        item_b = by_name[fb]
        traits_a = _FORMATION_TRAITS[fa]
        traits_b = _FORMATION_TRAITS[fb]
        slots_a = [s.slot for s in slots_for(fa)]
        slots_b = [s.slot for s in slots_for(fb)]

        diffs = [
            f"Rest-defense structural baseline: {fa}={traits_a['rest_defense']:.2f} vs {fb}={traits_b['rest_defense']:.2f}",
            f"Flank width vs central density: {fa} (width={traits_a['width_bias']:.2f}, central={traits_a['central_bias']:.2f}) vs {fb} (width={traits_b['width_bias']:.2f}, central={traits_b['central_bias']:.2f})",
            f"Unique to {fa}: {sorted(set(slots_a) - set(slots_b))}; unique to {fb}: {sorted(set(slots_b) - set(slots_a))}",
        ]
        preferred = fa if (item_a.experiment_wins, item_a.theoretical_score) >= (item_b.experiment_wins, item_b.theoretical_score) else fb
        grade = (
            EvidenceGrade.CONTROLLED_EXPERIMENT_EVIDENCE
            if (item_a.experiment_wins > 0 or item_b.experiment_wins > 0)
            else (
                EvidenceGrade.OBSERVED_ASSOCIATION
                if (item_a.observed_match_count > 0 or item_b.observed_match_count > 0)
                else EvidenceGrade.THEORETICAL_SUITABILITY
            )
        )
        return FormationComparisonReport(
            user_id=uid,
            game_version=rec.game_version,
            game_patch=game_patch,
            formation_a=item_a,
            formation_b=item_b,
            structural_differences=diffs,
            preferred_formation=preferred,
            evidence_grade=grade,
            summary=(
                f"{preferred} currently leads between {fa} (fit={item_a.theoretical_fit:.2f}, obs={item_a.observed_match_count} matches) "
                f"and {fb} (fit={item_b.theoretical_fit:.2f}, obs={item_b.observed_match_count} matches)."
            ),
            caveat=rec.caveat,
        )
