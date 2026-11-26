"""Phase 44N: Typed Co-Pilot Gamer DNA & Style Matching Tools Mixin (13 Tools).

Backed strictly by Phase 44 governance, Gamer DNA V2, Professional Similarity,
Elite Skill Gap, Style Evolution, and Style-Squad-Training bridges.
All tools enforce caller `user_id` scoping and preserve frozen V3.2.1 & FC26/FC27 boundaries.
"""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.domain.phase44_models import StyleSandboxRequest
from backend.repositories.phase40_repository import get_phase40_repository
from backend.repositories.phase41_repository import get_phase41_repository
from backend.repositories.phase43_repository import get_phase43_repository
from backend.repositories.phase44_repository import get_phase44_repository
from backend.services.elite_skill_gap_engine import EliteSkillGapEngine
from backend.services.gamer_dna_v2_engine import GamerDNAV2Engine
from backend.services.professional_similarity_engine import ProfessionalGamerSimilarityEngine
from backend.services.reference_governance_service import ProfessionalReferenceRepository
from backend.services.style_evolution_engine import StyleEvolutionEngine
from backend.services.style_squad_training_bridge import (
    EliteTrainingPathwayService,
    PlayingStyleSandbox,
    StyleAwareRecommendationService,
)


class DNAProfileInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = Field(default="ALL", max_length=32)
    gameplay_mode: str = Field(default="ALL", max_length=40)


class ProMatchesInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = Field(default="ALL", max_length=32)
    top_n: int = Field(default=5, ge=1, le=10)


class ExplainSimilarityInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reference_id: Optional[str] = Field(default=None, max_length=64)
    game_version: Literal["FC26", "FC27"] = "FC27"


class FeatureBreakdownInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    game_version: Literal["FC26", "FC27"] = "FC27"
    feature_group: Optional[str] = Field(default=None, max_length=48)


class StyleCompatiblePlayersInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    game_version: Literal["FC26", "FC27"] = "FC27"
    position: str = Field(default="CM", max_length=8)
    mode: Literal["SUPPORT_NATURAL_STYLE", "COMPENSATE_WEAKNESS"] = "SUPPORT_NATURAL_STYLE"
    limit: int = Field(default=6, ge=1, le=10)


class StyleSandboxToolInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = Field(default="PATCH_1.04", max_length=32)
    sandbox_mode: Literal[
        "SUPPORT_NATURAL_POSSESSION",
        "SHIFT_COUNTER_ATTACK",
        "BALANCE_STABILITY_CREATIVITY",
        "PRO_INSPIRED_TEMPLATE",
        "NATURAL_VS_BALANCED",
    ] = "SUPPORT_NATURAL_POSSESSION"
    formation: Optional[str] = Field(default=None, max_length=16)


PHASE44_TOOL_INPUT_MODELS: Dict[str, Any] = {
    "get_gamer_style_profile": DNAProfileInput,
    "get_style_archetypes": DNAProfileInput,
    "get_professional_style_matches": ProMatchesInput,
    "compare_reference_profiles": DNAProfileInput,
    "explain_style_similarity": ExplainSimilarityInput,
    "get_style_feature_breakdown": FeatureBreakdownInput,
    "get_elite_skill_gap": DNAProfileInput,
    "get_style_evolution": DNAProfileInput,
    "recommend_style_compatible_players": StyleCompatiblePlayersInput,
    "recommend_style_compatible_formations": DNAProfileInput,
    "preview_style_based_squad": StyleSandboxToolInput,
    "recommend_elite_training_plan": DNAProfileInput,
    "suggest_style_experiment": StyleSandboxToolInput,
}

PHASE44_TOOL_DESCRIPTIONS: Dict[str, str] = {
    "get_gamer_style_profile": "Build the versioned 60-feature GamerStyleVectorV2 separated cleanly across Groups A-F (Style) and Group G (Execution).",
    "get_style_archetypes": "Classify gamer playing identity across 10 archetypes using interpretable rules + empirical unsupervised gate.",
    "get_professional_style_matches": "Compute fail-closed playing-style similarity against rights-verified pro profiles (abstains honestly if 0 exist).",
    "compare_reference_profiles": "Inspect seeded EA FC Pro candidate registry metadata, dataset manifest & fail-closed rights status.",
    "explain_style_similarity": "Explain Group A-F similarity breakdown, rank stability, and statistical indistinguishability intervals.",
    "get_style_feature_breakdown": "Inspect detailed observed vs missing style & proficiency feature observations with coverage & uncertainty.",
    "get_elite_skill_gap": "Evaluate Group G execution proficiency & Decision IQ strengths/gaps strictly decoupled from style similarity.",
    "get_style_evolution": "Track longitudinal EWMA playing-style shifts, archetype transitions & Phase 43 experiment attributions.",
    "recommend_style_compatible_players": "Recommend FC26/FC27 players preserving frozen V3.2.1 suitability + style support or weakness compensation.",
    "recommend_style_compatible_formations": "Recommend formations aligned with Gamer DNA V2 style tendencies & empirical patch telemetry.",
    "preview_style_based_squad": "Dry-run preview an XI inside the Playing Style Sandbox without altering saved squads.",
    "recommend_elite_training_plan": "Bridge Group G execution gaps into Training Academy & Decision Replay freeze-frame drills.",
    "suggest_style_experiment": "Design a controlled Phase 43 A/B tactical experiment tailored to the user's playing style identity.",
}


