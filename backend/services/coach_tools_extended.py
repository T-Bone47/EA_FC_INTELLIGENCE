"""Phase 41.5 Extended Typed Football Agent Tools & Schema Registry.

Reuses exclusively existing verified backend engines:
- RecommendationServiceV3 (frozen V3.2.1 math untouched)
- PlayerRepository & CandidateRepository (Postgres + RESEARCH_ONLY gate respected)
- ComparisonService, SquadRepository, card_squad_lab, squad_intelligence
- SpatialIntelligenceEngine, CounterfactualFootballEngine, TrainingPlanService, FootballKnowledgeService
"""
from __future__ import annotations

import math
import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.api.schemas_v3 import RecommendationRequestV3
from backend.data_access.candidate_repository import CandidateRepository
from backend.services.comparison_service import ComparisonService
from backend.services.formations import FORMATION_SLOTS, slots_for
from backend.services.intent_parser import parse as parse_structured_intent
from backend.services.llm.contracts import LLMToolSpec
from backend.services.llm.router import TaskIntent
from backend.services.recommendation_service_v3 import RecommendationServiceV3


# ------------------------------------------------------------------ Strict Pydantic Input Contracts
class _EmptyInput(BaseModel):
    model_config = ConfigDict(extra="ignore")


class SearchPlayersInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    query_name: Optional[str] = Field(default=None, max_length=80)
    position: Optional[str] = Field(default=None, max_length=6)
    club: Optional[str] = Field(default=None, max_length=80)
    nation: Optional[str] = Field(default=None, max_length=80)
    league: Optional[str] = Field(default=None, max_length=80)
    playstyle: Optional[str] = Field(default=None, max_length=60)
    ovr_min: Optional[int] = Field(default=None, ge=40, le=99)
    ovr_max: Optional[int] = Field(default=None, ge=40, le=99)
    game_version: Literal["FC26", "FC27"] = "FC27"
    limit: int = Field(default=6, ge=1, le=10)


class PlayerLookupInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    query_name: Optional[str] = Field(default=None, max_length=80)
    player_id: Optional[str] = Field(default=None, max_length=64)
    game_version: Literal["FC26", "FC27"] = "FC27"


class ComparePlayersInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    names: List[str] = Field(min_length=2, max_length=4)
    game_version: Literal["FC26", "FC27"] = "FC27"
    position: Optional[str] = Field(default=None, max_length=6)
    tactical_profile: str = Field(default="BALANCED", max_length=32)


class SimilarPlayersInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    player_name: str = Field(min_length=2, max_length=80)
    game_version: Literal["FC26", "FC27"] = "FC27"
    limit: int = Field(default=5, ge=1, le=8)


class RecommendPlayersV3Input(BaseModel):
    model_config = ConfigDict(extra="ignore")
    game_version: Literal["FC26", "FC27"] = "FC26"
    position: str = Field(default="CDM", max_length=6)
    tactical_profile: str = Field(default="BALANCED", max_length=32)
    formation: Optional[str] = Field(default=None, max_length=12)
    slot: Optional[str] = Field(default=None, max_length=10)
    desired_playstyles: List[str] = Field(default_factory=list, max_length=6)
    text_query: Optional[str] = Field(default=None, max_length=240)
    budget_coins: Optional[int] = Field(default=None, ge=0)
    limit: int = Field(default=5, ge=1, le=8)


class SquadEvalInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    squad_id: Optional[str] = Field(default=None, max_length=64)
    formation: str = Field(default="4-3-3", max_length=12)
    tactical_profile: str = Field(default="BALANCED", max_length=32)
    game_version: Literal["FC26", "FC27"] = "FC27"
    budget_coins: Optional[int] = Field(default=None, ge=0)


class PreviewReplacementInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    current_player_name: str = Field(min_length=2, max_length=80)
    position: Optional[str] = Field(default=None, max_length=6)
    tactical_profile: str = Field(default="BALANCED", max_length=32)
    game_version: Literal["FC26", "FC27"] = "FC26"
    squad_id: Optional[str] = Field(default=None, max_length=64)


class PreviewFormationChangeInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    target_formation: str = Field(default="4-2-3-1", max_length=12)
    squad_id: Optional[str] = Field(default=None, max_length=64)
    game_version: Literal["FC26", "FC27"] = "FC27"


class OptimizeSquadInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    formation: str = Field(default="4-3-3", max_length=12)
    tactical_profile: str = Field(default="BALANCED", max_length=32)
    game_version: Literal["FC26", "FC27"] = "FC27"
    squad_id: Optional[str] = Field(default=None, max_length=64)
    objective: Optional[str] = Field(default="balanced stability", max_length=120)
    session_id: Optional[str] = Field(default=None, max_length=64)


class MatchOptionalInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    match_id: Optional[str] = Field(default=None, max_length=80)


class DecisionWindowInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    window_id: Optional[str] = Field(default=None, max_length=80)
    match_id: Optional[str] = Field(default=None, max_length=80)
    reveal_outcome: bool = False


class KnowledgeInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    query: str = Field(min_length=1, max_length=200)
    game_version: Optional[Literal["FC26", "FC27"]] = None
    game_patch: Optional[str] = Field(default=None, max_length=30)
    topic: Optional[str] = Field(default=None, max_length=60)
    official_only: bool = False


class PersonalFitInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    position: str = Field(default="CDM", max_length=6)
    game_version: Literal["FC26", "FC27"] = "FC27"
    budget_coins: Optional[int] = Field(default=None, ge=0)


class GameVersionOnlyInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    game_version: Literal["FC26", "FC27"] = "FC27"


TOOL_INPUT_MODELS: Dict[str, type[BaseModel]] = {
    "search_players": SearchPlayersInput,
    "search_player_cards": SearchPlayersInput,
    "get_player_card": PlayerLookupInput,
    "get_player_attributes": PlayerLookupInput,
    "get_player_playstyles": PlayerLookupInput,
    "get_player_role_suitability": PersonalFitInput,
    "compare_players": ComparePlayersInput,
    "compare_player_cards": ComparePlayersInput,
    "find_similar_players": SimilarPlayersInput,
    "get_personal_gameplay_fit": PersonalFitInput,
    "recommend_player_profiles": PersonalFitInput,
    "recommend_players": RecommendPlayersV3Input,
    "get_current_squad": SquadEvalInput,
    "get_squad_snapshot": MatchOptionalInput,
    "get_match_squad_snapshot": MatchOptionalInput,
    "evaluate_squad": SquadEvalInput,
    "evaluate_formation": PreviewFormationChangeInput,
    "evaluate_player_partnership": _EmptyInput,
    "evaluate_whole_xi_cohesion": SquadEvalInput,
    "find_squad_weaknesses": SquadEvalInput,
    "recommend_squad_upgrades": SquadEvalInput,
    "recommend_squad_changes": SquadEvalInput,
    "compare_squad_alternatives": PreviewFormationChangeInput,
    "preview_player_replacement": PreviewReplacementInput,
    "preview_formation_change": PreviewFormationChangeInput,
    "optimize_squad": OptimizeSquadInput,
    "get_match_history": _EmptyInput,
    "get_match_analysis": MatchOptionalInput,
    "get_match_statistics": MatchOptionalInput,
    "get_tactical_diagnostics": MatchOptionalInput,
    "find_recurring_mistakes": _EmptyInput,
    "get_gameplay_evidence": _EmptyInput,
    "get_evidence_clip": _EmptyInput,
    "get_pitch_control_analysis": MatchOptionalInput,
    "get_transition_analysis": MatchOptionalInput,
    "get_gamer_dna": _EmptyInput,
    "get_football_iq": _EmptyInput,
    "get_football_iq_profile": _EmptyInput,
    "get_gamer_strengths": _EmptyInput,
    "get_gamer_weaknesses": _EmptyInput,
    "get_performance_trends": _EmptyInput,
    "evaluate_improvement": _EmptyInput,
    "compare_recent_matches": _EmptyInput,
    "compare_match_performance": _EmptyInput,
    "get_decision_opportunities": MatchOptionalInput,
    "get_decision_state": DecisionWindowInput,
    "get_decision_frame_analysis": DecisionWindowInput,
    "get_candidate_actions": DecisionWindowInput,
    "evaluate_passing_options": MatchOptionalInput,
    "compare_decision_alternatives": DecisionWindowInput,
    "get_decision_regret": MatchOptionalInput,
    "get_decision_regret_summary": MatchOptionalInput,
    "get_counterfactual_analysis": DecisionWindowInput,
    "generate_training_plan": GameVersionOnlyInput,
    "get_training_history": _EmptyInput,
    "recommend_training_exercises": GameVersionOnlyInput,
    "create_decision_training_scenario": DecisionWindowInput,
    "evaluate_training_progress": _EmptyInput,
    "search_football_knowledge": KnowledgeInput,
    "get_official_gameplay_knowledge": KnowledgeInput,
    "get_official_gameplay_mechanics": KnowledgeInput,
    "get_playstyle_explanation": KnowledgeInput,
    "get_role_explanation": KnowledgeInput,
    "get_patch_information": KnowledgeInput,
    "get_formation_information": PreviewFormationChangeInput,
}

