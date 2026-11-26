"""Phase 43H: Tactical Counterfactual & Hypothetical Configuration Workspace Service.

Evaluates two TacticalConfigurationSnapshots side-by-side purely at the modeled
tactical/role/cohesion/spatial-geometry level BEFORE playing live matches.
Strictly tagged `THEORETICAL_SUITABILITY` so gamers never mistake a counterfactual
simulation for confirmed match evidence.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.domain.phase43_models import EvidenceGrade, TacticalCounterfactualComparison
from backend.repositories.phase43_repository import Phase43Repository, get_phase43_repository
from backend.services.formations import PROFILE_DIMENSIONS


class TacticalCounterfactualService:
    """Computes theoretical configuration deltas between two immutable tactical snapshots."""

    def __init__(self, repo: Optional[Phase43Repository] = None) -> None:
        self.repo = repo or get_phase43_repository()

    def compare_snapshots(
        self,
        user_id: str,
        baseline_snapshot_id: str,
        variant_snapshot_id: str,
    ) -> TacticalCounterfactualComparison:
        uid = str(user_id)
        snap_a = self.repo.get_snapshot(uid, baseline_snapshot_id)
        snap_b = self.repo.get_snapshot(uid, variant_snapshot_id)

        if snap_a.game_version != snap_b.game_version:
            raise ValueError("Cannot compare tactical snapshots across FC26 and FC27 edition walls.")

        deltas: List[Dict[str, Any]] = []
        if snap_a.formation != snap_b.formation:
            deltas.append({"dimension": "formation", "baseline": snap_a.formation, "variant": snap_b.formation})
        if snap_a.tactical_profile != snap_b.tactical_profile:
            deltas.append({"dimension": "tactical_profile", "baseline": snap_a.tactical_profile, "variant": snap_b.tactical_profile})
        if snap_a.build_up_style != snap_b.build_up_style:
            deltas.append({"dimension": "build_up_style", "baseline": snap_a.build_up_style or "UNKNOWN", "variant": snap_b.build_up_style or "UNKNOWN"})
        if snap_a.defensive_approach != snap_b.defensive_approach:
            deltas.append({"dimension": "defensive_approach", "baseline": snap_a.defensive_approach or "UNKNOWN", "variant": snap_b.defensive_approach or "UNKNOWN"})
        if snap_a.line_height != snap_b.line_height:
            deltas.append({"dimension": "line_height", "baseline": snap_a.line_height, "variant": snap_b.line_height})
        if snap_a.width_setting != snap_b.width_setting:
            deltas.append({"dimension": "width_setting", "baseline": snap_a.width_setting, "variant": snap_b.width_setting})

        dim_a = PROFILE_DIMENSIONS.get(snap_a.tactical_profile.upper(), {"press_intensity": 0.5, "directness": 0.5, "width": 0.5})
        dim_b = PROFILE_DIMENSIONS.get(snap_b.tactical_profile.upper(), {"press_intensity": 0.5, "directness": 0.5, "width": 0.5})

        press_a = float(snap_a.line_height / 100.0) if snap_a.line_height is not None else float(dim_a.get("press_intensity", 0.5))
        press_b = float(snap_b.line_height / 100.0) if snap_b.line_height is not None else float(dim_b.get("press_intensity", 0.5))
        # Rest defense risk increases with higher line/press unless double-pivot protection added
        piv_a = 1 if ("4-2-" in snap_a.formation or "4-4-2" in snap_a.formation) else 0
        piv_b = 1 if ("4-2-" in snap_b.formation or "4-4-2" in snap_b.formation) else 0
        rest_risk_delta = round((press_b - press_a) * 0.45 - (piv_b - piv_a) * 0.14, 4)

        prog_delta = round(
            (float(dim_b.get("directness", 0.5)) - float(dim_a.get("directness", 0.5))) * 0.25
            + ((float(snap_b.width_setting or 50) - float(snap_a.width_setting or 50)) / 100.0) * 0.15,
            4,
        )

        coh_a = float((snap_a.cohesion_summary or {}).get("overall_synergy_score") or (snap_a.cohesion_summary or {}).get("tactical_alignment_index") or 0.65)
        coh_b = float((snap_b.cohesion_summary or {}).get("overall_synergy_score") or (snap_b.cohesion_summary or {}).get("tactical_alignment_index") or 0.65)
        coh_delta = round(coh_b - coh_a, 4)

        part_a = float((snap_a.partnership_summary or {}).get("synergy_score") or 0.65)
        part_b = float((snap_b.partnership_summary or {}).get("synergy_score") or 0.65)
        part_delta = round(part_b - part_a, 4)

        gaps: List[str] = []
        for sl in snap_b.slots:
            if sl.assigned_role and sl.role_familiarity in ("BASE", "UNKNOWN"):
                gaps.append(f"{sl.slot_position} ({sl.player_name or 'Slot'}): {sl.assigned_role} has {sl.role_familiarity} familiarity (no Role+/Role++ verified).")

        # Spatial zone geometry estimates explicitly marked by epistemic tier
        width_a = float(snap_a.width_setting) if snap_a.width_setting is not None else float(dim_a.get("width", 0.5) * 100.0)
        width_b = float(snap_b.width_setting) if snap_b.width_setting is not None else float(dim_b.get("width", 0.5) * 100.0)
        height_a = float(snap_a.line_height) if snap_a.line_height is not None else float(dim_a.get("block_height", 0.5) * 100.0)
        height_b = float(snap_b.line_height) if snap_b.line_height is not None else float(dim_b.get("block_height", 0.5) * 100.0)

        narrow_a = 1 if ("4-1-2-1-2" in snap_a.formation or "4-3-2-1" in snap_a.formation) else 0
        narrow_b = 1 if ("4-1-2-1-2" in snap_b.formation or "4-3-2-1" in snap_b.formation) else 0
        zone_geometry_deltas = {
            "passing_outlets_delta": round((width_b - width_a) / 200.0 + (piv_a - piv_b) * 0.04, 4),
            "zone14_overloads_delta": round((narrow_b - narrow_a) * 0.14 + (piv_a - piv_b) * 0.06, 4),
            "midfield_congestion_delta": round((narrow_b - narrow_a) * 0.18 + (50.0 - width_b) / 400.0 - (50.0 - width_a) / 400.0, 4),
            "attacking_width_delta_m": round((width_b - width_a) * 0.45, 2),
            "defensive_coverage_delta": round((piv_b - piv_a) * 0.12 - (height_b - height_a) / 350.0, 4),
            "transition_exposure_delta": rest_risk_delta,
            "role_conflicts_count": len(gaps),
            "spatial_occupation_shift": f"line_height {height_a:.0f}->{height_b:.0f}, width {width_a:.0f}->{width_b:.0f}",
        }

        epistemic_classification = {
            "snapshot_metadata_and_slots": "ACTUAL_OBSERVED",
            "rest_defense_and_width_deltas": "HYPOTHETICAL_MODELED",
            "passing_outlets_and_overloads": "HEURISTIC_MOVEMENT",
            "future_match_win_rate_and_stamina": "UNSUPPORTED_ASSUMPTION",
        }

        sensitivity_sweep: List[Dict[str, Any]] = []
        for dh in (-10, 0, 10):
            for dw in (-10, 0, 10):
                eff_h = max(1.0, min(100.0, height_b + dh))
                eff_w = max(1.0, min(100.0, width_b + dw))
                r_risk = round(((eff_h / 100.0) - press_a) * 0.45 - (piv_b - piv_a) * 0.14, 4)
                p_lane = round((float(dim_b.get("directness", 0.5)) - float(dim_a.get("directness", 0.5))) * 0.25 + ((eff_w - width_a) / 100.0) * 0.15, 4)
                sensitivity_sweep.append(
                    {
                        "line_height": int(eff_h),
                        "width_setting": int(eff_w),
                        "rest_defense_risk_delta": r_risk,
                        "progression_lane_delta": p_lane,
                    }
                )

        summary = (
            f"Hypothetical comparison ({snap_a.label} -> {snap_b.label}): "
            f"modeled rest-defense risk shift={rest_risk_delta:+.3f}, "
            f"progression lane shift={prog_delta:+.3f}, whole-XI alignment shift={coh_delta:+.3f}."
        )
        return TacticalCounterfactualComparison(
            baseline_snapshot_id=snap_a.snapshot_id,
            variant_snapshot_id=snap_b.snapshot_id,
            deltas=deltas,
            rest_defense_risk_delta=rest_risk_delta,
            progression_lane_delta=prog_delta,
            cohesion_delta=coh_delta,
            partnership_delta=part_delta,
            zone_geometry_deltas=zone_geometry_deltas,
            epistemic_classification=epistemic_classification,
            sensitivity_sweep=sensitivity_sweep,
            role_familiarity_gaps=gaps,
            summary=summary,
            evidence_grade=EvidenceGrade.THEORETICAL_SUITABILITY,
        )
