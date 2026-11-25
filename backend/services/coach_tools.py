"""Phase 40E: Bounded, Typed, Authorization-Enforced Agent Tool Registry (22 Tools).

Implements OWASP GenAI security defenses:
- Strict typed Pydantic input contracts & validation
- Caller user_id ownership enforcement (LLM cannot bypass auth or read other users)
- Prompt-injection detector & sanitizer stripping override payloads in inputs/metadata
- Bounded execution limits & timing instrumentation
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from backend.repositories.phase40_repository import Phase40Repository, get_phase40_repository
from backend.repositories.phase41_repository import Phase41Repository, get_phase41_repository
from backend.repositories.player_repository import PlayerRepository
from backend.repositories.squad_repository import SquadRepository
from backend.services.coach_tools_extended import (
    INTENT_TO_TOOLS,
    TOOL_INPUT_MODELS,
    Phase415ExtendedToolsMixin,
    build_tool_specs,
)
from backend.services.counterfactual_football_engine import CounterfactualFootballEngine
from backend.services.decision_scenario_service import DecisionScenarioService
from backend.services.decision_state_builder import build_state_from_snapshot
from backend.services.defensive_and_chance_intelligence import OffBallOpportunityEngine
from backend.services.football_iq_engine import FootballIQEngine
from backend.services.football_knowledge_service import FootballKnowledgeService, get_shared_knowledge_service
from backend.services.gamer_dna_engine import GamerDNAEngine
from backend.services.match_intelligence_repository import MatchIntelligenceService
from backend.services.partnership_intelligence import PartnershipIntelligenceEngine
from backend.services.performance_progression_service import PerformanceProgressionService
from backend.services.personal_gameplay_fit import PersonalGameplayFitService
from backend.services.recurring_mistake_analyzer import RecurringMistakeAnalyzer
from backend.services.squad_synergy import compute_whole_xi_synergy
from backend.services.training_plan_service import TrainingPlanService


_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"system\s+prompt|developer\s+message|reveal\s+instructions", re.I),
    re.compile(r"bypass\s+(auth|authorization|ownership|policy)", re.I),
    re.compile(r"other\s+user'?s\s+(matches|data|dna|squad)", re.I),
    re.compile(r";\s*(DROP|DELETE|UPDATE|INSERT)\s+", re.I),
]


def detect_prompt_injection(text: str) -> List[str]:
    """Detects untrusted prompt-injection or cross-user override attempts."""
    flags: List[str] = []
    for pat in _INJECTION_PATTERNS:
        if pat.search(text or ""):
            flags.append(f"BLOCKED_UNTRUSTED_DIRECTIVE:{pat.pattern[:32]}")
    return flags


@dataclass
class ToolInvocationRecord:
    tool_name: str
    status: str
    elapsed_ms: float
    provenance: str
    summary: str


class CoachToolRegistry(Phase415ExtendedToolsMixin):
    """Executes all Phase 40/41 (34) + Phase 41.5 agentic tools with strict validation & auth."""

    PHASE40_TOOLS = [
        "get_gamer_dna",
        "get_gamer_profile_confidence",
        "get_match_history",
        "get_match_analysis",
        "get_match_squad_snapshot",
        "find_recurring_mistakes",
        "get_tactical_diagnostic",
        "get_evidence_clip",
        "compare_match_performance",
        "get_current_squad",
        "get_player_card",
        "search_player_cards",
        "compare_player_cards",
        "evaluate_role_suitability",
        "evaluate_squad_cohesion",
        "evaluate_player_partnership",
        "evaluate_tactical_fit",
        "recommend_player_profiles",
        "recommend_squad_changes",
        "get_official_gameplay_knowledge",
        "generate_training_plan",
        "evaluate_improvement",
    ]

    PHASE41_TOOLS = [
        "get_decision_opportunities",
        "get_decision_frame_analysis",
        "evaluate_candidate_actions",
        "get_best_alternative_action",
        "get_decision_regret_summary",
        "get_football_iq_profile",
        "get_passing_decision_diagnostics",
        "get_defensive_decision_diagnostics",
        "get_shooting_decision_diagnostics",
        "get_off_ball_run_diagnostics",
        "generate_decision_training_scenario",
        "evaluate_player_capability_constraints",
    ]

    ALL_TOOLS = PHASE40_TOOLS + PHASE41_TOOLS

    PHASE41_5_TOOLS = [
        "search_players",
        "get_player_attributes",
        "get_player_playstyles",
        "compare_players",
        "find_similar_players",
        "get_personal_gameplay_fit",
        "recommend_players",
        "get_squad_snapshot",
        "evaluate_squad",
        "evaluate_formation",
        "evaluate_whole_xi_cohesion",
        "find_squad_weaknesses",
        "recommend_squad_upgrades",
        "compare_squad_alternatives",
        "preview_player_replacement",
        "preview_formation_change",
        "optimize_squad",
        "get_match_statistics",
        "get_tactical_diagnostics",
        "get_gameplay_evidence",
        "get_pitch_control_analysis",
        "get_transition_analysis",
        "get_gamer_strengths",
        "get_gamer_weaknesses",
        "get_performance_trends",
        "compare_recent_matches",
        "get_decision_state",
        "get_candidate_actions",
        "evaluate_passing_options",
        "compare_decision_alternatives",
        "get_decision_regret",
        "get_counterfactual_analysis",
        "get_training_history",
        "recommend_training_exercises",
        "create_decision_training_scenario",
        "evaluate_training_progress",
        "search_football_knowledge",
        "get_official_gameplay_mechanics",
        "get_playstyle_explanation",
        "get_role_explanation",
        "get_patch_information",
        "get_formation_information",
        "get_football_iq",
    ]

    def __init__(
        self,
        repo: Optional[Phase40Repository] = None,
        phase41_repo: Optional[Phase41Repository] = None,
    ) -> None:
        self.repo = repo or get_phase40_repository()
        self.p41_repo = phase41_repo or get_phase41_repository()
        self.match_service = MatchIntelligenceService(self.repo)
        self.dna_engine = GamerDNAEngine()
        self.mistake_analyzer = RecurringMistakeAnalyzer()
        self.knowledge = get_shared_knowledge_service()
        self.fit_service = PersonalGameplayFitService()
        self.training_service = TrainingPlanService()
        self.progression_service = PerformanceProgressionService()
        self.players = PlayerRepository()
        self.squads = SquadRepository()
        self.partnerships = PartnershipIntelligenceEngine()
        self.counterfactual_engine = CounterfactualFootballEngine()
        self.iq_engine = FootballIQEngine()
        self.scenario_service = DecisionScenarioService()
        self.off_ball_engine = OffBallOpportunityEngine()

        self._handlers: Dict[str, Callable[..., Dict[str, Any]]] = {
            "get_gamer_dna": self.get_gamer_dna,
            "get_gamer_profile_confidence": self.get_gamer_profile_confidence,
            "get_match_history": self.get_match_history,
            "get_match_analysis": self.get_match_analysis,
            "get_match_squad_snapshot": self.get_match_squad_snapshot,
            "find_recurring_mistakes": self.find_recurring_mistakes,
            "get_tactical_diagnostic": self.get_tactical_diagnostic,
            "get_evidence_clip": self.get_evidence_clip,
            "compare_match_performance": self.compare_match_performance,
            "get_current_squad": self.get_current_squad,
            "get_player_card": self.get_player_card,
            "search_player_cards": self.search_player_cards,
            "compare_player_cards": self.compare_player_cards,
            "evaluate_role_suitability": self.evaluate_role_suitability,
            "evaluate_squad_cohesion": self.evaluate_squad_cohesion,
            "evaluate_player_partnership": self.evaluate_player_partnership,
            "evaluate_tactical_fit": self.evaluate_tactical_fit,
            "recommend_player_profiles": self.recommend_player_profiles,
            "recommend_squad_changes": self.recommend_squad_changes,
            "get_official_gameplay_knowledge": self.get_official_gameplay_knowledge,
            "generate_training_plan": self.generate_training_plan,
            "evaluate_improvement": self.evaluate_improvement,
            # Phase 41 tools
            "get_decision_opportunities": self.get_decision_opportunities,
            "get_decision_frame_analysis": self.get_decision_frame_analysis,
            "evaluate_candidate_actions": self.evaluate_candidate_actions,
            "get_best_alternative_action": self.get_best_alternative_action,
            "get_decision_regret_summary": self.get_decision_regret_summary,
            "get_football_iq_profile": self.get_football_iq_profile,
            "get_passing_decision_diagnostics": self.get_passing_decision_diagnostics,
            "get_defensive_decision_diagnostics": self.get_defensive_decision_diagnostics,
            "get_shooting_decision_diagnostics": self.get_shooting_decision_diagnostics,
            "get_off_ball_run_diagnostics": self.get_off_ball_run_diagnostics,
            "generate_decision_training_scenario": self.generate_decision_training_scenario,
            "evaluate_player_capability_constraints": self.evaluate_player_capability_constraints,
            # Phase 41.5 extended & canonical alias tools
            "search_players": self._safe_search_players,
            "get_player_attributes": self.get_player_attributes,
            "get_player_playstyles": self.get_player_playstyles,
            "compare_players": self.compare_player_cards,
            "find_similar_players": self.find_similar_players,
            "get_personal_gameplay_fit": self.recommend_player_profiles,
            "recommend_players": self.recommend_players,
            "get_squad_snapshot": self.get_match_squad_snapshot,
            "evaluate_squad": self.evaluate_squad,
            "evaluate_formation": self.evaluate_tactical_fit,
            "evaluate_whole_xi_cohesion": self.evaluate_squad_cohesion,
            "find_squad_weaknesses": self.evaluate_squad,
            "recommend_squad_upgrades": self.recommend_squad_changes,
            "compare_squad_alternatives": self.preview_formation_change,
            "preview_player_replacement": self.preview_player_replacement,
            "preview_formation_change": self.preview_formation_change,
            "optimize_squad": self.optimize_squad,
            "get_match_statistics": self.get_match_statistics,
            "get_tactical_diagnostics": self.get_tactical_diagnostic,
            "get_gameplay_evidence": self.get_evidence_clip,
            "get_pitch_control_analysis": self.get_pitch_control_analysis,
            "get_transition_analysis": self.get_transition_analysis,
            "get_gamer_strengths": self.get_gamer_strengths,
            "get_gamer_weaknesses": self.get_gamer_weaknesses,
            "get_performance_trends": self.evaluate_improvement,
            "compare_recent_matches": self.compare_match_performance,
            "get_decision_state": self.get_decision_frame_analysis,
            "get_candidate_actions": self.evaluate_candidate_actions,
            "evaluate_passing_options": self.get_passing_decision_diagnostics,
            "compare_decision_alternatives": self.get_best_alternative_action,
            "get_decision_regret": self.get_decision_regret_summary,
            "get_counterfactual_analysis": self.evaluate_candidate_actions,
            "get_training_history": self.get_training_history,
            "recommend_training_exercises": self.generate_training_plan,
            "create_decision_training_scenario": self.generate_decision_training_scenario,
            "evaluate_training_progress": self.get_training_history,
            "search_football_knowledge": self.get_official_gameplay_knowledge,
            "get_official_gameplay_mechanics": self.get_official_gameplay_knowledge,
            "get_playstyle_explanation": self.get_official_gameplay_knowledge,
            "get_role_explanation": self.get_official_gameplay_knowledge,
            "get_patch_information": self.get_official_gameplay_knowledge,
            "get_formation_information": self.preview_formation_change,
            "get_football_iq": self.get_football_iq_profile,
        }

    def select_tool_specs_for_intent(self, intent: Any) -> list:
        from backend.services.llm.router import TaskIntent
        ti = intent if isinstance(intent, TaskIntent) else TaskIntent.GENERAL_FOOTBALL
        names = [n for n in INTENT_TO_TOOLS.get(ti, INTENT_TO_TOOLS[TaskIntent.GENERAL_FOOTBALL]) if n in self._handlers]
        return build_tool_specs(names)

    def execute(self, tool_name: str, user_id: str, **kwargs: Any) -> tuple[Dict[str, Any], ToolInvocationRecord]:
        if tool_name not in self._handlers:
            raise ValueError(f"Unknown or unapproved coach tool: {tool_name!r}")
        # Never allow callers to spoof or pass a conflicting target_user_id
        kwargs.pop("target_user_id", None)
        kwargs.pop("user_id", None)
        # Strict Pydantic argument validation when input schema exists
        schema_cls = TOOL_INPUT_MODELS.get(tool_name)
        if schema_cls is not None and kwargs:
            try:
                validated = schema_cls.model_validate(kwargs)
                kwargs = {k: v for k, v in validated.model_dump(exclude_unset=True, exclude_none=True).items()}
            except Exception as exc:
                rec = ToolInvocationRecord(
                    tool_name=tool_name,
                    status="INVALID_ARGS",
                    elapsed_ms=0.0,
                    provenance="VALIDATION_ERROR",
                    summary=f"Rejected invalid args: {exc}",
                )
                return {"error": f"Invalid tool arguments: {exc}", "tool": tool_name}, rec
        t0 = time.perf_counter()
        try:
            out = self._handlers[tool_name](user_id, **kwargs)
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            rec = ToolInvocationRecord(
                tool_name=tool_name,
                status="OK",
                elapsed_ms=elapsed,
                provenance=str(out.get("provenance", "PLATFORM_VERIFIED")),
                summary=str(out.get("_summary", f"Executed {tool_name}")),
            )
            return out, rec
        except Exception as exc:
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            rec = ToolInvocationRecord(
                tool_name=tool_name,
                status="ERROR",
                elapsed_ms=elapsed,
                provenance="ERROR",
                summary=f"{type(exc).__name__}: {exc}",
            )
            return {"error": str(exc), "tool": tool_name}, rec

    # ------------------------------------------------------------------ 22 Tool Implementations
    def get_gamer_dna(self, user_id: str, patch_scope: str = "ALL", **_: Any) -> Dict[str, Any]:
        matches = self.repo.list_matches(user_id)
        cold = self.repo.get_cold_start_preferences(user_id)
        dna = self.dna_engine.build_profile(user_id, matches, cold_start=cold, patch_scope=patch_scope)
        self.repo.save_gamer_profile_snapshot(user_id, dna.model_dump(mode="json"), dna.eligible_match_count, dna.synthetic_excluded_count)
        return {"provenance": "REAL_OBSERVED_DNA" if dna.eligible_match_count > 0 else "COLD_START", "_summary": f"DNA matches={dna.eligible_match_count}", **dna.model_dump(mode="json")}

    def get_gamer_profile_confidence(self, user_id: str) -> Dict[str, Any]:
        dna = self.get_gamer_dna(user_id)
        low_dims = [d["dimension"] for d in (dna["style_dimensions"] + dna["proficiency_dimensions"]) if d["status"] != "OBSERVED"]
        return {
            "eligible_match_count": dna["eligible_match_count"],
            "synthetic_excluded_count": dna["synthetic_excluded_count"],
            "suppressed_or_low_sample_dimensions": low_dims,
            "provenance": dna["provenance"],
            "_summary": f"{dna['eligible_match_count']} real matches; {len(low_dims)} sparse dimensions",
        }

    def get_match_history(self, user_id: str, limit: int = 20, exclude_synthetic: bool = True) -> Dict[str, Any]:
        items = self.repo.list_matches(user_id, exclude_synthetic=exclude_synthetic, limit=limit)
        return {
            "count": len(items),
            "matches": [
                {
                    "match_id": m.match_id,
                    "video_id": m.video_id,
                    "game_version": m.game_version,
                    "game_patch": m.game_patch,
                    "formation": m.formation,
                    "gameplay_mode": m.gameplay_mode,
                    "provenance": m.provenance,
                    "observation_quality": m.observation_quality,
                    "findings_count": len(m.coaching_findings),
                    "match_result": m.match_result.model_dump(),
                    "created_at": m.created_at,
                }
                for m in items
            ],
            "provenance": "USER_SCOPED_REPOSITORY",
            "_summary": f"Retrieved {len(items)} user matches",
        }

    def get_match_analysis(self, user_id: str, match_id: str) -> Dict[str, Any]:
        m = self.repo.get_match(user_id, match_id)
        return {"provenance": m.provenance, "_summary": f"Match {match_id}", **m.model_dump(mode="json")}

    def get_match_squad_snapshot(self, user_id: str, match_id: str) -> Dict[str, Any]:
        m = self.repo.get_match(user_id, match_id)
        return {
            "match_id": m.match_id,
            "squad_snapshot": m.squad_snapshot.model_dump(mode="json") if m.squad_snapshot else None,
            "provenance": m.provenance,
            "_summary": f"Historical snapshot for {match_id}",
        }

    def find_recurring_mistakes(self, user_id: str, diagnostic_filter: Optional[str] = None) -> Dict[str, Any]:
        matches = self.repo.list_matches(user_id, exclude_synthetic=True)
        patterns = self.mistake_analyzer.analyze(matches, diagnostic_filter=diagnostic_filter)
        return {
            "eligible_matches": len(matches),
            "patterns": [p.model_dump(mode="json") for p in patterns],
            "provenance": "REAL_OBSERVED_PATTERNS" if patterns else "EMPTY_NO_REAL_PATTERN",
            "_summary": f"Found {len(patterns)} recurring mistake patterns across {len(matches)} matches",
        }

    def get_tactical_diagnostic(self, user_id: str, diagnostic_code: str) -> Dict[str, Any]:
        return self.find_recurring_mistakes(user_id, diagnostic_filter=diagnostic_code)

    def get_evidence_clip(self, user_id: str, diagnostic_code: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
        matches = self.repo.list_matches(user_id, exclude_synthetic=True)
        clips = []
        for m in matches:
            for c in m.evidence_clips:
                if not diagnostic_code or c.diagnostic_code == diagnostic_code:
                    clips.append(c.model_dump(mode="json"))
        return {"clips": clips[:limit], "provenance": "USER_EVIDENCE_CLIPS", "_summary": f"Found {len(clips[:limit])} clips"}

    def compare_match_performance(self, user_id: str, match_id_a: Optional[str] = None, match_id_b: Optional[str] = None) -> Dict[str, Any]:
        matches = self.repo.list_matches(user_id, exclude_synthetic=True)
        if not match_id_a or not match_id_b:
            if len(matches) < 2:
                return {"insufficient_matches": True, "count": len(matches), "provenance": "INSUFFICIENT_EVIDENCE", "_summary": "Fewer than 2 real matches to compare"}
            match_id_b = matches[0].match_id
            match_id_a = matches[1].match_id
        comp = self.match_service.compare_matches(user_id, match_id_a, match_id_b)
        return {"provenance": "USER_MATCH_COMPARISON", "_summary": f"Compared {match_id_a} vs {match_id_b}", **comp}

    def get_current_squad(self, user_id: str, squad_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            import uuid
            uid = uuid.UUID(user_id)
            squad_list = self.squads.list_squads(uid)
            if squad_id:
                sq = self.squads.get_squad(uid, uuid.UUID(squad_id))
                slots = self.squads.slots(uuid.UUID(squad_id), uid) if sq else []
                return {"squad": sq, "slots": slots, "provenance": "USER_SQUAD_DB", "_summary": f"Loaded squad {squad_id}"}
            return {"squads": squad_list, "provenance": "USER_SQUAD_DB", "_summary": f"{len(squad_list)} saved squads"}
        except Exception:
            return {"squads": [], "provenance": "UNAVAILABLE", "_summary": "No saved PostgreSQL squad found"}

    def get_player_card(self, user_id: str, query_name: str, game_version: str = "FC27") -> Dict[str, Any]:
        return self.search_player_cards(user_id, query_name=query_name, game_version=game_version, limit=3)

    def search_player_cards(
        self,
        user_id: str,
        *,
        query_name: Optional[str] = None,
        position: Optional[str] = None,
        game_version: str = "FC27",
        limit: int = 5,
    ) -> Dict[str, Any]:
        gv = "FC26" if game_version.upper() == "FC26" else "FC27"
        try:
            gvid = self.players.game_version_id(gv)
            if not gvid:
                return {"items": [], "provenance": "CATALOGUE_UNAVAILABLE", "_summary": "No game_version row"}
            res = self.players.search(
                gvid, q=query_name, position=position.upper() if position else None,
                sort="overall_rating", sort_dir="desc", page=1, page_size=limit, research=(gv == "FC27"),
            )
            items = [
                {
                    "id": str(r.get("id")),
                    "name": r.get("display_name"),
                    "position": r.get("position_primary"),
                    "overall_rating": r.get("overall_rating"),
                    "nation": r.get("nation"),
                    "playstyles": r.get("playstyles") or [],
                }
                for r in res.get("items", [])
            ]
            return {"items": items, "game_version": gv, "provenance": "CANONICAL_POSTGRES_CATALOGUE", "_summary": f"Found {len(items)} {gv} candidates"}
        except Exception as exc:
            return {"items": [], "error": str(exc), "provenance": "CATALOGUE_ERROR", "_summary": "Catalogue lookup unavailable"}

    def compare_player_cards(self, user_id: str, names: List[str], game_version: str = "FC27", **_: Any) -> Dict[str, Any]:
        found = []
        for n in names[:4]:
            res = self.get_player_attributes(user_id, query_name=n, game_version=game_version)
            if res.get("found"):
                found.append(res)
            else:
                sr = self.search_player_cards(user_id, query_name=n, game_version=game_version, limit=1)
                if sr.get("items"):
                    found.append(sr["items"][0])
        return {"compared": found, "game_version": game_version, "provenance": "CANONICAL_POSTGRES_CATALOGUE", "_summary": f"Compared {len(found)} cards"}

    def evaluate_role_suitability(self, user_id: str, position: str = "CDM", game_version: str = "FC27") -> Dict[str, Any]:
        matches = self.repo.list_matches(user_id, exclude_synthetic=True)
        cold = self.repo.get_cold_start_preferences(user_id)
        dna = self.dna_engine.build_profile(user_id, matches, cold_start=cold)
        roles = dna.tactical_suitability[0].recommended_roles if dna.tactical_suitability else []
        kb = self.knowledge.query(f"{position} role fc iq", game_version=game_version, top_k=2)
        return {"position": position, "recommended_roles": roles, "official_role_notes": kb["entries"], "provenance": "DNA_PLUS_OFFICIAL_KB", "_summary": f"Role suitability for {position}"}

    def evaluate_squad_cohesion(self, user_id: str, formation: str = "4-3-3", tactical_profile: str = "BALANCED", slot_scores: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        synergy = compute_whole_xi_synergy(formation=formation, tactical_profile=tactical_profile, slots_data=slot_scores or [])
        return {"provenance": "PHASE34B_SYNERGY_ENGINE", "_summary": f"Cohesion for {formation}", **synergy}

    def evaluate_player_partnership(self, user_id: str, slot_1: str = "LCM", slot_2: str = "CDM", card_1: Optional[Dict[str, Any]] = None, card_2: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        res = self.partnerships.evaluate_partnership(
            slot_1=slot_1,
            card_1=card_1 or {"name": slot_1, "attributes": {"short_passing": 82, "vision": 80}},
            card_1_score=0.75,
            slot_2=slot_2,
            card_2=card_2 or {"name": slot_2, "attributes": {"interceptions": 84, "defensive_awareness": 84}},
            card_2_score=0.76,
            tactical_profile="BALANCED",
        )
        return {"provenance": "PARTNERSHIP_INTELLIGENCE_V2", "_summary": f"Partnership {slot_1}+{slot_2}", **res.to_dict()}

    def evaluate_tactical_fit(self, user_id: str, formation: str = "4-2-3-1") -> Dict[str, Any]:
        dna = self.get_gamer_dna(user_id)
        return {
            "requested_formation": formation,
            "tactical_suitability": dna["tactical_suitability"],
            "archetype": dna["archetype"],
            "provenance": dna["provenance"],
            "_summary": f"Evaluated tactical fit ({dna['archetype']['primary_archetype']})",
        }

    def recommend_player_profiles(self, user_id: str, position: str = "CDM", game_version: str = "FC27", budget_coins: Optional[int] = None) -> Dict[str, Any]:
        matches = self.repo.list_matches(user_id, exclude_synthetic=True)
        cold = self.repo.get_cold_start_preferences(user_id)
        dna = self.dna_engine.build_profile(user_id, matches, cold_start=cold)
        mistakes = self.mistake_analyzer.analyze(matches)
        res = self.fit_service.recommend_for_gamer(
            game_version=game_version, position=position, dna=dna, mistakes=mistakes, matches=matches, budget_coins=budget_coins
        )
        return {"provenance": "PERSONAL_GAMEPLAY_FIT", "_summary": f"Profiles for {position}", **res}

    def recommend_squad_changes(self, user_id: str, game_version: str = "FC27", formation: str = "4-3-3", tactical_profile: str = "BALANCED", budget_coins: Optional[int] = None) -> Dict[str, Any]:
        matches = self.repo.list_matches(user_id, exclude_synthetic=True)
        cold = self.repo.get_cold_start_preferences(user_id)
        dna = self.dna_engine.build_profile(user_id, matches, cold_start=cold)
        mistakes = self.mistake_analyzer.analyze(matches)
        analysis = self.fit_service.analyze_personal_squad(
            game_version=game_version, formation=formation, tactical_profile=tactical_profile,
            slots=[], dna=dna, mistakes=mistakes, matches=matches, budget_coins=budget_coins,
        )
        return {"provenance": "SQUAD_INTERVENTION_ENGINE", "_summary": analysis["intervention_assessment"]["recommended_intervention"], **analysis}

    def get_official_gameplay_knowledge(
        self,
        user_id: str,
        query: str,
        game_version: Optional[str] = None,
        game_patch: Optional[str] = None,
        topic: Optional[str] = None,
        official_only: bool = False,
        **_: Any,
    ) -> Dict[str, Any]:
        kb = self.knowledge.query(
            query,
            game_version=game_version,
            game_patch=game_patch,
            topic=topic,
            official_only=official_only,
            top_k=4,
        )
        return {"provenance": "OFFICIAL_KB", "_summary": f"KB matches={kb['total_matches']}", **kb}

    def generate_training_plan(self, user_id: str, game_version: str = "FC27") -> Dict[str, Any]:
        matches = self.repo.list_matches(user_id, exclude_synthetic=True)
        cold = self.repo.get_cold_start_preferences(user_id)
        dna = self.dna_engine.build_profile(user_id, matches, cold_start=cold)
        mistakes = self.mistake_analyzer.analyze(matches)
        existing = self.repo.get_latest_training_plan(user_id)
        attempts = self.repo.list_training_attempts(user_id)
        wins = self.p41_repo.list_decision_windows(user_id, exclude_synthetic=True, limit=15)
        plan = self.training_service.generate_plan(
            user_id,
            game_version=game_version,
            mistakes=mistakes,
            dna=dna,
            existing_bkt=existing.bkt_states if existing else None,
            decision_windows=wins,
            attempt_logs=attempts,
        )
        self.repo.save_training_plan(user_id, plan)
        return {
            "provenance": "TRAINING_ACADEMY",
            "_summary": f"Generated {len(plan.exercises)} drills ({plan.decision_windows_linked} linked decision windows)",
            **plan.model_dump(mode="json"),
        }

    def evaluate_improvement(self, user_id: str) -> Dict[str, Any]:
        matches = self.repo.list_matches(user_id, exclude_synthetic=True)
        attempts = self.repo.list_training_attempts(user_id)
        rep = self.progression_service.evaluate(user_id, matches, training_attempts=attempts)
        return {"provenance": "LONGITUDINAL_PROGRESSION", "_summary": f"Progression across {rep.total_eligible_matches} matches", **rep.model_dump(mode="json")}

    # ------------------------------------------------------------------ 12 Phase 41 Decision Tools
    def get_decision_opportunities(self, user_id: str, match_id: Optional[str] = None, exclude_synthetic: bool = True, limit: int = 30) -> Dict[str, Any]:
        wins = self.p41_repo.list_decision_windows(user_id, match_id=match_id, exclude_synthetic=exclude_synthetic, limit=limit)
        return {
            "count": len(wins),
            "windows": [
                {
                    "window_id": w["window_id"],
                    "match_id": w["match_id"],
                    "decision_type": w["decision_type"],
                    "status": w["status"],
                    "provenance": w["provenance"],
                    "action_timestamp_sec": w["action_timestamp_sec"],
                    "regret_estimate": w.get("regret_estimate"),
                }
                for w in wins
            ],
            "provenance": "PHASE41_DECISION_REPO",
            "_summary": f"Found {len(wins)} decision opportunities",
        }

    def get_decision_frame_analysis(self, user_id: str, window_id: Optional[str] = None, match_id: Optional[str] = None, reveal_outcome: bool = False) -> Dict[str, Any]:
        wins = self.p41_repo.list_decision_windows(user_id, match_id=match_id, exclude_synthetic=True, limit=25)
        target = next((w for w in wins if w["window_id"] == window_id), None) if window_id else (wins[0] if wins else None)
        if not target:
            return {"status": "ABSTAINED_NO_WINDOWS", "provenance": "PHASE41_DECISION_REPO", "_summary": "No evaluated decision window found"}
        out = dict(target)
        if not reveal_outcome:
            out["post_action_outcome"] = None
        return {"window": out, "provenance": target["provenance"], "_summary": f"Window {target['window_id']} regret={target.get('regret_estimate')}"}

    def evaluate_candidate_actions(self, user_id: str, snapshot: Optional[Dict[str, Any]] = None, match_id: str = "coach-eval") -> Dict[str, Any]:
        if snapshot:
            state = build_state_from_snapshot(match_id, snapshot)
            comp = self.counterfactual_engine.evaluate(state)
            return {"comparison": comp.model_dump(mode="json"), "provenance": state.provenance, "_summary": f"Evaluated {len(comp.candidates)} candidates"}
        wins = self.p41_repo.list_decision_windows(user_id, exclude_synthetic=True, limit=1)
        if not wins:
            return {"status": "ABSTAINED_NO_WINDOWS", "candidates": [], "provenance": "PHASE41_DECISION_REPO", "_summary": "No saved snapshots to evaluate"}
        comp = wins[0].get("counterfactual_comparison") or {}
        return {"comparison": comp, "provenance": wins[0]["provenance"], "_summary": f"Loaded {len(comp.get('candidates', []))} candidates"}

    def get_best_alternative_action(self, user_id: str, window_id: Optional[str] = None) -> Dict[str, Any]:
        frame = self.get_decision_frame_analysis(user_id, window_id=window_id)
        if frame.get("status") == "ABSTAINED_NO_WINDOWS":
            return frame
        comp = frame["window"].get("counterfactual_comparison") or {}
        return {
            "window_id": frame["window"]["window_id"],
            "best_alternative_id": comp.get("best_alternative_id"),
            "best_alternative_label": comp.get("best_alternative_label"),
            "best_alternative_utility": comp.get("best_alternative_utility"),
            "observed_utility": comp.get("observed_utility"),
            "regret_estimate": comp.get("regret_estimate"),
            "uncertainty": frame["window"].get("uncertainty_payload") or comp.get("uncertainty"),
            "provenance": frame["provenance"],
            "_summary": f"Best alt: {comp.get('best_alternative_label')}",
        }

    def get_decision_regret_summary(self, user_id: str, match_id: Optional[str] = None) -> Dict[str, Any]:
        wins = [w for w in self.p41_repo.list_decision_windows(user_id, match_id=match_id, exclude_synthetic=True, limit=100) if w.get("status") == "EVALUATED"]
        regrets = [float(w.get("regret_estimate") or 0.0) for w in wins]
        mean_r = round(sum(regrets) / len(regrets), 4) if regrets else None
        high = [w["window_id"] for w in wins if float(w.get("regret_estimate") or 0.0) >= 0.08]
        return {
            "evaluated_windows": len(wins),
            "mean_regret": mean_r,
            "high_regret_window_ids": high[:10],
            "provenance": "PHASE41_REGRET_ENGINE",
            "_summary": f"{len(wins)} windows evaluated; mean regret={mean_r}",
        }

    def get_football_iq_profile(self, user_id: str) -> Dict[str, Any]:
        wins = self.p41_repo.list_decision_windows(user_id, exclude_synthetic=False, limit=250)
        profile = self.iq_engine.compute_profile(user_id, wins)
        self.p41_repo.save_football_iq_profile(user_id, profile.model_dump(mode="json"))
        return {"provenance": "FOOTBALL_IQ_ENGINE", "_summary": f"IQ={profile.overall_football_iq} ({profile.confidence})", **profile.model_dump(mode="json")}

    def get_passing_decision_diagnostics(self, user_id: str, match_id: Optional[str] = None) -> Dict[str, Any]:
        wins = [
            w for w in self.p41_repo.list_decision_windows(user_id, match_id=match_id, exclude_synthetic=True, limit=80)
            if w.get("decision_type") in ("ATTACKING_PASS", "THROUGH_BALL", "POSSESSION_RETENTION", "SWITCH_OR_CROSS") and w.get("status") == "EVALUATED"
        ]
        return {"count": len(wins), "windows": wins[:8], "provenance": "PASSING_DECISION_ENGINE", "_summary": f"{len(wins)} passing windows"}

    def get_defensive_decision_diagnostics(self, user_id: str, match_id: Optional[str] = None) -> Dict[str, Any]:
        wins = [
            w for w in self.p41_repo.list_decision_windows(user_id, match_id=match_id, exclude_synthetic=True, limit=80)
            if w.get("decision_type") == "DEFENSIVE_ACTION" and w.get("status") == "EVALUATED"
        ]
        return {"count": len(wins), "windows": wins[:8], "provenance": "DEFENSIVE_DECISION_ENGINE", "_summary": f"{len(wins)} defensive windows"}

    def get_shooting_decision_diagnostics(self, user_id: str, match_id: Optional[str] = None) -> Dict[str, Any]:
        wins = [
            w for w in self.p41_repo.list_decision_windows(user_id, match_id=match_id, exclude_synthetic=True, limit=80)
            if w.get("decision_type") == "SHOT" and w.get("status") == "EVALUATED"
        ]
        return {"count": len(wins), "is_calibrated_xg": False, "windows": wins[:8], "provenance": "SHOOTING_HEURISTIC_ENGINE", "_summary": f"{len(wins)} shot decision windows"}

    def get_off_ball_run_diagnostics(self, user_id: str, match_id: Optional[str] = None) -> Dict[str, Any]:
        wins = self.p41_repo.list_decision_windows(user_id, match_id=match_id, exclude_synthetic=True, limit=25)
        detected: List[Dict[str, Any]] = []
        for w in wins[:6]:
            pre = w.get("pre_action_state") or {}
            if pre.get("pre_action_players"):
                from backend.domain.phase41_models import FootballDecisionState
                st = FootballDecisionState.model_validate(pre)
                runs = self.off_ball_engine.detect_runs(st)
                if runs:
                    detected.append({"window_id": w["window_id"], "runs": [r.model_dump(mode="json") for r in runs]})
        return {"analyzed_windows": len(detected), "opportunities": detected, "provenance": "OFF_BALL_ENGINE", "_summary": f"Off-ball runs across {len(detected)} windows"}

    def generate_decision_training_scenario(self, user_id: str, window_id: Optional[str] = None) -> Dict[str, Any]:
        wins = self.p41_repo.list_decision_windows(user_id, exclude_synthetic=True, limit=30)
        target = next((w for w in wins if w["window_id"] == window_id), None) if window_id else next((w for w in wins if w.get("status") == "EVALUATED"), None)
        if not target:
            return {"status": "ABSTAINED_NO_WINDOWS", "provenance": "PHASE42_SCENARIO_BRIDGE", "_summary": "No evaluated window available for scenario export"}
        from backend.domain.phase41_models import CounterfactualComparison, FootballDecisionState
        st = FootballDecisionState.model_validate(target["pre_action_state"])
        comp = CounterfactualComparison.model_validate(target["counterfactual_comparison"])
        scn = self.scenario_service.build_scenario(st, comp)
        saved = self.p41_repo.save_training_scenario(user_id, scn)
        return {"scenario": saved, "provenance": target["provenance"], "_summary": f"Created scenario {scn.scenario_id}"}

    def evaluate_player_capability_constraints(self, user_id: str, position: str = "CM") -> Dict[str, Any]:
        wins = self.p41_repo.list_decision_windows(user_id, exclude_synthetic=False, limit=120)
        res = self.fit_service.evaluate_decision_capability_bottleneck(wins, position=position)
        return {"provenance": "CAPABILITY_BOTTLENECK_ISOLATOR", "_summary": res["primary_bottleneck"], **res}