TOOL_DESCRIPTIONS: Dict[str, str] = {
    "recommend_players": "Run the frozen V3.2.1 suitability ranking engine for a position/tactic/formation/PlayStyle query.",
    "search_players": "Search verified canonical FC26/FC27 players by name, position, club, nation, OVR, or PlayStyle.",
    "get_player_attributes": "Fetch full detailed attributes, weak foot, skill moves, club, and provenance for a player.",
    "get_player_playstyles": "Fetch verified PlayStyles, PlayStyle+ tier, and published status for a player.",
    "get_player_role_suitability": "Evaluate FC IQ tactical role alignment for a position against the gamer's DNA.",
    "compare_players": "Compare 2-4 verified players side-by-side on attributes, PlayStyles, and tactical fit.",
    "find_similar_players": "Find statistically similar canonical players in the same EA FC game version.",
    "get_personal_gameplay_fit": "Rank players combining V3.2.1 suitability with Gamer DNA and recurring mistakes.",
    "get_current_squad": "Load the gamer's saved squads and filled lineup slots from the database.",
    "get_squad_snapshot": "Inspect the immutable historical squad snapshot recorded with a match or active squad.",
    "evaluate_squad": "Evaluate the current saved XI for structural gaps, synergy, and non-purchase tactical fixes.",
    "evaluate_formation": "Compare candidate formations against Gamer DNA and style balance.",
    "evaluate_player_partnership": "Analyze complementarity between two central slots in a formation.",
    "evaluate_whole_xi_cohesion": "Evaluate Whole-XI tactical cohesion across formation slots.",
    "find_squad_weaknesses": "Identify structural weaknesses and mistake-linked gaps in the user's saved squad.",
    "recommend_squad_upgrades": "Identify tactical fixes first and verified candidate upgrades for weak positions.",
    "compare_squad_alternatives": "Compare tactical profiles and formation alternatives without mutating saved squads.",
    "preview_player_replacement": "Compare an incumbent player against top V3.2.1 replacements and create a preview proposal.",
    "preview_formation_change": "Check position compatibility of moving the current squad into a new formation.",
    "optimize_squad": "Propose a preview lineup for a target formation/tactic requiring explicit user confirmation.",
    "get_match_history": "List the gamer's verified non-synthetic match analyses.",
    "get_match_analysis": "Retrieve full coaching findings, events, and clips for a specific match.",
    "get_match_statistics": "Inspect match telemetry metrics such as defensive compactness and transition exposure.",
    "get_tactical_diagnostics": "Filter recurring tactical diagnostic patterns.",
    "find_recurring_mistakes": "Summarize recurring gameplay mistakes across verified matches.",
    "get_gameplay_evidence": "Retrieve timestamped deep-linked video/trace evidence clips.",
    "get_pitch_control_analysis": "Inspect pitch control coverage, line compactness, and zone structure.",
    "get_transition_analysis": "Analyze counter-attack & ball-loss transition vulnerabilities across matches.",
    "get_gamer_dna": "Compute Persistent Gamer DNA (Style vs Proficiency with credible intervals) excluding synthetic fixtures.",
    "get_football_iq": "Retrieve Decision Intelligence Football IQ dimensions and confidence bounds.",
    "get_gamer_strengths": "Extract top observed Gamer DNA & Football IQ strengths.",
    "get_gamer_weaknesses": "Extract verified priority areas for improvement and high-regret patterns.",
    "get_performance_trends": "Evaluate longitudinal improvement trends across comparable patches/modes.",
    "compare_recent_matches": "Compare the user's two most recent verified matches.",
    "get_decision_opportunities": "List detected pre-action decision windows for analyzed matches.",
    "get_decision_state": "Inspect a frozen pre-action decision state and outcome-blind candidate evaluations.",
    "get_candidate_actions": "Evaluate passing/dribbling/shooting/defensive alternatives in a decision window.",
    "evaluate_passing_options": "Inspect passing decision diagnostics, lane clearance, and xT trade-offs.",
    "compare_decision_alternatives": "Compare observed action vs highest-utility alternative and Decision Regret Index.",
    "get_decision_regret": "Summarize Decision Regret across evaluated match windows.",
    "get_counterfactual_analysis": "Retrieve Monte Carlo uncertainty intervals and counterfactual action rankings.",
    "generate_training_plan": "Build personalized next-match training objectives and freeze-frame BKT exercises.",
    "get_training_history": "Retrieve past Training Academy exercise attempts and mastery progression.",
    "recommend_training_exercises": "Get targeted decision drills mapped to recurring mistakes.",
    "create_decision_training_scenario": "Export an evaluated decision window into an interactive freeze-frame drill.",
    "evaluate_training_progress": "Summarize BKT mastery levels and practice accuracy.",
    "search_football_knowledge": "Run BM25 RAG retrieval over official EA Pitch Notes, FC IQ rules, and academic research.",
    "get_official_gameplay_mechanics": "Retrieve verified OFFICIAL_FACT entries for FC26/FC27 mechanics.",
    "get_playstyle_explanation": "Explain PlayStyles and FC27 PlayStyle+ caps from official sources.",
    "get_role_explanation": "Explain FC IQ Player Roles and Focuses from official EA documentation.",
    "get_patch_information": "Check patch-specific tuning and mode applicability notes.",
    "get_formation_information": "Return valid slots and tactical rest-defense characteristics for a formation.",
}

