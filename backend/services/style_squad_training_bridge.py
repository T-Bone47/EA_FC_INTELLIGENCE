"""Phase 44K-44M: Style-Aware Recommendation, Playing Style Sandbox & Elite Training Bridge.

Strictly preserves:
- Frozen V3.2.1 mathematical weights (`RecommendationServiceV3`) untouched
- FC26/FC27 edition walls & `MARKET_PRICE_UNAVAILABLE` honesty
- Additive explainability separating Style Support from Weakness Compensation
- Interactive dry-run Sandbox previews with explicit opt-in Phase 43 experiment creation
- Practice-only BKT / Decision Lab training pathways separated from live match claims
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.api.schemas_v3 import RecommendationRequestV3
from backend.domain.phase43_models import (
    DesignType,
    ExperimentType,
    SquadOptimizationRequest,
    TacticalExperimentCreate,
    TacticalSnapshotCreate,
)
from backend.domain.phase44_models import (
    EliteSkillGapReport,
    GamerStyleVectorV2,
    StyleAwareRecommendationAdjustment,
    StyleSandboxRequest,
)
from backend.repositories.phase40_repository import Phase40Repository, get_phase40_repository
from backend.repositories.phase41_repository import Phase41Repository, get_phase41_repository
from backend.repositories.phase43_repository import Phase43Repository, get_phase43_repository
from backend.services.elite_skill_gap_engine import EliteSkillGapEngine
from backend.services.gamer_dna_v2_engine import GamerDNAV2Engine
from backend.services.multi_objective_squad_optimizer import MultiObjectiveSquadOptimizer
from backend.services.personal_formation_engine import PersonalFormationEngine
from backend.services.recommendation_service_v3 import RecommendationServiceV3
from backend.services.recurring_mistake_analyzer import RecurringMistakeAnalyzer
from backend.services.tactical_experiment_engine import TacticalExperimentEngine
from backend.services.tactical_snapshot_service import TacticalSnapshotService
from backend.services.training_plan_service import TrainingPlanService


_STYLE_PROFILE_MAP: Dict[str, Dict[str, Any]] = {
    "Possession Architect": {
        "tactic": "POSSESSION",
        "key_playstyles": ["Tiki Taka", "Incisive Pass", "Press Proven", "Deep-Lying Playmaker"],
        "key_attrs": ["short_passing", "composure", "vision", "ball_control"],
        "roles": ["Deep-Lying Playmaker (Build-Up)", "Playmaker (Roam)", "Falseback (Balanced)"],
    },
    "Direct Attacking Specialist": {
        "tactic": "COUNTER_ATTACK",
        "key_playstyles": ["Rapid", "Long Ball Pass", "Pinged Pass", "Quick Step"],
        "key_attrs": ["long_passing", "sprint_speed", "acceleration", "attack_positioning"],
        "roles": ["Inside Forward (Attack)", "Box-to-Box (Balanced)", "Poacher (Attack)"],
    },
    "Counter-Attacking Specialist": {
        "tactic": "COUNTER_ATTACK",
        "key_playstyles": ["Quick Step", "Rapid", "Long Ball Pass", "Intercept"],
        "key_attrs": ["sprint_speed", "acceleration", "interceptions", "stamina"],
        "roles": ["Holding (Defend)", "Winger (Balanced)", "Advanced Forward (Attack)"],
    },
    "High-Pressing Aggressor": {
        "tactic": "PRESSING",
        "key_playstyles": ["Relentless", "Bruiser", "Anticipate", "Rapid"],
        "key_attrs": ["stamina", "aggression", "interceptions", "acceleration"],
        "roles": ["Ball-Winning Midfielder", "Stopper (Balanced)", "Inside Forward (Attack)"],
    },
    "Defensive Controller": {
        "tactic": "DEFENSIVE",
        "key_playstyles": ["Anticipate", "Intercept", "Jockey", "Block"],
        "key_attrs": ["defensive_awareness", "interceptions", "standing_tackle", "composure"],
        "roles": ["Holding (Defend)", "Defender (Defend)", "Fullback (Defend)"],
    },
    "Wing-Based Creator": {
        "tactic": "ATTACKING",
        "key_playstyles": ["Whipped Pass", "Rapid", "Technical", "Trickster"],
        "key_attrs": ["crossing", "sprint_speed", "dribbling_detail", "curve"],
        "roles": ["Winger (Attack)", "Attacking Wingback (Attack)", "Target Forward"],
    },
    "Central Combination Specialist": {
        "tactic": "POSSESSION",
        "key_playstyles": ["Incisive Pass", "Tiki Taka", "First Touch", "Finesse Shot"],
        "key_attrs": ["short_passing", "vision", "dribbling_detail", "agility"],
        "roles": ["Shadow Striker (Attack)", "Half-Winger (Balanced)", "Deep-Lying Playmaker"],
    },
    "High-Risk Creative Attacker": {
        "tactic": "ATTACKING",
        "key_playstyles": ["Incisive Pass", "Technical", "Trivela", "Quick Step"],
        "key_attrs": ["vision", "dribbling_detail", "long_passing", "finishing"],
        "roles": ["Playmaker (Attack)", "Shadow Striker", "Inside Forward (Attack)"],
    },
    "Adaptive Tactical Strategist": {
        "tactic": "BALANCED",
        "key_playstyles": ["Press Proven", "Relentless", "Incisive Pass"],
        "key_attrs": ["composure", "reactions", "stamina", "short_passing"],
        "roles": ["Box-to-Box (Balanced)", "Half-Winger", "Deep-Lying Playmaker"],
    },
    "Balanced Tactical Generalist": {
        "tactic": "BALANCED",
        "key_playstyles": ["Press Proven", "Intercept", "Incisive Pass"],
        "key_attrs": ["short_passing", "stamina", "reactions", "composure"],
        "roles": ["Box-to-Box (Balanced)", "Holding (Defend)", "Advanced Forward"],
    },
}


class StyleAwareRecommendationService:
    """Phase 44K: Additive style-alignment and weakness-compensation layer over frozen V3.2.1."""

    def __init__(
        self,
        p40_repo: Optional[Phase40Repository] = None,
        p43_repo: Optional[Phase43Repository] = None,
        v3_service: Optional[RecommendationServiceV3] = None,
    ) -> None:
        self.p40 = p40_repo or get_phase40_repository()
        self.p43 = p43_repo or get_phase43_repository()
        self.v3 = v3_service or RecommendationServiceV3()
        self.dna_engine = GamerDNAV2Engine()
        self.gap_engine = EliteSkillGapEngine()
        self.form_engine = PersonalFormationEngine(self.p40, self.p43, get_phase41_repository())

    def recommend_players(
        self,
        user_id: str,
        *,
        game_version: str = "FC27",
        position: str = "CM",
        mode: str = "SUPPORT_NATURAL_STYLE",
        game_patch: str = "PATCH_1.04",
        limit: int = 6,
    ) -> Dict[str, Any]:
        gv = "FC26" if game_version.upper() == "FC26" else "FC27"
        uid = str(user_id)
        matches = self.p40.list_matches(uid, game_version=gv, exclude_synthetic=True, limit=40)
        cold = self.p40.get_cold_start_preferences(uid)
        v2 = self.dna_engine.build_profile(uid, matches, game_version=gv, game_patch=game_patch, cold_start=cold)
        gaps_rep = self.gap_engine.analyze(v2)

        arch = v2.archetype.primary_archetype
        arch_meta = _STYLE_PROFILE_MAP.get(arch, _STYLE_PROFILE_MAP["Balanced Tactical Generalist"])
        tactic = arch_meta["tactic"]

        req_v3 = RecommendationRequestV3(
            game_version=gv,
            position=position.upper(),
            tactical_profile=tactic,
            include_research_data=(gv == "FC27"),
            limit=min(12, max(limit * 2, 8)),
        )
        raw_v3 = self.v3.recommend(req_v3)
        ranked = raw_v3.get("ranked") or []

        # Priority weakness traits
        weak_playstyles: set[str] = set()
        for g in gaps_rep.gaps[:2]:
            if g.dimension in ("defensive_recovery_success", "possession_loss_rate"):
                weak_playstyles.update({"Intercept", "Anticipate", "Jockey", "Press Proven"})
            elif g.dimension in ("pass_success_rate", "decision_regret_inverse"):
                weak_playstyles.update({"Tiki Taka", "Incisive Pass", "First Touch"})
            elif g.dimension in ("shooting_execution_quality", "opportunity_conversion_rate"):
                weak_playstyles.update({"Finesse Shot", "Low Driven Shot", "Quick Step"})

        adjustments: List[StyleAwareRecommendationAdjustment] = []
        for row in ranked:
            card = row.get("player") or row.get("card") or {}
            base_s = float(row.get("score") or 0.0)
            ps_raw = card.get("playstyles") or []
            ps_names = {
                (p.get("name") or p.get("playstyle_name") or "").strip()
                if isinstance(p, dict)
                else str(p).strip()
                for p in ps_raw
            }
            ps_hits = len(ps_names & set(arch_meta["key_playstyles"]))
            weak_hits = len(ps_names & weak_playstyles)

            style_align = round(min(1.0, 0.52 + 0.14 * ps_hits), 4)
            weak_comp = round(min(1.0, 0.45 + 0.16 * weak_hits), 4)
            if mode == "COMPENSATE_WEAKNESS":
                comb = round(0.65 * base_s + 0.12 * (style_align * 100.0) + 0.23 * (weak_comp * 100.0), 3)
                rationale = (
                    f"Weakness-compensation weighting highlights {weak_hits} priority gap PlayStyle(s) "
                    f"over frozen V3.2.1 base ({base_s:.1f})."
                )
            else:
                comb = round(0.68 * base_s + 0.24 * (style_align * 100.0) + 0.08 * (weak_comp * 100.0), 3)
                rationale = (
                    f"Natural-style alignment ({arch}) scores {ps_hits} matching PlayStyle(s) "
                    f"alongside frozen V3.2.1 base ({base_s:.1f})."
                )

            adjustments.append(
                StyleAwareRecommendationAdjustment(
                    entity_id=str(row.get("entity_id")),
                    name=str(row.get("name") or card.get("name") or "Player"),
                    position=str(card.get("position_primary") or position.upper()),
                    overall_rating=float(card["overall_rating"]) if card.get("overall_rating") else None,
                    frozen_v321_suitability=round(base_s, 3),
                    style_alignment_score=style_align,
                    weakness_compensation_score=weak_comp,
                    advisory_combined_score=comb,
                    role_recommendations=list(arch_meta["roles"][:2]),
                    style_rationale=rationale,
                )
            )

        adjustments.sort(key=lambda a: a.advisory_combined_score, reverse=True)
        return {
            "user_id": uid,
            "game_version": gv,
            "position": position.upper(),
            "mode": mode,
            "primary_archetype": arch,
            "frozen_v321_weights_altered": False,
            "market_price_status": "MARKET_PRICE_UNAVAILABLE",
            "items": [a.model_dump(mode="json") for a in adjustments[:limit]],
            "caveat": "Frozen V3.2.1 suitability weights remain untouched; style adjustment is purely an additive personalization layer.",
        }

    def recommend_formations(self, user_id: str, *, game_version: str = "FC27", game_patch: str = "PATCH_1.04") -> Dict[str, Any]:
        uid = str(user_id)
        gv = "FC26" if game_version.upper() == "FC26" else "FC27"
        matches = self.p40.list_matches(uid, game_version=gv, exclude_synthetic=True, limit=40)
        cold = self.p40.get_cold_start_preferences(uid)
        v2 = self.dna_engine.build_profile(uid, matches, game_version=gv, game_patch=game_patch, cold_start=cold)
        rec = self.form_engine.recommend_formations(uid, game_version=gv, game_patch=game_patch)
        return {
            "user_id": uid,
            "game_version": rec.game_version,
            "game_patch": rec.game_patch,
            "primary_archetype": v2.archetype.primary_archetype,
            "eligible_match_count": rec.eligible_match_count,
            "ranked_formations": [f.model_dump(mode="json") for f in rec.ranked_formations],
            "frozen_v321_weights_altered": False,
            "disclaimer": rec.caveat,
        }


class PlayingStyleSandbox:
    """Phase 44L: Non-mutating interactive Playing Style Sandbox with optional Phase 43 experiment handoff."""

    _MODE_CONFIG: Dict[str, Dict[str, str]] = {
        "SUPPORT_NATURAL_POSSESSION": {"objective": "POSSESSION", "default_form": "4-2-3-1", "desc": "Align XI roles & triangle creators around calm ball retention and half-space support."},
        "SHIFT_COUNTER_ATTACK": {"objective": "COUNTER_ATTACK", "default_form": "4-4-2", "desc": "Prioritize transition pace, vertical outlets & low/mid-block compact springs."},
        "BALANCE_STABILITY_CREATIVITY": {"objective": "BALANCED", "default_form": "4-2-3-1", "desc": "Balance double-pivot counter shielding with central Zone 14 creativity."},
        "PRO_INSPIRED_TEMPLATE": {"objective": "PERSONALIZED", "default_form": "4-2-1-3", "desc": "Abstract structural template inspired by high-tempo tournament setups (metadata-level; no fabricated pro data)."},
        "NATURAL_VS_BALANCED": {"objective": "PERSONALIZED", "default_form": "4-3-3", "desc": "Side-by-side comparison between current archetype tendencies and defensively balanced shape."},
    }

    def __init__(
        self,
        p40_repo: Optional[Phase40Repository] = None,
        p43_repo: Optional[Phase43Repository] = None,
    ) -> None:
        self.p40 = p40_repo or get_phase40_repository()
        self.p43 = p43_repo or get_phase43_repository()
        self.dna_engine = GamerDNAV2Engine()
        self.optimizer = MultiObjectiveSquadOptimizer(self.p40)

    def preview(self, user_id: str, req: StyleSandboxRequest) -> Dict[str, Any]:
        uid = str(user_id)
        gv = req.game_version
        cfg = self._MODE_CONFIG.get(req.sandbox_mode, self._MODE_CONFIG["SUPPORT_NATURAL_POSSESSION"])
        target_form = req.formation or cfg["default_form"]
        if target_form == "4-2-1-3":
            # Ensure canonical FORMATION_SLOTS fallback if 4-2-1-3 isn't registered identically
            target_form = "4-2-3-1"

        matches = self.p40.list_matches(uid, game_version=gv, exclude_synthetic=True, limit=30)
        v2 = self.dna_engine.build_profile(uid, matches, game_version=gv, game_patch=req.game_patch)

        opt = self.optimizer.optimize_squad(
            uid,
            SquadOptimizationRequest(
                game_version=gv,
                game_patch=req.game_patch,
                formation=target_form,
                objective=cfg["objective"],  # type: ignore[arg-type]
                locked_slots=req.locked_slots,
            ),
        )

        created_experiment: Optional[Dict[str, Any]] = None
        if req.convert_to_experiment:
            snap_svc = TacticalSnapshotService(self.p43, self.p40)
            exp_eng = TacticalExperimentEngine(self.p43, self.p40)
            base_form = (matches[0].formation if matches else "4-3-3")
            var_form = target_form if target_form != base_form else ("4-2-3-1" if base_form != "4-2-3-1" else "4-4-2")
            snap_a = snap_svc.create_snapshot(
                uid,
                TacticalSnapshotCreate(
                    label=f"Baseline ({base_form})",
                    game_version=gv,
                    game_patch=req.game_patch,
                    formation=base_form,
                    tactical_profile="BALANCED",
                ),
            )
            snap_b = snap_svc.create_snapshot(
                uid,
                TacticalSnapshotCreate(
                    label=f"Sandbox {req.sandbox_mode} ({var_form})",
                    game_version=gv,
                    game_patch=req.game_patch,
                    formation=var_form,
                    tactical_profile=cfg["objective"],
                ),
            )
            exp = exp_eng.create_experiment(
                uid,
                TacticalExperimentCreate(
                    title=f"Style Sandbox Trial: {req.sandbox_mode} ({base_form} vs {var_form})",
                    hypothesis=(
                        f"Testing whether shifting from {base_form} toward {var_form} ({cfg['objective']}) improves "
                        "conceded transition stability without breaking style identity."
                    ),
                    experiment_type=ExperimentType.FORMATION_COMPARISON,
                    game_version=gv,
                    baseline_patch=req.game_patch,
                    baseline_snapshot_id=snap_a.snapshot_id,
                    variant_snapshot_id=snap_b.snapshot_id,
                    primary_metric="conceded_transition_rate",
                    design_type=DesignType.CROSSOVER_ABBA,
                ),
            )
            created_experiment = exp.model_dump(mode="json")

        return {
            "sandbox_mode": req.sandbox_mode,
            "description": cfg["desc"],
            "user_archetype": v2.archetype.primary_archetype,
            "formation": opt.formation,
            "objective": opt.objective,
            "preview_xi": opt.primary_xi,
            "alternatives": opt.alternatives[:2],
            "hard_constraints_verified": opt.hard_constraints_verified,
            "market_price_status": opt.market_price_status,
            "frozen_v321_weights_altered": False,
            "non_mutating_preview": not req.convert_to_experiment,
            "created_experiment": created_experiment,
            "caveat": "Preview lineup is dry-run advisory only; live squad/match uplift requires controlled testing.",
        }


class EliteTrainingPathwayService:
    """Phase 44M: Maps Group G execution/Decision IQ gaps to Training Academy & Decision Replay drills."""

    def __init__(
        self,
        p40_repo: Optional[Phase40Repository] = None,
        p41_repo: Optional[Phase41Repository] = None,
    ) -> None:
        self.p40 = p40_repo or get_phase40_repository()
        self.p41 = p41_repo or get_phase41_repository()
        self.dna_v2 = GamerDNAV2Engine()
        self.gap_engine = EliteSkillGapEngine()
        self.training_svc = TrainingPlanService()
        self.mistakes = RecurringMistakeAnalyzer()

    def build_pathway(self, user_id: str, *, game_version: str = "FC27") -> Dict[str, Any]:
        uid = str(user_id)
        gv = "FC26" if game_version.upper() == "FC26" else "FC27"
        matches = self.p40.list_matches(uid, game_version=gv, exclude_synthetic=True, limit=40)
        cold = self.p40.get_cold_start_preferences(uid)
        windows = self.p41.list_decision_windows(uid, exclude_synthetic=True, limit=40)

        v2 = self.dna_v2.build_profile(uid, matches, game_version=gv, decision_windows=windows, cold_start=cold)
        gaps_rep = self.gap_engine.analyze(v2)
        mistake_list = self.mistakes.analyze(matches)

        # Build legacy GamerDNAProfile seamlessly so existing TrainingPlanService links Decision Lab windows
        from backend.services.gamer_dna_engine import GamerDNAEngine
        dna_v1 = GamerDNAEngine().build_profile(uid, matches, cold_start=cold)
        plan = self.training_svc.generate_plan(
            uid, game_version=gv, mistakes=mistake_list, dna=dna_v1, decision_windows=windows
        )

        gap_actions = [
            {
                "gap_dimension": g.dimension,
                "gap_estimate": g.skill_gap_estimate,
                "training_objective": g.suggested_training_objective,
                "tactical_adjustment": g.suggested_tactical_adjustment,
                "supporting_evidence": g.supporting_evidence,
            }
            for g in gaps_rep.gaps[:4]
        ]

        return {
            "user_id": uid,
            "game_version": gv,
            "primary_archetype": v2.archetype.primary_archetype,
            "reference_scope": gaps_rep.reference_scope,
            "reference_population_verified": gaps_rep.reference_population_verified,
            "priority_gap_actions": gap_actions,
            "linked_exercises": [ex.model_dump(mode="json") for ex in plan.exercises[:4]],
            "practice_only": True,
            "caveat": (
                "Training drills and Decision Replay scenarios improve decision familiarity in practice sessions; "
                "competitive match progression must still be verified via observed matches."
            ),
        }
