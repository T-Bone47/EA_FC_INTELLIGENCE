"""Phase 40K -> Phase 42I Closed-Loop Longitudinal Progression & Pro Gamer DNA Schema Foundation."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.domain.phase40_models import (
    GamerDNAProfile,
    MatchIntelligenceRecord,
    ProgressionReport,
    ProgressionWindowSummary,
)

_DIAGNOSTIC_TO_SKILL: Dict[str, str] = {
    "UNNECESSARY_CB_DISPLACEMENT": "defensive_discipline",
    "EXPOSED_CENTRAL_CHANNEL": "pivot_screening",
    "RISKY_PASSING_DECISION": "progression_selection",
    "COUNTER_ATTACK_VULNERABILITY": "rest_defense",
    "ISOLATED_STRIKER": "width_switching",
    "POOR_PRESSING_TIMING": "pressing_discipline",
    "LOW_XG_SHOT_SELECTION": "finishing_selection",
    "CLOCK_MANAGEMENT_TURNOVER": "ball_retention",
    "PASS_SELECTION": "progression_selection",
    "DEFENSIVE_SWITCH": "defensive_discipline",
    "PRESS_TIMING": "pressing_discipline",
}


class PerformanceProgressionService:
    """Computes covariate-aware closed-loop progression (weakness -> drill -> subsequent matches)."""

    def evaluate(
        self,
        user_id: str,
        matches: List[MatchIntelligenceRecord],
        training_attempts: Optional[List[Dict[str, Any]]] = None,
    ) -> ProgressionReport:
        eligible = [m for m in matches if m.provenance != "SYNTHETIC_FIXTURE"]
        eligible_chrono = sorted(eligible, key=lambda m: m.created_at)

        attempts = training_attempts or []
        train_acc = None
        if attempts:
            train_acc = round(sum(1 for a in attempts if a.get("is_optimal_or_defensible")) / len(attempts), 3)

        windows: List[ProgressionWindowSummary] = []
        for label, count in [("LAST_5", 5), ("LAST_10", 10), ("LAST_20", 20)]:
            slice_m = eligible_chrono[-count:] if len(eligible_chrono) >= 1 else []
            if slice_m:
                windows.append(self._summarize_window(label, slice_m, train_acc))

        formations = sorted({m.formation for m in eligible_chrono})
        if len(formations) >= 2:
            for fm in formations[:3]:
                fm_matches = [m for m in eligible_chrono if m.formation == fm]
                if fm_matches:
                    windows.append(self._summarize_window(f"FORMATION:{fm}", fm_matches, None))

        warnings: List[str] = []
        patches = sorted({f"{m.game_version}:{m.game_patch}" for m in eligible_chrono})
        modes = sorted({m.gameplay_mode for m in eligible_chrono})
        squad_ids = sorted({str((m.feature_metrics or {}).get("squad_id") or m.formation) for m in eligible_chrono})
        opp_tiers = sorted({str((m.feature_metrics or {}).get("opponent_quality_proxy") or "UNKNOWN") for m in eligible_chrono})

        if len(patches) > 1:
            warnings.append(f"Patch heterogeneity ({', '.join(patches)}): gameplay tuning changes may confound raw before/after trends.")
        if len(formations) > 1:
            warnings.append(f"Formation shifts detected ({', '.join(formations)}): attribute deltas to both tactics and player habits cautiously.")
        if len(modes) > 1:
            warnings.append(f"Mixed gameplay modes ({', '.join(modes)}): opponent intensity differs across modes.")
        if len(eligible_chrono) < 3:
            warnings.append(f"Small sample size (n={len(eligible_chrono)} non-synthetic matches); treat progression signals as provisional.")

        trend_notes: List[str] = []
        if len(eligible_chrono) >= 2:
            first_half = eligible_chrono[: len(eligible_chrono) // 2]
            second_half = eligible_chrono[len(eligible_chrono) // 2 :]
            w1 = self._summarize_window("EARLY", first_half, None)
            w2 = self._summarize_window("RECENT", second_half, None)
            if w1.avg_mistake_rate is not None and w2.avg_mistake_rate is not None:
                delta = w2.avg_mistake_rate - w1.avg_mistake_rate
                trend_notes.append(
                    f"Mistake findings/match shifted by {delta:+.2f} between early half (n={len(first_half)}) and recent half (n={len(second_half)}). Correlation != proven causal improvement."
                )

        # Phase 42I Closed-Loop Weakness -> Drill -> Match Shift Tracking
        weakness_loop = self._compute_weakness_loops(eligible_chrono, attempts)
        covariates = {
            "patches": patches,
            "formations": formations,
            "gameplay_modes": modes,
            "squad_strata": squad_ids,
            "opponent_quality_buckets": opp_tiers,
            "homogeneous_patch_formation_comparable": len(patches) <= 1 and len(formations) <= 1 and len(eligible_chrono) >= 4,
        }

        return ProgressionReport(
            user_id=user_id,
            total_eligible_matches=len(eligible_chrono),
            windows=windows,
            comparability_warnings=warnings,
            trend_notes=trend_notes,
            weakness_loop_tracking=weakness_loop,
            covariate_summary=covariates,
            within_person_experiment_contract={
                "contract_version": "phase41.n_of_1.v1",
                "phase42_closed_loop_enabled": True,
                "minimum_baseline_matches": 3,
                "minimum_intervention_matches": 3,
                "control_covariates": [
                    "game_version",
                    "game_patch",
                    "gameplay_mode",
                    "formation",
                    "squad_strata",
                    "opponent_quality_proxy",
                    "observation_quality",
                ],
                "ready_for_tactical_ab": len(eligible_chrono) >= 6 and len(patches) == 1,
            },
        )

    def _compute_weakness_loops(
        self,
        eligible_chrono: List[MatchIntelligenceRecord],
        attempts: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not eligible_chrono:
            return []

        attempts_by_skill: Dict[str, List[Dict[str, Any]]] = {}
        for att in attempts:
            sk = str(att.get("skill_code") or "")
            if sk:
                attempts_by_skill.setdefault(sk, []).append(att)

        def _finding_code(f: Any) -> Optional[str]:
            return f.get("diagnostic_code") if isinstance(f, dict) else getattr(f, "diagnostic_code", None)

        all_codes = sorted({
            str(_finding_code(f))
            for m in eligible_chrono
            for f in (m.coaching_findings or [])
            if _finding_code(f)
        })
        if not all_codes:
            return []

        mid = max(1, len(eligible_chrono) // 2)
        early = eligible_chrono[:mid]
        recent = eligible_chrono[mid:] if len(eligible_chrono) > 1 else []

        def _rate_for_code(slice_matches: List[MatchIntelligenceRecord], code: str) -> Optional[float]:
            if not slice_matches:
                return None
            total_occ = 0.0
            total_opp = 0.0
            for m in slice_matches:
                fm = m.feature_metrics or {}
                base_opps = max(1.0, float(fm.get("transition_opportunities") or fm.get("observable_windows") or 10.0))
                occ = sum(1 for f in (m.coaching_findings or []) if _finding_code(f) == code)
                total_occ += occ
                total_opp += base_opps
            return round(total_occ / max(1.0, total_opp), 4)

        items: List[Dict[str, Any]] = []
        for code in all_codes:
            skill = _DIAGNOSTIC_TO_SKILL.get(code, "progression_selection")
            skill_atts = attempts_by_skill.get(skill, [])
            practice_acc = (
                round(sum(1 for a in skill_atts if a.get("is_optimal_or_defensible")) / len(skill_atts), 3)
                if skill_atts else None
            )
            latest_bkt_p = float(skill_atts[0]["posterior_p"]) if (skill_atts and skill_atts[0].get("posterior_p") is not None) else None

            early_rate = _rate_for_code(early, code)
            recent_rate = _rate_for_code(recent, code)
            delta = round(recent_rate - early_rate, 4) if (early_rate is not None and recent_rate is not None) else None

            if delta is None or len(eligible_chrono) < 3:
                verdict = "INSUFFICIENT_COMPARABLE_MATCHES"
            elif delta <= -0.04:
                verdict = "PROVISIONAL_IMPROVEMENT"
            elif delta >= 0.04:
                verdict = "PROVISIONAL_REGRESSION"
            else:
                verdict = "NO_MATERIAL_SHIFT"

            items.append({
                "diagnostic_code": code,
                "linked_skill_code": skill,
                "early_opportunity_rate": early_rate,
                "recent_opportunity_rate": recent_rate,
                "rate_delta": delta,
                "early_match_count": len(early),
                "recent_match_count": len(recent),
                "practice_attempts": len(skill_atts),
                "practice_accuracy": practice_acc,
                "latest_practice_bkt_p": latest_bkt_p,
                "verdict": verdict,
                "comparability_note": "Opportunity-normalized rate; verify patch/formation parity before attributing transfer.",
            })
        return items

    @staticmethod
    def _summarize_window(label: str, items: List[MatchIntelligenceRecord], train_acc: Optional[float]) -> ProgressionWindowSummary:
        n = len(items)
        avg_mistakes = round(sum(len(m.coaching_findings or []) for m in items) / n, 2)
        comp_vals = [float(m.feature_metrics["defensive_compactness"]) for m in items if "defensive_compactness" in (m.feature_metrics or {})]
        prog_vals = [float(m.feature_metrics["central_progression"]) for m in items if "central_progression" in (m.feature_metrics or {})]
        exp_rates = []
        for m in items:
            fm = m.feature_metrics or {}
            opps = max(1, int(fm.get("transition_opportunities", 4)))
            exp = int(fm.get("exposed_transitions", 0))
            exp_rates.append(min(1.0, exp / opps))

        return ProgressionWindowSummary(
            window_label=label,
            match_count=n,
            avg_mistake_rate=avg_mistakes,
            avg_defensive_compactness=round(sum(comp_vals) / len(comp_vals), 3) if comp_vals else None,
            avg_central_progression=round(sum(prog_vals) / len(prog_vals), 3) if prog_vals else None,
            avg_transition_exposure_rate=round(sum(exp_rates) / len(exp_rates), 3) if exp_rates else None,
            training_accuracy=train_acc,
            patches_present=sorted({f"{m.game_version}:{m.game_patch}" for m in items}),
            formations_present=sorted({m.formation for m in items}),
            modes_present=sorted({m.gameplay_mode for m in items}),
        )


def build_pro_dna_preview(profile: GamerDNAProfile, *, pro_dataset_verified: bool = False) -> Dict[str, Any]:
    """Phase 40L Feature-Gated Pro DNA Schema Foundation."""
    if not pro_dataset_verified:
        return {
            "feature_enabled": False,
            "status": "FEATURE_GATED_AWAITING_VERIFIED_PRO_DATASET",
            "policy": (
                "Generic tactical archetype similarity is shown instead of named pro-gamer similarity percentages. "
                "Style similarity remains strictly separate from execution proficiency."
            ),
            "generic_style_archetype": profile.archetype.primary_archetype,
            "secondary_archetype": profile.archetype.secondary_archetype,
            "named_pro_similarity_blocked": True,
        }
    return {
        "feature_enabled": True,
        "status": "READY",
        "generic_style_archetype": profile.archetype.primary_archetype,
        "named_pro_similarity_blocked": False,
    }