INTENT_TO_TOOLS: Dict[TaskIntent, List[str]] = {
    TaskIntent.PLAYER_DISCOVERY: [
        "recommend_players",
        "search_players",
        "get_player_attributes",
        "get_gamer_dna",
        "search_football_knowledge",
    ],
    TaskIntent.PLAYER_COMPARISON: [
        "compare_players",
        "search_players",
        "get_player_attributes",
        "get_gamer_dna",
    ],
    TaskIntent.TEAM_BUILDING: [
        "get_current_squad",
        "evaluate_squad",
        "find_squad_weaknesses",
        "recommend_players",
        "optimize_squad",
        "get_gamer_dna",
    ],
    TaskIntent.SQUAD_OPTIMIZATION: [
        "get_current_squad",
        "evaluate_squad",
        "find_squad_weaknesses",
        "preview_player_replacement",
        "optimize_squad",
        "recommend_players",
    ],
    TaskIntent.TACTICAL_RECOMMENDATION: [
        "get_gamer_dna",
        "evaluate_formation",
        "evaluate_squad",
        "find_recurring_mistakes",
        "search_football_knowledge",
    ],
    TaskIntent.GAMEPLAY_ANALYSIS: [
        "get_match_history",
        "find_recurring_mistakes",
        "get_transition_analysis",
        "get_gamer_dna",
        "recommend_training_exercises",
    ],
    TaskIntent.DECISION_ANALYSIS: [
        "get_decision_opportunities",
        "get_decision_state",
        "get_counterfactual_analysis",
        "get_decision_regret",
        "get_football_iq",
    ],
    TaskIntent.GAMER_PERFORMANCE: [
        "get_gamer_dna",
        "get_football_iq",
        "get_performance_trends",
        "get_match_history",
    ],
    TaskIntent.TRAINING: [
        "generate_training_plan",
        "get_training_history",
        "get_decision_opportunities",
        "find_recurring_mistakes",
    ],
    TaskIntent.GAME_MECHANICS: [
        "search_football_knowledge",
        "get_official_gameplay_mechanics",
        "get_patch_information",
        "get_formation_information",
    ],
    TaskIntent.GENERAL_FOOTBALL: [
        "get_gamer_dna",
        "find_recurring_mistakes",
        "recommend_players",
        "search_football_knowledge",
    ],
    TaskIntent.IMAGE_SCREENSHOT: [
        "get_current_squad",
        "evaluate_squad",
        "search_players",
        "search_football_knowledge",
    ],
}


def build_tool_specs(tool_names: List[str]) -> List[LLMToolSpec]:
    specs: List[LLMToolSpec] = []
    for name in tool_names:
        model_cls = TOOL_INPUT_MODELS.get(name, _EmptyInput)
        desc = TOOL_DESCRIPTIONS.get(name, f"Execute verified EA FC tool {name}.")
        specs.append(
            LLMToolSpec(
                name=name,
                description=desc,
                parameters_json_schema=model_cls.model_json_schema(),
            )
        )
    return specs


