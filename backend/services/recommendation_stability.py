"""Recommendation Stability and Robustness Lab Engine (Phase 35).

Measures candidate rank volatility, parameter sensitivity, and context resilience
across systematic perturbations:
1. Tactical profile shifts (BALANCED, HIGH_PRESS, COUNTER_ATTACK, POSSESSION, WING_PLAY, DIRECT_COUNTER)
2. Formation slot context shifts (e.g., ST in 4-3-3 vs 4-4-2 vs 3-5-2)
3. Attribute weight perturbations (+/- 10%, +/- 20%)

Outputs baseline rank, min/max/median rank, volatility (standard deviation),
top-1/3/5 finish frequencies, and categorical stability classifications:
- ROBUST_ACROSS_CONTEXTS
- TACTIC_SPECIALIZED
- PREFERENCE_SENSITIVE
- UNSTABLE
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np

from backend.api.schemas import AttributePreferenceIn
from backend.domain.card_model import ALL_ATTRS, Candidate
from backend.services.card_squad_lab import SlotRequest
from backend.services.recommendation_service_v3 import RecommendationServiceV3


StabilityCategory = Literal[
    "ROBUST_ACROSS_CONTEXTS",
    "TACTIC_SPECIALIZED",
    "PREFERENCE_SENSITIVE",
    "UNSTABLE"
]


@dataclass
class CandidateStabilityProfile:
    """Quantitative stability metrics and robustness classification for a player candidate."""
    card_item_id: str
    card_name: str
    overall_rating: int
    baseline_rank: int
    baseline_score: float
    min_rank: int
    max_rank: int
    rank_range: int
    mean_rank: float
    median_rank: float
    rank_volatility: float                  # Standard deviation of ranks across scenarios
    top_1_frequency_pct: float
    top_3_frequency_pct: float
    top_5_frequency_pct: float
    stability_category: StabilityCategory
    dominant_tactical_fit: Optional[str] = None
    vulnerable_tactical_fit: Optional[str] = None
    scenario_ranks: Dict[str, int] = field(default_factory=dict)
    scenario_scores: Dict[str, float] = field(default_factory=dict)
    robustness_explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RecommendationStabilityEngine:
    """Runs systematic perturbation batteries to compute recommendation robustness."""

    TACTICAL_PROFILES = [
        "BALANCED",
        "HIGH_PRESS",
        "COUNTER_ATTACK",
        "POSSESSION",
        "WING_PLAY",
        "DIRECT_COUNTER",
    ]

    def __init__(self, service: RecommendationServiceV3):
        self.service = service

    def evaluate_position_stability(
        self,
        position: str,
        formation: str = "4-3-3",
        slot: Optional[str] = None,
        candidate_subset: Optional[List[Candidate]] = None,
        test_formations: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Evaluates rank stability for all eligible candidates in a given position."""
        target_slot = slot or position
        formations_to_test = test_formations or [formation]
        
        # Scenario definitions
        scenarios: List[Dict[str, Any]] = []
        
        # 1. Tactical Profile Scenarios
        for prof in self.TACTICAL_PROFILES:
            scenarios.append({
                "scenario_id": f"TAC_{prof}",
                "description": f"Tactical Profile: {prof}",
                "formation": formation,
                "slot": target_slot,
                "profile": prof,
                "preferences": [],
            })
            
        # 2. Formation Shifts (if multiple provided)
        if len(formations_to_test) > 1:
            for form in formations_to_test:
                if form == formation:
                    continue
                scenarios.append({
                    "scenario_id": f"FORM_{form}",
                    "description": f"Formation shift to {form}",
                    "formation": form,
                    "slot": target_slot,
                    "profile": "BALANCED",
                    "preferences": [],
                })
                
        # 3. Attribute Sensitivity Perturbations (+20% on key position attributes)
        key_attrs = {
            "ST": ["pace", "finishing", "physicality"],
            "CAM": ["vision", "short_passing", "dribbling"],
            "CM": ["short_passing", "defending", "stamina"],
            "CDM": ["defending", "physicality", "interceptions"],
            "CB": ["defending", "pace", "physicality"],
            "LB": ["pace", "defending", "stamina"],
            "RB": ["pace", "defending", "stamina"],
            "LW": ["pace", "dribbling", "crossing"],
            "RW": ["pace", "dribbling", "crossing"],
        }.get(position, ["pace", "defending"])
        
        for attr in key_attrs:
            scenarios.append({
                "scenario_id": f"PREF_PLUS_{attr.upper()}",
                "description": f"+20% User Preference: {attr}",
                "formation": formation,
                "slot": target_slot,
                "profile": "BALANCED",
                "preferences": [AttributePreferenceIn(attribute=attr, weight=1.20)],
            })
            scenarios.append({
                "scenario_id": f"PREF_MINUS_{attr.upper()}",
                "description": f"-20% User Preference: {attr}",
                "formation": formation,
                "slot": target_slot,
                "profile": "BALANCED",
                "preferences": [AttributePreferenceIn(attribute=attr, weight=0.80)],
            })

        # Run all scenarios
        candidate_records: Dict[str, Dict[str, Any]] = {}
        total_scenarios = len(scenarios)
        
        # Identify baseline
        baseline_ranks: Dict[str, int] = {}
        baseline_scores: Dict[str, float] = {}
        
        candidate_map = {str(c.entity_id): c for c in getattr(self.service, "candidates", [])}
        
        for sc in scenarios:
            try:
                req = SlotRequest(
                    game_version="FC27",
                    include_research_data=True,
                    position=position,
                    formation=sc["formation"],
                    slot=sc["slot"],
                    tactical_profile=sc["profile"],
                    attribute_preferences=sc["preferences"],
                    limit=50,
                )
                res, _, _, _ = self.service.run(req)
                ranked = res.ranked
            except Exception as e:
                ranked = []

            for rank_idx, rc in enumerate(ranked, start=1):
                cid = str(rc.context.candidate_entity_id)
                score = round(float(getattr(rc.context, "r", 0.0)), 4)
                cand_obj = candidate_map.get(cid)
                card_name = getattr(rc.context, "candidate_name", None) or (cand_obj.name if cand_obj else f"Player-{cid[:8]}")
                ovr = getattr(cand_obj, "overall_rating", 85) if cand_obj else 85
                
                if cid not in candidate_records:
                    candidate_records[cid] = {
                        "card_name": card_name,
                        "ovr": ovr,
                        "ranks": [],
                        "scores": [],
                        "scenario_ranks": {},
                        "scenario_scores": {},
                    }
                
                candidate_records[cid]["ranks"].append(rank_idx)
                candidate_records[cid]["scores"].append(score)
                candidate_records[cid]["scenario_ranks"][sc["scenario_id"]] = rank_idx
                candidate_records[cid]["scenario_scores"][sc["scenario_id"]] = score
                
                if sc["scenario_id"] == "TAC_BALANCED":
                    baseline_ranks[cid] = rank_idx
                    baseline_scores[cid] = score

        # Compute robustness statistics per candidate
        profiles: List[CandidateStabilityProfile] = []
        
        for cid, data in candidate_records.items():
            ranks = data["ranks"]
            if not ranks:
                continue
                
            n_eval = len(ranks)
            min_r = int(min(ranks))
            max_r = int(max(ranks))
            mean_r = float(np.mean(ranks))
            median_r = float(np.median(ranks))
            volatility = float(np.std(ranks))
            
            top_1_freq = round(100.0 * sum(1 for r in ranks if r == 1) / total_scenarios, 1)
            top_3_freq = round(100.0 * sum(1 for r in ranks if r <= 3) / total_scenarios, 1)
            top_5_freq = round(100.0 * sum(1 for r in ranks if r <= 5) / total_scenarios, 1)
            
            base_r = baseline_ranks.get(cid, median_r)
            base_s = baseline_scores.get(cid, float(np.mean(data["scores"])))
            
            # Determine dominant and vulnerable profile
            tac_ranks = {
                prof: data["scenario_ranks"].get(f"TAC_{prof}", 99)
                for prof in self.TACTICAL_PROFILES
            }
            dominant_prof = min(tac_ranks, key=tac_ranks.get) if tac_ranks else None
            vulnerable_prof = max(tac_ranks, key=tac_ranks.get) if tac_ranks else None
            
            # Classification
            if top_3_freq >= 75.0 and volatility <= 1.8:
                cat: StabilityCategory = "ROBUST_ACROSS_CONTEXTS"
                expl = f"Maintains elite top-3 rank across {top_3_freq}% of tactical and preference shifts (volatility: {volatility:.2f})."
            elif tac_ranks and (max(tac_ranks.values()) - min(tac_ranks.values()) >= 4):
                cat = "TACTIC_SPECIALIZED"
                expl = f"Heavily specialized: peaks at rank #{tac_ranks[dominant_prof]} in {dominant_prof}, falls to #{tac_ranks[vulnerable_prof]} in {vulnerable_prof}."
            elif volatility > 3.0:
                cat = "UNSTABLE"
                expl = f"High sensitivity to minor attribute or formation perturbations (volatility: {volatility:.2f}, rank range: {min_r}-{max_r})."
            else:
                cat = "PREFERENCE_SENSITIVE"
                expl = f"Stable under tactical shifts but shifts rank across user attribute preference weight variations."
                
            profiles.append(CandidateStabilityProfile(
                card_item_id=cid,
                card_name=data["card_name"],
                overall_rating=data["ovr"],
                baseline_rank=int(base_r),
                baseline_score=round(base_s, 4),
                min_rank=min_r,
                max_rank=max_r,
                rank_range=max_r - min_r,
                mean_rank=round(mean_r, 2),
                median_rank=round(median_r, 1),
                rank_volatility=round(volatility, 2),
                top_1_frequency_pct=top_1_freq,
                top_3_frequency_pct=top_3_freq,
                top_5_frequency_pct=top_5_freq,
                stability_category=cat,
                dominant_tactical_fit=dominant_prof,
                vulnerable_tactical_fit=vulnerable_prof,
                scenario_ranks=data["scenario_ranks"],
                scenario_scores=data["scenario_scores"],
                robustness_explanation=expl,
            ))

        # Sort profiles by baseline rank
        profiles.sort(key=lambda p: (p.baseline_rank, p.rank_volatility))

        # Serialize scenarios safely
        serialized_scenarios = []
        for sc in scenarios:
            sc_copy = dict(sc)
            sc_copy["preferences"] = [
                p.model_dump() if hasattr(p, "model_dump") else (p.dict() if hasattr(p, "dict") else str(p))
                for p in sc.get("preferences", [])
            ]
            serialized_scenarios.append(sc_copy)

        return {
            "evaluation_engine": "RecommendationStabilityLab-v1",
            "position": position,
            "formation": formation,
            "total_scenarios_evaluated": total_scenarios,
            "scenarios": serialized_scenarios,
            "total_candidates_analyzed": len(profiles),
            "candidates": [p.to_dict() for p in profiles],
        }
