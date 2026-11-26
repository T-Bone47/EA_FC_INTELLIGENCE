"""Phase 43G: Player Replacement Triage & Single-Position Experiment Designer.

Diagnostic hierarchy before recommending coin spending:
1. Gamer decision / risky passing habit (DECISION_PRACTICE_FIRST)
2. Tactical instructions / defensive line height (TACTICAL_OR_ROLE_ADJUSTMENT_FIRST)
3. Formation fit mismatch
4. Player Role / Focus configuration
5. Player attribute / PlayStyle capability bottleneck (TEST_REPLACEMENT_EXPERIMENT)

Respects MARKET_PRICE_UNAVAILABLE cleanly and preserves frozen V3.2.1 weights.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.domain.phase43_models import EvidenceGrade, ReplacementTriageReport
from backend.repositories.phase40_repository import Phase40Repository, get_phase40_repository
from backend.repositories.phase43_repository import Phase43Repository, get_phase43_repository
from backend.services.gamer_dna_engine import GamerDNAEngine
from backend.services.personal_gameplay_fit import PersonalGameplayFitService
from backend.services.recurring_mistake_analyzer import RecurringMistakeAnalyzer


class ReplacementExperimentService:
    """Triages behavioral/tactical causes vs genuine capability gaps before player replacement."""

    def __init__(
        self,
        p40_repo: Optional[Phase40Repository] = None,
        p43_repo: Optional[Phase43Repository] = None,
    ) -> None:
        self.p40_repo = p40_repo or get_phase40_repository()
        self.p43_repo = p43_repo or get_phase43_repository()
        self.dna_engine = GamerDNAEngine()
        self.mistake_analyzer = RecurringMistakeAnalyzer()
        self.fit_service = PersonalGameplayFitService()

    def evaluate_replacement(
        self,
        user_id: str,
        *,
        target_slot: str,
        current_player_name: Optional[str] = None,
        game_version: str = "FC27",
        budget_coins: Optional[int] = None,
    ) -> ReplacementTriageReport:
        uid = str(user_id)
        gv = "FC26" if game_version.upper() == "FC26" else "FC27"
        slot_up = target_slot.upper().strip()
        matches = self.p40_repo.list_matches(uid, game_version=gv, exclude_synthetic=True, limit=60)
        cold = self.p40_repo.get_cold_start_preferences(uid)
        dna = self.dna_engine.build_profile(uid, matches, cold_start=cold)
        mistakes = self.mistake_analyzer.analyze(matches)
        diag = self.fit_service.diagnose_intervention(dna, mistakes, matches)

        likely_causes: List[Dict[str, Any]] = []
        non_purchase_actions: List[str] = list(diag.get("tactical_first_actions") or [])
        if not matches:
            return ReplacementTriageReport(
                target_slot=slot_up,
                current_player_name=current_player_name,
                game_version=gv,  # type: ignore[arg-type]
                likely_causes=[{"cause": "NO_ELIGIBLE_MATCH_EVIDENCE", "confidence": "LOW", "note": "No verified non-synthetic matches logged for capability triage."}],
                primary_recommendation="INSUFFICIENT_MATCH_EVIDENCE",
                purchase_justified=False,
                non_purchase_interventions=["Record 2+ real matches in Gameplay Studio before evaluating whether slot replacement is warranted."],
                candidate_upgrades=[],
                proposed_experiment_design=None,
                evidence_grade=EvidenceGrade.THEORETICAL_SUITABILITY,
            )

        rec_cat = diag.get("recommended_intervention", "TACTICAL_INSTRUCTION_ADJUSTMENT")
        purchase_justified = bool(diag.get("purchase_justified", False))

        if rec_cat in ("GAMEPLAY_PRACTICE",):
            primary_rec = "DECISION_PRACTICE_FIRST"
            likely_causes.append({"cause": "GAMER_DECISION_PATTERN", "plausibility": "HIGH", "note": diag.get("reason")})
        elif not purchase_justified:
            primary_rec = "TACTICAL_OR_ROLE_ADJUSTMENT_FIRST"
            likely_causes.append({"cause": rec_cat, "plausibility": "MODERATE_HIGH", "note": diag.get("reason")})
            non_purchase_actions.append(f"Test switching {slot_up} Role/Focus (e.g., Holding / Deep-Lying Playmaker) over 3 matches before replacing the card.")
        else:
            primary_rec = "TEST_REPLACEMENT_EXPERIMENT"
            likely_causes.append({"cause": "PLAYER_CAPABILITY_OR_ROLE_BOTTLENECK", "plausibility": "MODERATE", "note": diag.get("reason")})

        # Fetch canonical candidates purely via existing read-only V3.2.1 PersonalGameplayFit wrapper
        exclude_list = [current_player_name] if current_player_name else []
        pos_norm = "CDM" if "CDM" in slot_up else ("CM" if "CM" in slot_up else ("CB" if "CB" in slot_up else slot_up))
        rec_out = self.fit_service.recommend_for_gamer(
            game_version=gv,
            position=pos_norm,
            dna=dna,
            mistakes=mistakes,
            matches=matches,
            budget_coins=budget_coins,
            exclude_names=exclude_list,
            limit=4,
        )
        candidates = rec_out.get("recommendations", [])

        proposed_exp = {
            "experiment_type": "SINGLE_POSITION_REPLACEMENT",
            "title": f"Isolate {slot_up} Upgrade: {current_player_name or 'Incumbent'} vs Candidate",
            "hypothesis": f"Replacing only {slot_up} while holding formation & all 10 other slots constant changes transition/progression stability.",
            "primary_metric": "conceded_transition_rate" if slot_up in ("CDM", "CM", "CB", "LB", "RB") else "chance_creation",
            "target_min_matches_per_arm": 3,
            "control_rule": "Hold formation, tactical preset, line height, and other 10 players constant across Arm A and Arm B.",
        }

        candidate_comparisons: List[Dict[str, Any]] = [
            {
                "option": "CURRENT_PLAYER",
                "label": current_player_name or f"Current {slot_up}",
                "coin_cost": 0,
                "expected_delta_hypothesis": "Baseline incumbent performance in current role focus.",
                "market_price_status": "NOT_APPLICABLE",
            },
            {
                "option": "NO_COIN_TACTICAL_ADJUSTMENT",
                "label": f"Adjust {slot_up} Role/Focus + Line Height",
                "coin_cost": 0,
                "expected_delta_hypothesis": non_purchase_actions[0] if non_purchase_actions else f"Reconfigure {slot_up} role focus before spending coins.",
                "market_price_status": "FREE_TACTICAL_CHANGE",
            },
        ]
        for idx, cand in enumerate(candidates[:2]):
            opt_tag = "CANDIDATE_ALT_A" if idx == 0 else "CANDIDATE_ALT_B"
            candidate_comparisons.append(
                {
                    "option": opt_tag,
                    "label": cand.get("name") or cand.get("player_name") or f"Alt {idx + 1}",
                    "overall_rating": cand.get("overall_rating") or cand.get("ovr"),
                    "v321_fit_score": cand.get("personal_fit_score") or cand.get("v321_score"),
                    "coin_cost": cand.get("coin_cost"),
                    "market_price_status": "MARKET_PRICE_UNAVAILABLE" if cand.get("coin_cost") is None else "VERIFIED_PRICE",
                }
            )

        report = ReplacementTriageReport(
            target_slot=slot_up,
            current_player_name=current_player_name,
            game_version=gv,  # type: ignore[arg-type]
            likely_causes=likely_causes,
            primary_recommendation=primary_rec,
            purchase_justified=purchase_justified,
            non_purchase_interventions=list(dict.fromkeys(non_purchase_actions)),
            candidate_upgrades=candidates,
            candidate_comparisons=candidate_comparisons,
            proposed_experiment_design=proposed_exp,
            market_price_status="MARKET_PRICE_UNAVAILABLE",
            frozen_v321_untouched=True,
            evidence_grade=EvidenceGrade.OBSERVED_ASSOCIATION,
        )
        try:
            self.p43_repo.save_replacement_experiment(
                uid,
                game_version=gv,
                position=slot_up,
                outgoing_card_id=current_player_name,
                candidate_card_id=str(candidates[0].get("name") or candidates[0].get("player_name")) if candidates else None,
                verdict=primary_rec,
                no_coin_viable=not purchase_justified,
                payload=report.model_dump(mode="json"),
            )
        except Exception:
            pass
        return report
