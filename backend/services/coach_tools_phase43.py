"""Phase 43 Co-Pilot Tactical Tools Mixin & Schema Registry (12 Core Tools + Aliases).

Backed strictly by verified Phase 43 engines:
- TacticalFingerprintEngine
- PersonalFormationEngine
- TacticalCounterfactualService
- TacticalExperimentEngine (including dry-run preview & suggestion)
- ExperimentAnalysisService
- ReplacementExperimentService
- MultiObjectiveSquadOptimizer
- PersonalMetaService & Closed-Loop Feedback
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.domain.phase43_models import (
    DesignType,
    ExperimentType,
    SquadOptimizationRequest,
    TacticalExperimentCreate,
    TacticalSnapshotCreate,
)
from backend.repositories.phase40_repository import get_phase40_repository
from backend.repositories.phase43_repository import get_phase43_repository
from backend.services.experiment_analysis_service import ExperimentAnalysisService
from backend.services.multi_objective_squad_optimizer import MultiObjectiveSquadOptimizer
from backend.services.personal_formation_engine import PersonalFormationEngine
from backend.services.personal_meta_service import PersonalMetaService
from backend.services.replacement_experiment_service import ReplacementExperimentService
from backend.services.tactical_counterfactual_service import TacticalCounterfactualService
from backend.services.tactical_experiment_engine import TacticalExperimentEngine
from backend.services.tactical_fingerprint_engine import TacticalFingerprintEngine
from backend.services.tactical_snapshot_service import TacticalSnapshotService


class FingerprintToolInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    match_id: Optional[str] = Field(default=None, max_length=80)
    snapshot_id: Optional[str] = Field(default=None, max_length=64)


class FormationSuitabilityToolInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = Field(default="PATCH_1.04", max_length=32)


class CompareFormationsInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    formation_a: str = Field(default="4-3-3", max_length=16)
    formation_b: str = Field(default="4-2-3-1", max_length=16)
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = Field(default="PATCH_1.04", max_length=32)


class CompareTacticalConfigsInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    baseline_snapshot_id: Optional[str] = Field(default=None, max_length=64)
    variant_snapshot_id: Optional[str] = Field(default=None, max_length=64)
    experiment_id: Optional[str] = Field(default=None, max_length=64)


class SuggestExperimentToolInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = Field(default="PATCH_1.04", max_length=32)
    focus_weakness: Optional[str] = Field(default=None, max_length=64)


class CreateExperimentToolInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=3, max_length=140)
    hypothesis: str = Field(default="Testing whether tactical adjustment lowers transition exposure.", min_length=5, max_length=400)
    experiment_type: ExperimentType = ExperimentType.FORMATION_COMPARISON
    game_version: Literal["FC26", "FC27"] = "FC27"
    baseline_patch: str = Field(default="PATCH_1.04", max_length=32)
    baseline_formation: str = Field(default="4-3-3", max_length=16)
    variant_formation: str = Field(default="4-2-3-1", max_length=16)
    baseline_profile: str = Field(default="BALANCED", max_length=32)
    variant_profile: str = Field(default="POSSESSION", max_length=32)
    primary_metric: str = Field(default="conceded_transition_rate", max_length=64)
    design_type: DesignType = DesignType.CROSSOVER_ABBA
    target_min_matches_per_arm: int = Field(default=3, ge=1, le=50)
    confirm: bool = False


class ExperimentLookupInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    experiment_id: Optional[str] = Field(default=None, max_length=64)


class TacticalAdjustmentInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = Field(default="PATCH_1.04", max_length=32)
    match_id: Optional[str] = Field(default=None, max_length=80)


class EvaluateReplacementToolInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    target_slot: str = Field(default="CDM", max_length=12)
    current_player_name: Optional[str] = Field(default=None, max_length=80)
    game_version: Literal["FC26", "FC27"] = "FC27"
    budget_coins: Optional[int] = Field(default=None, ge=0)


class OptimizePersonalSquadToolInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = Field(default="PATCH_1.04", max_length=32)
    formation: str = Field(default="4-3-3", max_length=16)
    objective: Literal["BALANCED", "ATTACKING", "DEFENSIVE", "POSSESSION", "COUNTER_ATTACK", "PRESSING", "PERSONALIZED"] = "PERSONALIZED"
    verified_budget_coins: Optional[int] = Field(default=None, ge=0)


PHASE43_TOOL_INPUT_MODELS: Dict[str, type[BaseModel]] = {
    "get_tactical_fingerprint": FingerprintToolInput,
    "get_formation_suitability": FormationSuitabilityToolInput,
    "compare_formations": CompareFormationsInput,
    "compare_tactical_configurations": CompareTacticalConfigsInput,
    "suggest_tactical_experiment": SuggestExperimentToolInput,
    "preview_tactical_experiment": CreateExperimentToolInput,
    "create_tactical_experiment": CreateExperimentToolInput,
    "get_experiment_status": ExperimentLookupInput,
    "get_experiment_results": ExperimentLookupInput,
    "explain_experiment_uncertainty": ExperimentLookupInput,
    "explain_tactical_tradeoffs": CompareTacticalConfigsInput,
    "recommend_tactical_adjustments": TacticalAdjustmentInput,
    "evaluate_player_replacement": EvaluateReplacementToolInput,
    "optimize_personal_squad": OptimizePersonalSquadToolInput,
    "get_personal_meta_profile": FormationSuitabilityToolInput,
}

PHASE43_TOOL_DESCRIPTIONS: Dict[str, str] = {
    "get_tactical_fingerprint": "Extract 4-phase observed tactical fingerprint vs nominal formation with metric calibration & abstention notes.",
    "get_formation_suitability": "Rank all 12 formations across Theoretical Suitability, Observed Match Performance, and Controlled Experiment Evidence.",
    "compare_formations": "Head-to-head tactical, structural, and empirical comparison of two formations for the gamer's style.",
    "compare_tactical_configurations": "Compare two immutable tactical snapshots hypothetically on spatial geometry, rest defense, progression, and role familiarity.",
    "suggest_tactical_experiment": "Suggest an N-of-1 tactical experiment hypothesis and metric targeted at observed gamer weaknesses (read-only).",
    "preview_tactical_experiment": "Preview protocol & ABBA schedule for a proposed experiment without mutating saved squads or tactical configs.",
    "create_tactical_experiment": "Create a user-scoped N-of-1 tactical experiment only after explicit confirmation (preview when confirm=false).",
    "get_experiment_status": "List tactical experiments, adherence rates, and scheduled vs observed match counts.",
    "get_experiment_results": "Run or retrieve match-clustered SciPy paired/bootstrap & Bayesian analysis with practical meaningfulness check.",
    "explain_experiment_uncertainty": "Decompose sample size, adherence, leave-one-out stability, and patch/mode confounder risks for an experiment.",
    "explain_tactical_tradeoffs": "Explain theoretical rest-defense vs progression trade-offs across two tactical setups.",
    "recommend_tactical_adjustments": "Suggest behavioral/instruction adjustments grounded in Phase 43 fingerprints before card spending.",
    "evaluate_player_replacement": "Triage behavioral vs tactical vs capability gaps (Current vs Alt A/B vs No-Coin fix) preserving MARKET_PRICE_UNAVAILABLE.",
    "optimize_personal_squad": "Optimize 11-player XI under hard role/GK/uniqueness/budget constraints across 7 objectives without mutating V3.2.1.",
    "get_personal_meta_profile": "Retrieve user-scoped Personal Meta breakdown strictly isolated by game_version and game_patch.",
}


class Phase43TacticalToolsMixin:
    """Implements all 12 named Phase 43 tools + confirmation-gated write tools scoped strictly to `user_id`."""

    def get_tactical_fingerprint(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = FingerprintToolInput.model_validate(kwargs)
        p40 = self.repo if hasattr(self, "repo") else get_phase40_repository()
        p43 = get_phase43_repository()
        matches = p40.list_matches(user_id, exclude_synthetic=True, limit=10)
        if not matches:
            return {"status": "ABSTAINED_NO_REAL_MATCHES", "provenance": "PHASE43_FINGERPRINT_ENGINE", "_summary": "0 real matches available for tactical fingerprinting"}
        target = next((m for m in matches if m.match_id == inp.match_id), matches[0]) if inp.match_id else matches[0]
        snap = p43.get_snapshot(user_id, inp.snapshot_id) if inp.snapshot_id else None
        fp = TacticalFingerprintEngine(p43).build_fingerprint(user_id, target, snapshot=snap)
        return {"provenance": fp.provenance, "_summary": f"Fingerprint {target.match_id} ({fp.observed_out_of_possession_shape})", **fp.model_dump(mode="json")}

    def get_formation_suitability(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = FormationSuitabilityToolInput.model_validate(kwargs)
        p40 = self.repo if hasattr(self, "repo") else get_phase40_repository()
        res = PersonalFormationEngine(p40, get_phase43_repository()).recommend_formations(
            user_id, game_version=inp.game_version, game_patch=inp.game_patch
        )
        return {"provenance": "PHASE43_FORMATION_ENGINE", "_summary": f"Top formation: {res.ranked_formations[0].formation if res.ranked_formations else 'N/A'}", **res.model_dump(mode="json")}

    def compare_formations(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = CompareFormationsInput.model_validate(kwargs)
        p40 = self.repo if hasattr(self, "repo") else get_phase40_repository()
        rep = PersonalFormationEngine(p40, get_phase43_repository()).compare_formations(
            user_id, inp.formation_a, inp.formation_b, game_version=inp.game_version, game_patch=inp.game_patch
        )
        return {"provenance": rep.evidence_grade.value, "_summary": rep.summary, **rep.model_dump(mode="json")}

    def compare_tactical_configurations(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = CompareTacticalConfigsInput.model_validate(kwargs)
        p43 = get_phase43_repository()
        a_id, b_id = inp.baseline_snapshot_id, inp.variant_snapshot_id
        if inp.experiment_id and (not a_id or not b_id):
            exp = p43.get_experiment(user_id, inp.experiment_id)
            a_id, b_id = exp.baseline_snapshot_id, exp.variant_snapshot_id
        if not a_id or not b_id:
            snaps = p43.list_snapshots(user_id, limit=2)
            if len(snaps) < 2:
                return {"status": "NEED_TWO_SNAPSHOTS", "provenance": "PHASE43_COUNTERFACTUAL", "_summary": "Create two tactical snapshots to compare configurations"}
            b_id, a_id = snaps[0].snapshot_id, snaps[1].snapshot_id
        comp = TacticalCounterfactualService(p43).compare_snapshots(user_id, a_id, b_id)
        return {"provenance": comp.evidence_grade.value, "_summary": comp.summary, **comp.model_dump(mode="json")}

    def explain_tactical_tradeoffs(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        return self.compare_tactical_configurations(user_id, **kwargs)

    def suggest_tactical_experiment(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = SuggestExperimentToolInput.model_validate(kwargs)
        p40 = self.repo if hasattr(self, "repo") else get_phase40_repository()
        eng = TacticalExperimentEngine(get_phase43_repository(), p40)
        res = eng.suggest_tactical_experiment(
            user_id, game_version=inp.game_version, game_patch=inp.game_patch, focus_weakness=inp.focus_weakness
        )
        return {"provenance": "PHASE43_EXPERIMENT_ADVISOR", "_summary": f"Suggested {res['experiment_type']} on {res['suggested_primary_metric']}", **res}

    def preview_tactical_experiment(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = CreateExperimentToolInput.model_validate(kwargs)
        eng = TacticalExperimentEngine(get_phase43_repository(), self.repo if hasattr(self, "repo") else get_phase40_repository())
        schedule = eng._build_assignment_schedule(
            experiment_id="PREVIEW",
            baseline_snapshot_id=f"DRAFT:{inp.baseline_formation}",
            variant_snapshot_id=f"DRAFT:{inp.variant_formation}",
            design_type=inp.design_type.value,
            target_per_arm=inp.target_min_matches_per_arm,
            seed=43,
        )
        return {
            "preview_only": True,
            "requires_confirmation": True,
            "mutates_saved_config": False,
            "title": inp.title,
            "hypothesis": inp.hypothesis,
            "experiment_type": inp.experiment_type.value,
            "baseline_setup": {"formation": inp.baseline_formation, "profile": inp.baseline_profile},
            "variant_setup": {"formation": inp.variant_formation, "profile": inp.variant_profile},
            "primary_metric": inp.primary_metric,
            "design_type": inp.design_type.value,
            "recommended_schedule": schedule,
            "provenance": "PHASE43_EXPERIMENT_PREVIEW",
            "_summary": f"Previewed {inp.baseline_formation} vs {inp.variant_formation} protocol (no saved config altered)",
        }

    def create_tactical_experiment(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = CreateExperimentToolInput.model_validate(kwargs)
        if not inp.confirm:
            return self.preview_tactical_experiment(user_id, **kwargs)
        p40 = self.repo if hasattr(self, "repo") else get_phase40_repository()
        p43 = get_phase43_repository()
        snap_svc = TacticalSnapshotService(p43, p40)
        snap_a = snap_svc.create_snapshot(
            user_id,
            TacticalSnapshotCreate(
                label=f"Baseline {inp.baseline_formation} ({inp.baseline_profile})",
                game_version=inp.game_version,
                game_patch=inp.baseline_patch,
                formation=inp.baseline_formation,
                tactical_profile=inp.baseline_profile,
            ),
        )
        snap_b = snap_svc.create_snapshot(
            user_id,
            TacticalSnapshotCreate(
                label=f"Variant {inp.variant_formation} ({inp.variant_profile})",
                game_version=inp.game_version,
                game_patch=inp.baseline_patch,
                formation=inp.variant_formation,
                tactical_profile=inp.variant_profile,
                parent_snapshot_id=snap_a.snapshot_id,
            ),
        )
        eng = TacticalExperimentEngine(p43, p40)
        exp = eng.create_experiment(
            user_id,
            TacticalExperimentCreate(
                title=inp.title,
                hypothesis=inp.hypothesis,
                experiment_type=inp.experiment_type,
                game_version=inp.game_version,
                baseline_patch=inp.baseline_patch,
                baseline_snapshot_id=snap_a.snapshot_id,
                variant_snapshot_id=snap_b.snapshot_id,
                primary_metric=inp.primary_metric,
                design_type=inp.design_type,
                target_min_matches_per_arm=inp.target_min_matches_per_arm,
            ),
        )
        return {
            "provenance": "PHASE43_EXPERIMENT_ENGINE",
            "_summary": f"Created experiment {exp.experiment_id}: {exp.title}",
            "experiment": exp.model_dump(mode="json"),
            "recommended_schedule": eng.get_recommended_schedule(exp.experiment_id),
        }

    def get_experiment_status(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = ExperimentLookupInput.model_validate(kwargs)
        p43 = get_phase43_repository()
        if inp.experiment_id:
            exp = p43.get_experiment(user_id, inp.experiment_id)
            return {"experiment": exp.model_dump(mode="json"), "provenance": "PHASE43_EXPERIMENT_REPO", "_summary": f"{exp.experiment_id}: {exp.status.value}"}
        exps = p43.list_experiments(user_id, limit=10)
        return {
            "count": len(exps),
            "experiments": [
                {
                    "experiment_id": e.experiment_id,
                    "title": e.title,
                    "status": e.status.value,
                    "linked_count": len(e.linked_matches),
                    "adherence_rate": e.adherence_rate,
                }
                for e in exps
            ],
            "provenance": "PHASE43_EXPERIMENT_REPO",
            "_summary": f"{len(exps)} tactical experiment(s)",
        }

    def get_experiment_results(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = ExperimentLookupInput.model_validate(kwargs)
        p40 = self.repo if hasattr(self, "repo") else get_phase40_repository()
        p43 = get_phase43_repository()
        exps = p43.list_experiments(user_id, limit=10)
        target_id = inp.experiment_id or (exps[0].experiment_id if exps else None)
        if not target_id:
            return {"status": "NO_EXPERIMENTS_FOUND", "provenance": "PHASE43_ANALYSIS_ENGINE", "_summary": "No tactical experiments created yet"}
        res = ExperimentAnalysisService(p43, p40).analyze(user_id, target_id, persist=False)
        return {"provenance": res.evidence_grade.value, "_summary": f"{res.experiment_id}: {res.verdict.value}", **res.model_dump(mode="json")}

    def explain_experiment_uncertainty(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = ExperimentLookupInput.model_validate(kwargs)
        p40 = self.repo if hasattr(self, "repo") else get_phase40_repository()
        p43 = get_phase43_repository()
        exps = p43.list_experiments(user_id, limit=10)
        target_id = inp.experiment_id or (exps[0].experiment_id if exps else None)
        if not target_id:
            return {"status": "NO_EXPERIMENTS_FOUND", "provenance": "PHASE43_ANALYSIS_ENGINE", "_summary": "No tactical experiments created yet"}
        out = ExperimentAnalysisService(p43, p40).explain_uncertainty(user_id, target_id)
        return {"provenance": out["evidence_grade"], "_summary": f"{target_id} uncertainty breakdown ({out['verdict']})", **out}

    def recommend_tactical_adjustments(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = TacticalAdjustmentInput.model_validate(kwargs)
        fp = self.get_tactical_fingerprint(user_id, match_id=inp.match_id)
        forms = self.get_formation_suitability(user_id, game_version=inp.game_version, game_patch=inp.game_patch)
        actions: List[str] = []
        if fp.get("status") != "ABSTAINED_NO_REAL_MATCHES":
            for delta in fp.get("intended_vs_observed_deltas") or []:
                if delta.get("alignment_status") == "DRIFTED":
                    actions.append(f"Address {delta['dimension']} drift ({delta['intended_spec']}, observed={delta.get('observed_measure')}).")
        top_form = (forms.get("ranked_formations") or [None])[0]
        if top_form:
            actions.append(f"Prioritize {top_form['formation']} ({top_form['tactical_profile']}) with roles: {', '.join(top_form.get('recommended_roles', [])[:2])}.")
        return {
            "recommended_adjustments": actions or ["Collect 2+ non-synthetic matches to derive match-grounded tactical adjustments."],
            "fingerprint_summary": fp.get("observed_out_of_possession_shape"),
            "top_formation": top_form,
            "provenance": "PHASE43_TACTICAL_ADVISORY",
            "_summary": f"{len(actions)} grounded tactical adjustment(s)",
        }

    def evaluate_player_replacement(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = EvaluateReplacementToolInput.model_validate(kwargs)
        p40 = self.repo if hasattr(self, "repo") else get_phase40_repository()
        rep = ReplacementExperimentService(p40).evaluate_replacement(
            user_id,
            target_slot=inp.target_slot,
            current_player_name=inp.current_player_name,
            game_version=inp.game_version,
            budget_coins=inp.budget_coins,
        )
        return {"provenance": rep.evidence_grade.value, "_summary": f"{rep.target_slot}: {rep.primary_recommendation}", **rep.model_dump(mode="json")}

    def optimize_personal_squad(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = OptimizePersonalSquadToolInput.model_validate(kwargs)
        p40 = self.repo if hasattr(self, "repo") else get_phase40_repository()
        res = MultiObjectiveSquadOptimizer(p40).optimize_squad(
            user_id,
            SquadOptimizationRequest(
                game_version=inp.game_version,
                game_patch=inp.game_patch,
                formation=inp.formation,
                objective=inp.objective,
                verified_budget_coins=inp.verified_budget_coins,
            ),
        )
        return {"provenance": "PHASE43_MULTI_OBJECTIVE_OPTIMIZER", "_summary": f"{res.formation} {res.objective}: U={res.primary_xi.get('utility')}", **res.model_dump(mode="json")}

    def get_personal_meta_profile(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = FormationSuitabilityToolInput.model_validate(kwargs)
        p40 = self.repo if hasattr(self, "repo") else get_phase40_repository()
        prof = PersonalMetaService(p40, get_phase43_repository()).build_profile(
            user_id, game_version=inp.game_version, game_patch=inp.game_patch
        )
        return {"provenance": "PHASE43_PERSONAL_META", "_summary": f"{prof.game_version} {prof.game_patch}: {prof.eligible_match_count} matches", **prof.model_dump(mode="json")}
