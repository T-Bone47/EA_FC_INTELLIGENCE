"""Phase 43J: Personal Meta Intelligence Foundation (Patch- & Edition-Isolated).

Computes empirical effectiveness breakdown across a specific user's real matches
strictly partitioned by `(user_id, game_version, game_patch)`.
Never alters frozen V3.2.1 player weights and never claims patch-agnostic global meta truth.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend.domain.phase43_models import (
    PersonalMetaProfile,
    RecommendationFeedbackCreate,
    RecommendationFeedbackRecord,
)
from backend.repositories.phase40_repository import Phase40Repository, get_phase40_repository
from backend.repositories.phase43_repository import Phase43Repository, get_phase43_repository


class PersonalMetaService:
    """Computes & persists isolated per-user, per-edition, per-patch empirical meta profiles."""

    def __init__(
        self,
        p40_repo: Optional[Phase40Repository] = None,
        p43_repo: Optional[Phase43Repository] = None,
    ) -> None:
        self.p40_repo = p40_repo or get_phase40_repository()
        self.p43_repo = p43_repo or get_phase43_repository()

    def build_profile(
        self,
        user_id: str,
        *,
        game_version: str = "FC27",
        game_patch: str = "PATCH_1.04",
        save: bool = True,
    ) -> PersonalMetaProfile:
        uid = str(user_id)
        gv = "FC26" if game_version.upper() == "FC26" else "FC27"
        patch = game_patch.strip() or "PATCH_1.04"

        all_user_matches = self.p40_repo.list_matches(uid, game_version=gv, exclude_synthetic=False, limit=150)
        synth_excl = sum(1 for m in all_user_matches if m.provenance == "SYNTHETIC_FIXTURE")
        patch_matches = [m for m in all_user_matches if m.provenance != "SYNTHETIC_FIXTURE" and m.game_patch == patch]

        exps_all = self.p43_repo.list_experiments(uid, game_version=gv, limit=50)
        exps = [
            e for e in exps_all
            if e.baseline_patch == patch and e.analysis and e.analysis.verdict.value in ("SUPPORTED_IMPROVEMENT", "SUPPORTED_REGRESSION", "NO_CLEAR_DIFFERENCE")
        ]
        snapshots = self.p43_repo.list_snapshots(uid, game_version=gv, limit=40)
        feedback_items = self.p43_repo.list_recommendation_feedback(uid, game_version=gv, limit=50)

        # Effective player role combinations & successful partnerships from user's verified snapshots
        role_combo_counts: Dict[Tuple[str, str], Dict[str, Any]] = {}
        partner_entries: List[Dict[str, Any]] = []
        for sn in snapshots:
            if sn.game_patch != patch:
                continue
            for sl in sn.slots:
                if sl.assigned_role:
                    key = (sl.slot_position, sl.assigned_role)
                    entry = role_combo_counts.setdefault(key, {"position": sl.slot_position, "role": sl.assigned_role, "focus": sl.role_focus, "snapshot_count": 0, "role_plus_or_pp": 0})
                    entry["snapshot_count"] += 1
                    if sl.role_familiarity in ("ROLE_PLUS", "ROLE_PLUS_PLUS"):
                        entry["role_plus_or_pp"] += 1
            if sn.partnership_summary and isinstance(sn.partnership_summary.get("synergy_score"), (int, float)):
                if float(sn.partnership_summary["synergy_score"]) >= 0.65:
                    partner_entries.append(
                        {
                            "snapshot_id": sn.snapshot_id,
                            "formation": sn.formation,
                            "synergy_score": round(float(sn.partnership_summary["synergy_score"]), 4),
                            "pair_label": sn.partnership_summary.get("pair_label") or sn.label,
                        }
                    )

        # Patch-dependent behaviour summary across patches WITHOUT conflating data across patches
        patch_summary_map: Dict[str, Dict[str, Any]] = {}
        for m in all_user_matches:
            if m.provenance == "SYNTHETIC_FIXTURE":
                continue
            p_slot = patch_summary_map.setdefault(m.game_patch, {"game_patch": m.game_patch, "match_count": 0, "formations": {}, "is_active_patch": m.game_patch == patch})
            p_slot["match_count"] += 1
            p_slot["formations"][m.formation] = p_slot["formations"].get(m.formation, 0) + 1
        patch_dependent_behaviour = list(patch_summary_map.values())

        exp_history = [
            {
                "experiment_id": e.experiment_id,
                "title": e.title,
                "experiment_type": e.experiment_type.value,
                "game_patch": e.baseline_patch,
                "status": e.status.value,
                "verdict": e.analysis.verdict.value if e.analysis else "PENDING",
                "raw_delta": e.analysis.raw_delta_b_minus_a if e.analysis else None,
            }
            for e in exps_all[:20]
        ]

        by_form: Dict[str, Dict[str, Any]] = {}
        vuln_counts: Dict[str, int] = {}

        for m in patch_matches:
            slot = by_form.setdefault(
                m.formation,
                {"formation": m.formation, "matches": 0, "wins": 0, "draws": 0, "losses": 0, "trans_rates": [], "compactness": []},
            )
            slot["matches"] += 1
            out = (m.match_result.outcome or "").upper()
            if out == "WIN":
                slot["wins"] += 1
            elif out == "DRAW":
                slot["draws"] += 1
            elif out == "LOSS":
                slot["losses"] += 1

            fm = m.feature_metrics or {}
            opps = fm.get("transition_opportunities")
            ex = fm.get("exposed_transitions")
            if isinstance(opps, (int, float)) and opps > 0 and isinstance(ex, (int, float)):
                slot["trans_rates"].append(float(ex) / float(opps))
            if isinstance(fm.get("defensive_compactness"), (int, float)):
                slot["compactness"].append(float(fm["defensive_compactness"]))

            opp_arch = str(m.opponent_context.get("archetype") or "").strip()
            if opp_arch and out == "LOSS":
                vuln_counts[opp_arch] = vuln_counts.get(opp_arch, 0) + 1
            for f in m.coaching_findings:
                code = str(f.get("code") or f.get("diagnostic_code") or "")
                if code:
                    vuln_counts[code] = vuln_counts.get(code, 0) + 1

        breakdown: List[Dict[str, Any]] = []
        best_sys: Optional[str] = None
        best_score = -1.0
        for form, st in by_form.items():
            mean_tr = round(sum(st["trans_rates"]) / len(st["trans_rates"]), 4) if st["trans_rates"] else None
            mean_cmp = round(sum(st["compactness"]) / len(st["compactness"]), 4) if st["compactness"] else None
            win_share = (st["wins"] + 0.5 * st["draws"]) / max(1, st["matches"])
            stab = (1.0 - mean_tr) if mean_tr is not None else (mean_cmp if mean_cmp is not None else 0.5)
            score = 0.55 * stab + 0.45 * win_share
            if st["matches"] >= 2 and score > best_score:
                best_score = score
                best_sys = form
            breakdown.append(
                {
                    "formation": form,
                    "matches": st["matches"],
                    "wins": st["wins"],
                    "draws": st["draws"],
                    "losses": st["losses"],
                    "mean_conceded_transition_rate": mean_tr,
                    "mean_defensive_compactness": mean_cmp,
                }
            )
        breakdown.sort(key=lambda b: b["matches"], reverse=True)
        vulnerable = [k for k, _ in sorted(vuln_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]]

        lims = [
            f"Strictly isolated to user={uid[:8]}…, edition={gv}, patch={patch}; never transferred across patches or editions.",
            "Frozen V3.2.1 player scoring weights remain completely unaltered.",
        ]
        if len(patch_matches) < 3:
            lims.append(f"Only {len(patch_matches)} verified match(es) recorded on {patch}; pattern estimates remain preliminary.")

        maturity = "VALIDATED" if len(exps) >= 2 and len(patch_matches) >= 6 else ("EMERGING" if len(patch_matches) >= 3 else "PRELIMINARY")
        prof = PersonalMetaProfile(
            meta_id=f"{uid}:{gv}:{patch}",
            user_id=uid,
            game_version=gv,  # type: ignore[arg-type]
            game_patch=patch,
            eligible_match_count=len(patch_matches),
            synthetic_excluded_count=synth_excl,
            strongest_system=best_sys,
            preferred_formations=[{"formation": b["formation"], "matches": b["matches"], "wins": b["wins"], "compactness": b["mean_defensive_compactness"]} for b in breakdown[:4]],
            effective_player_role_combinations=sorted(role_combo_counts.values(), key=lambda x: x["snapshot_count"], reverse=True)[:8],
            successful_partnerships=sorted(partner_entries, key=lambda x: x["synergy_score"], reverse=True)[:6],
            experiment_history=exp_history,
            patch_dependent_behaviour=patch_dependent_behaviour,
            confidence_and_evidence_maturity={
                "maturity_tier": maturity,
                "eligible_patch_matches": len(patch_matches),
                "validated_experiments": len(exps),
                "feedback_entries_logged": len(feedback_items),
                "calibrated_confidence": round(min(0.95, 0.25 + 0.08 * len(patch_matches) + 0.12 * len(exps)), 3),
            },
            vulnerable_matchups=vulnerable,
            formation_breakdown=breakdown,
            validated_experiments_count=len(exps),
            frozen_v321_weights_altered=False,
            limitations=lims,
        )
        if save:
            self.p43_repo.save_personal_meta(prof)
        return prof

    def record_feedback(self, user_id: str, req: RecommendationFeedbackCreate) -> RecommendationFeedbackRecord:
        """Persists closed-loop recommendation -> action -> snapshot/experiment -> effect ledger."""
        rec = RecommendationFeedbackRecord(user_id=str(user_id), **req.model_dump())
        return self.p43_repo.save_recommendation_feedback(rec)

    def list_feedback(self, user_id: str, *, game_version: Optional[str] = None, limit: int = 50) -> List[RecommendationFeedbackRecord]:
        return self.p43_repo.list_recommendation_feedback(str(user_id), game_version=game_version, limit=limit)