class Phase44GamerDNAToolsMixin:
    """Mixin delivering all 13 Phase 44 Co-Pilot tools cleanly."""

    def _build_p44_context(
        self, user_id: str, game_version: str = "FC27", game_patch: str = "ALL", gameplay_mode: str = "ALL"
    ):
        p40 = self.repo if hasattr(self, "repo") else get_phase40_repository()
        p41 = self.p41_repo if hasattr(self, "p41_repo") else get_phase41_repository()
        p43 = get_phase43_repository()
        gv = "FC26" if str(game_version).upper() == "FC26" else "FC27"
        matches = p40.list_matches(user_id, game_version=gv, exclude_synthetic=True, limit=60)
        cold = p40.get_cold_start_preferences(user_id)
        fps = p43.list_fingerprints(user_id, limit=30)
        wins = p41.list_decision_windows(user_id, exclude_synthetic=True, limit=80)
        v2 = GamerDNAV2Engine().build_profile(
            user_id,
            matches,
            game_version=gv,
            game_patch=game_patch,
            gameplay_mode=gameplay_mode,
            fingerprints=fps,
            decision_windows=wins,
            cold_start=cold,
        )
        return p40, p43, matches, v2

    def get_gamer_style_profile(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = DNAProfileInput.model_validate(kwargs)
        _, _, _, v2 = self._build_p44_context(user_id, inp.game_version, inp.game_patch, inp.gameplay_mode)
        return {
            "provenance": "GAMER_DNA_V2_ENGINE",
            "_summary": f"{v2.archetype.primary_archetype} ({v2.eligible_match_count} matches, {v2.overall_coverage:.0%} style coverage)",
            **v2.model_dump(mode="json"),
        }

    def get_style_archetypes(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = DNAProfileInput.model_validate(kwargs)
        _, _, _, v2 = self._build_p44_context(user_id, inp.game_version, inp.game_patch, inp.gameplay_mode)
        return {
            "provenance": "STYLE_ARCHETYPE_ENGINE",
            "archetype": v2.archetype.model_dump(mode="json"),
            "eligible_match_count": v2.eligible_match_count,
            "_summary": f"{v2.archetype.primary_archetype} ({v2.archetype.status})",
        }

    def get_professional_style_matches(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = ProMatchesInput.model_validate(kwargs)
        _, _, matches, v2 = self._build_p44_context(user_id, inp.game_version, inp.game_patch)
        rep = ProfessionalGamerSimilarityEngine(ProfessionalReferenceRepository(get_phase44_repository())).compare(
            v2, user_matches=matches, top_n=inp.top_n
        )
        return {
            "provenance": "PRO_SIMILARITY_GOVERNED",
            "_summary": (
                f"Abstained: {rep.abstention_reason}"
                if rep.abstained
                else f"Top match: {rep.matches[0].public_alias} ({rep.matches[0].interpretable_similarity_index:.1f})"
            ),
            **rep.model_dump(mode="json"),
        }

    def compare_reference_profiles(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        _ = user_id
        _ = kwargs
        ref_repo = ProfessionalReferenceRepository(get_phase44_repository())
        return {
            "manifest": ref_repo.get_manifest(),
            "candidates": [c.model_dump(mode="json") for c in ref_repo.list_candidates()],
            "provenance": "PRO_REFERENCE_GOVERNANCE_REGISTRY",
            "_summary": f"{ref_repo.get_manifest().get('authorized_profile_count', 0)} authorized pro profiles",
        }

    def explain_style_similarity(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = ExplainSimilarityInput.model_validate(kwargs)
        _, _, matches, v2 = self._build_p44_context(user_id, inp.game_version)
        rep = ProfessionalGamerSimilarityEngine(ProfessionalReferenceRepository(get_phase44_repository())).compare(
            v2, user_matches=matches, top_n=5
        )
        return {
            "abstained": rep.abstained,
            "abstention_reason": rep.abstention_reason,
            "scale_disclosure": rep.scale_disclosure,
            "uncertainty_summary": rep.uncertainty_summary,
            "matches": [m.model_dump(mode="json") for m in rep.matches],
            "fallback_archetype_summary": rep.fallback_archetype_summary,
            "provenance": "PRO_SIMILARITY_EXPLAINER",
            "_summary": "Abstained cleanly" if rep.abstained else f"Explained {len(rep.matches)} pro comparison(s)",
        }

    def get_style_feature_breakdown(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = FeatureBreakdownInput.model_validate(kwargs)
        _, _, _, v2 = self._build_p44_context(user_id, inp.game_version)
        items = list(v2.style_features.values()) + list(v2.proficiency_features.values())
        if inp.feature_group:
            fg = inp.feature_group.upper()
            items = [x for x in items if x.feature_group.value == fg]
        return {
            "game_version": v2.game_version,
            "eligible_match_count": v2.eligible_match_count,
            "feature_count": len(items),
            "observed_count": sum(1 for x in items if x.raw_value is not None),
            "features": [x.model_dump(mode="json") for x in items],
            "provenance": "GAMER_DNA_V2_FEATURES",
            "_summary": f"{sum(1 for x in items if x.raw_value is not None)}/{len(items)} features observed",
        }

    def get_elite_skill_gap(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = DNAProfileInput.model_validate(kwargs)
        _, _, _, v2 = self._build_p44_context(user_id, inp.game_version, inp.game_patch, inp.gameplay_mode)
        rep = EliteSkillGapEngine().analyze(v2)
        return {
            "provenance": "ELITE_SKILL_GAP_ENGINE",
            "_summary": f"{len(rep.gaps)} priority execution gap(s); {len(rep.strengths)} strength/parity dim(s)",
            **rep.model_dump(mode="json"),
        }

    def get_style_evolution(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = DNAProfileInput.model_validate(kwargs)
        p40, p43, matches, _ = self._build_p44_context(user_id, inp.game_version)
        exps = p43.list_experiments(user_id, game_version=inp.game_version, limit=20)
        rep = StyleEvolutionEngine().analyze(user_id, matches, game_version=inp.game_version, experiments=exps)
        return {
            "provenance": "STYLE_EVOLUTION_ENGINE",
            "_summary": rep.shift_summary,
            **rep.model_dump(mode="json"),
        }

    def recommend_style_compatible_players(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = StyleCompatiblePlayersInput.model_validate(kwargs)
        res = StyleAwareRecommendationService().recommend_players(
            user_id, game_version=inp.game_version, position=inp.position, mode=inp.mode, limit=inp.limit
        )
        return {"provenance": "STYLE_AWARE_V321_BRIDGE", "_summary": f"{len(res['items'])} {inp.position} style picks", **res}

    def recommend_style_compatible_formations(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = DNAProfileInput.model_validate(kwargs)
        patch = "PATCH_1.04" if inp.game_patch == "ALL" else inp.game_patch
        res = StyleAwareRecommendationService().recommend_formations(user_id, game_version=inp.game_version, game_patch=patch)
        return {"provenance": "STYLE_FORMATION_BRIDGE", "_summary": f"Archetype {res['primary_archetype']} formations", **res}

    def preview_style_based_squad(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = StyleSandboxToolInput.model_validate(kwargs)
        res = PlayingStyleSandbox().preview(
            user_id,
            StyleSandboxRequest(
                game_version=inp.game_version,
                game_patch=inp.game_patch,
                sandbox_mode=inp.sandbox_mode,
                formation=inp.formation,
                convert_to_experiment=False,
            ),
        )
        return {"provenance": "PLAYING_STYLE_SANDBOX_DRYRUN", "_summary": f"{res['sandbox_mode']} XI preview ({res['formation']})", **res}

    def recommend_elite_training_plan(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = DNAProfileInput.model_validate(kwargs)
        res = EliteTrainingPathwayService().build_pathway(user_id, game_version=inp.game_version)
        return {"provenance": "ELITE_TRAINING_PATHWAY", "_summary": f"{len(res['priority_gap_actions'])} gap objective(s)", **res}

    def suggest_style_experiment(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = StyleSandboxToolInput.model_validate(kwargs)
        _, _, matches, v2 = self._build_p44_context(user_id, inp.game_version, inp.game_patch)
        base_form = matches[0].formation if matches else "4-3-3"
        variant_form = inp.formation or ("4-2-3-1" if base_form != "4-2-3-1" else "4-4-2")
        return {
            "proposed_experiment": {
                "title": f"Style Experiment: {v2.archetype.primary_archetype} ({base_form} vs {variant_form})",
                "hypothesis": f"Evaluate whether {variant_form} improves defensive transition control while preserving your {v2.archetype.primary_archetype} identity.",
                "baseline_formation": base_form,
                "variant_formation": variant_form,
                "game_version": v2.game_version,
                "game_patch": inp.game_patch,
                "primary_metric": "conceded_transition_rate",
                "requires_confirmation": True,
            },
            "provenance": "STYLE_EXPERIMENT_SUGGESTER",
            "_summary": f"Suggested {base_form} vs {variant_form} ABBA test",
        }