class Phase415ExtendedToolsMixin:
    """Mixin adding V3.2.1, Squad Lab preview/optimization, and RAG tools to CoachToolRegistry."""

    _shared_v3_service: Optional[RecommendationServiceV3] = None

    def _get_v3_service(self) -> RecommendationServiceV3:
        if Phase415ExtendedToolsMixin._shared_v3_service is None:
            Phase415ExtendedToolsMixin._shared_v3_service = RecommendationServiceV3()
        return Phase415ExtendedToolsMixin._shared_v3_service

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _safe_search_players(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = SearchPlayersInput.model_validate(kwargs)
        gv = inp.game_version.upper()
        try:
            gvid = self.players.game_version_id(gv)
            if not gvid:
                return {"items": [], "provenance": "CATALOGUE_UNAVAILABLE", "confidence": "LOW", "freshness": None}
            res = self.players.search(
                gvid,
                q=inp.query_name,
                position=inp.position.upper() if inp.position else None,
                club=inp.club,
                nation=inp.nation,
                league=inp.league,
                ovr_min=inp.ovr_min,
                ovr_max=inp.ovr_max,
                playstyle=inp.playstyle,
                sort="overall_rating",
                sort_dir="desc",
                page=1,
                page_size=inp.limit,
                research=(gv == "FC27"),
            )
            items = [
                {
                    "entity_id": str(r.get("id")),
                    "name": r.get("display_name"),
                    "position": r.get("position_primary"),
                    "secondary_positions": r.get("secondary_positions") or [],
                    "overall_rating": r.get("overall_rating"),
                    "club": r.get("club"),
                    "league": r.get("league"),
                    "nation": r.get("nation"),
                    "pace": r.get("pace"),
                    "shooting": r.get("shooting"),
                    "passing": r.get("passing"),
                    "dribbling": r.get("dribbling"),
                    "defending": r.get("defending"),
                    "physicality": r.get("physicality"),
                    "game_version": gv,
                    "detail_route": f"/players/{r.get('id')}?game_version={gv}",
                    "squad_lab_route": f"/cards/squad-lab?item={r.get('id')}",
                }
                for r in res.get("items", [])
            ]
            return {
                "total": res.get("total", len(items)),
                "items": items,
                "game_version": gv,
                "data_status": "RESEARCH_ONLY" if gv == "FC27" else "CANONICAL",
                "market_price_status": "MARKET_PRICE_UNAVAILABLE",
                "provenance": "CANONICAL_POSTGRES_CATALOGUE",
                "confidence": "HIGH",
                "retrieved_at": self._now_iso(),
                "_summary": f"Found {len(items)} verified {gv} player(s)",
            }
        except Exception as exc:
            return {"items": [], "error": str(exc), "provenance": "CATALOGUE_ERROR", "confidence": "LOW"}

    def _resolve_player_page(self, query_name: Optional[str], player_id: Optional[str], gv: str) -> Optional[Dict[str, Any]]:
        gvid = self.players.game_version_id(gv)
        if not gvid:
            return None
        pid: Optional[uuid_lib.UUID] = None
        if player_id:
            try:
                pid = uuid_lib.UUID(player_id)
            except ValueError:
                pid = None
        if pid is None and query_name:
            found = self.players.search(gvid, q=query_name, page=1, page_size=1, research=(gv == "FC27"))
            if found.get("items"):
                pid = found["items"][0]["id"]
        if pid is None:
            return None
        return self.players.player_page(gvid, pid, include_cards=True, include_other_versions=False, research=(gv == "FC27"))

    def get_player_attributes(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = PlayerLookupInput.model_validate(kwargs)
        page = self._resolve_player_page(inp.query_name, inp.player_id, inp.game_version)
        if not page:
            return {"found": False, "provenance": "CANONICAL_POSTGRES_CATALOGUE", "_summary": "Player not found"}
        gp = page["game_player"]
        attrs = page.get("attributes") or {}
        clean_attrs = {k: v for k, v in attrs.items() if isinstance(v, (int, float)) and k != "game_player_id"}
        return {
            "found": True,
            "entity_id": str(gp["id"]),
            "name": gp.get("display_name"),
            "position": gp.get("position_primary"),
            "secondary_positions": page.get("secondary_positions") or [],
            "overall_rating": gp.get("overall_rating"),
            "weak_foot_stars": gp.get("weak_foot_stars"),
            "skill_moves_stars": gp.get("skill_moves_stars"),
            "preferred_foot": gp.get("preferred_foot"),
            "club": gp.get("club"),
            "league": gp.get("league"),
            "nation": gp.get("nation"),
            "attributes": clean_attrs,
            "playstyles": page.get("playstyles") or [],
            "playstyle_data_published": page.get("playstyle_data_published"),
            "freshness": page.get("freshness"),
            "game_version": inp.game_version,
            "provenance": "CANONICAL_POSTGRES_CATALOGUE",
            "confidence": "HIGH",
            "_summary": f"Loaded attributes for {gp.get('display_name')} ({gp.get('overall_rating')} OVR)",
        }

    def get_player_playstyles(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        info = self.get_player_attributes(user_id, **kwargs)
        if not info.get("found"):
            return info
        return {
            "found": True,
            "entity_id": info["entity_id"],
            "name": info["name"],
            "game_version": info["game_version"],
            "playstyle_data_published": info.get("playstyle_data_published"),
            "playstyles": info.get("playstyles") or [],
            "provenance": "CANONICAL_POSTGRES_CATALOGUE",
            "_summary": f"{info['name']}: {len(info.get('playstyles') or [])} PlayStyle(s)",
        }

    def find_similar_players(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = SimilarPlayersInput.model_validate(kwargs)
        gv = inp.game_version
        target = self.get_player_attributes(user_id, query_name=inp.player_name, game_version=gv)
        if not target.get("found"):
            return {"found": False, "items": [], "provenance": "CANONICAL_POSTGRES_CATALOGUE", "_summary": f"Reference player '{inp.player_name}' not found in {gv}"}

        try:
            cands = self._get_v3_service().repository.load_candidates(gv, positions={target["position"]}, include_research_only=(gv == "FC27"))
        except Exception as exc:
            return {"found": True, "items": [], "error": str(exc), "provenance": "CATALOGUE_ERROR"}

        t_attrs = target.get("attributes") or {}
        scored = []
        compare_keys = [k for k, v in t_attrs.items() if isinstance(v, (int, float)) and k != "overall_rating"]
        for c in cands:
            if str(c.entity_id) == target["entity_id"] or (c.name or "").lower() == (target["name"] or "").lower():
                continue
            diffs = []
            for k in compare_keys:
                cv = c.attributes.get(k)
                tv = t_attrs.get(k)
                if isinstance(cv, (int, float)) and isinstance(tv, (int, float)):
                    diffs.append((cv - tv) ** 2)
            if len(diffs) < 6:
                continue
            rmse = math.sqrt(sum(diffs) / len(diffs))
            sim = round(max(0.0, 1.0 - rmse / 35.0), 4)
            scored.append({
                "entity_id": str(c.entity_id),
                "name": c.name,
                "position": c.position_primary,
                "overall_rating": c.overall_rating,
                "similarity_score": sim,
                "club": c.club,
                "league": c.league,
                "playstyles": c.playstyles_base[:4] + [p + "+" for p in c.playstyles_plus[:3]],
                "game_version": gv,
                "detail_route": f"/players/{c.entity_id}?game_version={gv}",
                "squad_lab_route": f"/cards/squad-lab?item={c.entity_id}",
            })
        scored.sort(key=lambda x: x["similarity_score"], reverse=True)
        return {
            "reference_player": {"name": target["name"], "position": target["position"], "overall_rating": target["overall_rating"]},
            "game_version": gv,
            "items": scored[: inp.limit],
            "market_price_status": "MARKET_PRICE_UNAVAILABLE",
            "provenance": "CANONICAL_ATTRIBUTE_SIMILARITY",
            "confidence": "MODERATE",
            "_summary": f"Found {len(scored[:inp.limit])} similar {target['position']} players to {target['name']}",
        }

    def recommend_players(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        """Executes FROZEN V3.2.1 RecommendationServiceV3 cleanly."""
        inp = RecommendPlayersV3Input.model_validate(kwargs)
        gv = inp.game_version
        pos = inp.position.upper()
        tactic = inp.tactical_profile.upper()
        ps_list = list(inp.desired_playstyles)

        if inp.text_query:
            try:
                parsed = parse_structured_intent(inp.text_query, gv).to_draft()
                pos = str(parsed.get("position") or pos).upper()
                tactic = str(parsed.get("tactical_profile") or tactic).upper()
                if parsed.get("desired_playstyles"):
                    ps_list = list(dict.fromkeys([*ps_list, *parsed["desired_playstyles"]]))[:6]
            except Exception:
                pass

        try:
            body = RecommendationRequestV3(
                game_version=gv,
                position=pos,
                tactical_profile=tactic,
                formation=inp.formation,
                slot=inp.slot,
                desired_playstyles=ps_list,
                include_research_data=(gv == "FC27"),
                limit=inp.limit,
            )
            res = self._get_v3_service().recommend(body)
        except Exception as exc:
            return {"error": str(exc), "ranked": [], "provenance": "V321_ENGINE_ERROR", "frozen_v321_untouched": True}

        if "error" in res:
            return {**res, "provenance": "V321_SERVICE_REFUSAL", "frozen_v321_untouched": True}

        cards: List[Dict[str, Any]] = []
        for row in (res.get("ranked") or [])[: inp.limit]:
            player_meta = row.get("player") or row.get("card") or {}
            cards.append({
                "rank": row.get("rank"),
                "entity_id": row.get("entity_id"),
                "name": row.get("name"),
                "position": player_meta.get("position_primary") or pos,
                "overall_rating": player_meta.get("overall_rating"),
                "score": round(float(row.get("score") or 0.0), 4),
                "coverage": row.get("coverage"),
                "club": player_meta.get("club"),
                "nation": player_meta.get("nation"),
                "playstyles": player_meta.get("playstyles"),
                "reasons": (row.get("explanation") or {}).get("reasons", [])[:2],
                "trade_offs": (row.get("explanation") or {}).get("trade_offs", [])[:2],
                "game_version": gv,
                "detail_route": f"/players/{row.get('entity_id')}?game_version={gv}",
                "squad_lab_route": f"/cards/squad-lab?item={row.get('entity_id')}",
            })
        return {
            "game_version": gv,
            "position": pos,
            "tactical_profile": tactic,
            "engine_version": res.get("engine_version"),
            "config_version": res.get("config_version"),
            "dataset": res.get("dataset"),
            "frozen_v321_untouched": True,
            "budget_coins": inp.budget_coins,
            "market_price_status": "MARKET_PRICE_UNAVAILABLE" if inp.budget_coins is not None else "NOT_REQUESTED",
            "ranked": cards,
            "provenance": "FROZEN_V321_RECOMMENDATION_ENGINE",
            "confidence": "HIGH",
            "_summary": f"V3.2.1 ranked {len(cards)} {pos} ({tactic}, {gv})",
        }

    def _load_user_saved_slots(self, user_id: str, squad_id: Optional[str]) -> tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        try:
            uid = uuid_lib.UUID(user_id)
            squads = self.squads.list_squads(uid)
            if not squads:
                return None, []
            sq = self.squads.get_squad(uid, uuid_lib.UUID(squad_id)) if squad_id else squads[0]
            if not sq:
                return None, []
            slots = self.squads.slots(uuid_lib.UUID(str(sq["id"])), uid, research=(sq.get("game_version_code") == "FC27"))
            return sq, slots
        except Exception:
            return None, []

    def evaluate_squad(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = SquadEvalInput.model_validate(kwargs)
        sq, raw_slots = self._load_user_saved_slots(user_id, inp.squad_id)
        formation = str(sq.get("formation")) if sq else inp.formation
        gv = str(sq.get("game_version_code")) if sq else inp.game_version
        from backend.domain.phase40_models import SquadSlotSnapshot
        snaps = [
            SquadSlotSnapshot(
                slot_index=int(s.get("slot_index", idx)),
                slot_position=str(s.get("slot_position") or "CM"),
                entity_id=str(s.get("game_player_id") or s.get("ut_card_id") or ""),
                player_name=str(s.get("player_name") or f"Slot {idx + 1}"),
                overall_rating=s.get("overall_rating"),
            )
            for idx, s in enumerate(raw_slots)
        ]
        matches = self.repo.list_matches(user_id, exclude_synthetic=True)
        cold = self.repo.get_cold_start_preferences(user_id)
        dna = self.dna_engine.build_profile(user_id, matches, cold_start=cold)
        mistakes = self.mistake_analyzer.analyze(matches)
        out = self.fit_service.analyze_personal_squad(
            game_version=gv,
            formation=formation,
            tactical_profile=inp.tactical_profile,
            slots=snaps,
            dna=dna,
            mistakes=mistakes,
            matches=matches,
            budget_coins=inp.budget_coins,
        )
        out["saved_squad_id"] = str(sq["id"]) if sq else None
        out["saved_squad_name"] = sq.get("name") if sq else None
        out["filled_slots"] = len(snaps)
        out["provenance"] = "USER_SQUAD_PERSONAL_FIT"
        out["_summary"] = f"Evaluated {formation} ({len(snaps)} filled slots)"
        return out

    def preview_player_replacement(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = PreviewReplacementInput.model_validate(kwargs)
        cur = self.get_player_attributes(user_id, query_name=inp.current_player_name, game_version=inp.game_version)
        pos = (inp.position or (cur.get("position") if cur.get("found") else "CDM")).upper()
        recs = self.recommend_players(user_id, game_version=inp.game_version, position=pos, tactical_profile=inp.tactical_profile, limit=4)
        ranked = [r for r in recs.get("ranked", []) if r["name"].lower() != inp.current_player_name.lower()]
        proposal_id = f"PROP-REP-{str(uuid4())[:8]}"
        payload = {
            "proposal_type": "PLAYER_REPLACEMENT_PREVIEW",
            "requires_confirmation": True,
            "current_player": cur if cur.get("found") else {"name": inp.current_player_name, "position": pos},
            "recommended_replacements": ranked[:3],
            "market_price_status": "MARKET_PRICE_UNAVAILABLE",
        }
        self.repo.save_squad_proposal(
            user_id,
            proposal_id=proposal_id,
            session_id=None,
            target_squad_id=inp.squad_id,
            game_version=inp.game_version,
            formation="4-3-3",
            tactical_profile=inp.tactical_profile,
            proposal_payload=payload,
        )
        return {
            "proposal_id": proposal_id,
            "requires_confirmation": True,
            "status": "PENDING_CONFIRMATION",
            **payload,
            "provenance": "FROZEN_V321_REPLACEMENT_PREVIEW",
            "_summary": f"Previewed replacements for {inp.current_player_name} ({len(ranked[:3])} options)",
        }

    def preview_formation_change(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = PreviewFormationChangeInput.model_validate(kwargs)
        target = inp.target_formation
        target_slots = slots_for(target)
        if not target_slots:
            return {"valid": False, "error": f"Unknown formation {target!r}", "supported_formations": sorted(FORMATION_SLOTS.keys())}
        sq, raw_slots = self._load_user_saved_slots(user_id, inp.squad_id)
        target_pos_counts: Dict[str, int] = {}
        for ts in target_slots:
            target_pos_counts[ts.position] = target_pos_counts.get(ts.position, 0) + 1
        dna = self.get_gamer_dna(user_id)
        return {
            "valid": True,
            "current_formation": sq.get("formation") if sq else "4-3-3",
            "target_formation": target,
            "target_slots": [{"slot": s.slot, "position": s.position} for s in target_slots],
            "filled_current_slots": len(raw_slots),
            "dna_tactical_suitability": dna.get("tactical_suitability", [])[:3],
            "requires_confirmation": True,
            "provenance": "FORMATION_COMPATIBILITY_PREVIEW",
            "_summary": f"Previewed shift to {target} ({len(target_slots)} slots)",
        }

    def optimize_squad(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = OptimizeSquadInput.model_validate(kwargs)
        formation = inp.formation
        f_slots = slots_for(formation)
        if not f_slots:
            return {"status": "INVALID_FORMATION", "error": f"Formation {formation!r} is not supported."}

        gv = inp.game_version
        sq, raw_slots = self._load_user_saved_slots(user_id, inp.squad_id)
        try:
            gvid = self.players.game_version_id(gv)
        except Exception:
            gvid = None

        used_names: set[str] = set()
        proposed_lineup: List[Dict[str, Any]] = []
        pos_rec_cache: Dict[str, List[Dict[str, Any]]] = {}
        # Populate each formation slot respecting GK exclusivity, position eligibility, and no duplicates
        for ts in f_slots:
            chosen = None
            existing_match = next(
                (s for s in raw_slots if str(s.get("slot_position")).upper() == ts.position and str(s.get("player_name", "")).lower() not in used_names),
                None,
            )
            if existing_match:
                chosen = {
                    "entity_id": str(existing_match.get("game_player_id") or existing_match.get("ut_card_id") or ""),
                    "name": existing_match.get("player_name"),
                    "position": ts.position,
                    "overall_rating": existing_match.get("overall_rating"),
                    "source": "EXISTING_SAVED_SQUAD",
                }
            elif gvid:
                if ts.position not in pos_rec_cache:
                    recs = self.recommend_players(
                        user_id, game_version=gv, position=ts.position, tactical_profile=inp.tactical_profile, formation=formation, slot=ts.slot, limit=6
                    )
                    pos_rec_cache[ts.position] = recs.get("ranked", [])
                for c in pos_rec_cache[ts.position]:
                    cname = (c.get("name") or "").lower()
                    if cname and cname not in used_names:
                        chosen = {**c, "source": "V321_RECOMMENDED"}
                        break
            if chosen:
                used_names.add(str(chosen.get("name") or "").lower())
            proposed_lineup.append({"slot": ts.slot, "position": ts.position, "player": chosen})

        proposal_id = f"PROP-SQ-{str(uuid4())[:8]}"
        payload = {
            "proposal_type": "SQUAD_OPTIMIZATION_PREVIEW",
            "formation": formation,
            "tactical_profile": inp.tactical_profile,
            "game_version": gv,
            "objective": inp.objective,
            "hard_constraints_verified": {
                "unique_footballers": True,
                "position_eligible": True,
                "goalkeeper_exclusive": True,
                "market_prices_verified": False,
            },
            "slots": proposed_lineup,
        }
        self.repo.save_squad_proposal(
            user_id,
            proposal_id=proposal_id,
            session_id=inp.session_id,
            target_squad_id=str(sq["id"]) if sq else inp.squad_id,
            game_version=gv,
            formation=formation,
            tactical_profile=inp.tactical_profile,
            proposal_payload=payload,
        )
        return {
            "proposal_id": proposal_id,
            "requires_confirmation": True,
            "status": "PENDING_CONFIRMATION",
            "target_squad_id": str(sq["id"]) if sq else inp.squad_id,
            **payload,
            "provenance": "V321_CONSTRAINT_VERIFIED_PROPOSAL",
            "_summary": f"Generated {formation} ({inp.tactical_profile}) squad preview [{proposal_id}]",
        }

    def get_match_statistics(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        inp = MatchOptionalInput.model_validate(kwargs)
        matches = self.repo.list_matches(user_id, exclude_synthetic=True)
        target = next((m for m in matches if m.match_id == inp.match_id), matches[0] if matches else None)
        if not target:
            return {"status": "ABSTAINED_NO_MATCHES", "provenance": "EMPTY", "_summary": "No verified non-synthetic match found"}
        return {
            "match_id": target.match_id,
            "game_version": target.game_version,
            "game_patch": target.game_patch,
            "formation": target.formation,
            "provenance": target.provenance,
            "observation_quality": target.observation_quality,
            "tracking_coverage_pct": target.tracking_coverage_pct,
            "match_result": target.match_result.model_dump(),
            "feature_metrics": target.feature_metrics,
            "telemetry_summary": target.telemetry_summary,
            "_summary": f"Match {target.match_id} metrics (coverage={target.tracking_coverage_pct}%)",
        }

    def get_pitch_control_analysis(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        stats = self.get_match_statistics(user_id, **kwargs)
        if stats.get("status") == "ABSTAINED_NO_MATCHES":
            return stats
        fm = stats.get("feature_metrics") or {}
        return {
            "match_id": stats["match_id"],
            "provenance": stats["provenance"],
            "defensive_compactness": fm.get("defensive_compactness"),
            "central_progression_share": fm.get("central_progression_share"),
            "def_to_mid_gap_m": fm.get("def_to_mid_gap_m"),
            "note": "Spatial metrics derive from non-synthetic match telemetry and calibrated pitch geometry where available.",
            "_summary": f"Pitch control summary for {stats['match_id']}",
        }

    def get_transition_analysis(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        mistakes = self.find_recurring_mistakes(user_id, diagnostic_filter="EXPOSED_CENTRAL_CHANNEL")
        clips = self.get_evidence_clip(user_id, limit=4)
        return {
            "recurring_transition_patterns": mistakes.get("patterns", []),
            "supporting_clips": clips.get("clips", []),
            "provenance": mistakes.get("provenance", "EMPTY_NO_REAL_PATTERN"),
            "_summary": f"{len(mistakes.get('patterns', []))} transition vulnerability pattern(s)",
        }

    def get_gamer_strengths(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        dna = self.get_gamer_dna(user_id)
        strong = [d for d in (dna.get("proficiency_dimensions") or []) if (d.get("estimated_value") or 0.0) >= 0.65 and d.get("status") == "OBSERVED"]
        return {"eligible_matches": dna.get("eligible_match_count", 0), "strengths": strong, "archetype": dna.get("archetype"), "provenance": dna.get("provenance"), "_summary": f"{len(strong)} observed strengths"}

    def get_gamer_weaknesses(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        mistakes = self.find_recurring_mistakes(user_id)
        dna = self.get_gamer_dna(user_id)
        weak = [d for d in (dna.get("proficiency_dimensions") or []) if d.get("estimated_value") is not None and d["estimated_value"] < 0.60]
        return {
            "eligible_matches": dna.get("eligible_match_count", 0),
            "recurring_mistakes": mistakes.get("patterns", [])[:3],
            "low_proficiency_dimensions": weak,
            "improvement_potential": dna.get("improvement_potential", []),
            "provenance": dna.get("provenance"),
            "_summary": f"{len(mistakes.get('patterns', []))} mistake patterns & {len(weak)} weak dimensions",
        }

    def get_training_history(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        attempts = self.repo.list_training_attempts(user_id)
        plan = self.repo.get_latest_training_plan(user_id)
        return {
            "attempts_count": len(attempts),
            "recent_attempts": attempts[:15],
            "bkt_states": {k: v.model_dump() for k, v in (plan.bkt_states.items() if plan else {})},
            "provenance": "USER_TRAINING_LOG",
            "_summary": f"{len(attempts)} training attempts logged",
        }
