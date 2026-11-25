"""Partnership Intelligence V2 Engine for EA FC Intelligence (Phase 35).

Evaluates 5 core tactical partnerships without arbitrary chemistry numbers:
1. ST_CAM: Striker + Central Attacking Midfielder (Vertical Spacing & Creator-Finisher Synergy)
2. WINGER_FULLBACK: Flank Units (Channel Width, Overlap Mechanics & Defensive Cover)
3. CM_CDM: Central Midfield Pivot (Defensive Screening vs Ball Progression Balance)
4. TWO_STRIKERS: Striker Pairings (Aerial / Hold-up vs Behind-the-Defense Complementarity)
5. CB_CB: Central Defensive Unit (Aggressive Stopper vs Recovery Sweeper Balance)

Provides mathematically reconstructable Capability Complementarity,
Responsibility Overlap, Role Dependencies, and Friction Deductions.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple


PartnershipType = Literal["ST_CAM", "WINGER_FULLBACK", "CM_CDM", "TWO_STRIKERS", "CB_CB"]
PartnershipStatus = Literal["ELITE_PARTNERSHIP", "COMPLEMENTARY_PARTNERSHIP", "FUNCTIONAL_PARTNERSHIP", "ASYMMETRIC_OR_FRICTIONAL"]


def _get_attr(card: Any, attr_name: str, default: float = 70.0) -> float:
    """Helper to extract attribute value from dict or object."""
    attrs = getattr(card, "attributes", None)
    if attrs is None and isinstance(card, dict):
        attrs = card.get("attributes", {})
    if attrs is None:
        return default
        
    if hasattr(attrs, "get"):
        val = attrs.get(attr_name)
    elif hasattr(attrs, "values") and isinstance(attrs.values, dict):
        val = attrs.values.get(attr_name)
    elif isinstance(attrs, dict):
        val = attrs.get(attr_name)
    else:
        val = getattr(attrs, attr_name, None)
        
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _get_name(card: Any, fallback: str = "Player") -> str:
    """Helper to extract player name."""
    if hasattr(card, "card_name") and card.card_name:
        return str(card.card_name)
    if hasattr(card, "name") and card.name:
        return str(card.name)
    if isinstance(card, dict):
        return card.get("name") or card.get("card_name") or fallback
    return fallback


def _harmonic_mean(a: float, b: float) -> float:
    """Harmonic mean bounded in [0, 1]."""
    a = max(0.01, min(1.0, a))
    b = max(0.01, min(1.0, b))
    return (2.0 * a * b) / (a + b)


@dataclass
class PartnershipEvaluation:
    """Deterministic evaluation result for a pair of player cards."""
    partnership_type: PartnershipType
    slot_1: str
    card_1_name: str
    card_1_score: float
    slot_2: str
    card_2_name: str
    card_2_score: float
    mean_suitability: float
    capability_complementarity: float
    responsibility_overlap: float
    friction_penalties: List[Dict[str, Any]]
    total_friction: float
    synergy_score: float
    status: PartnershipStatus
    tactical_profile: str
    evidence_classification: str = "MODELED_HEURISTIC"
    explanation: str = ""
    tactical_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PartnershipIntelligenceEngine:
    """Evaluates multi-player partnerships based on tactical complementarity and spatial dynamics."""

    @staticmethod
    def evaluate_st_cam(
        card_st: Any,
        score_st: float,
        card_cam: Any,
        score_cam: float,
        tactical_profile: str = "BALANCED",
        slot_st: str = "ST",
        slot_cam: str = "CAM",
    ) -> PartnershipEvaluation:
        """Evaluates ST + CAM vertical spacing and creator-finisher dynamics."""
        st_name = _get_name(card_st, "Striker")
        cam_name = _get_name(card_cam, "Playmaker")
        
        # Attributes
        st_fin = _get_attr(card_st, "finishing", 80.0) / 100.0
        st_pace = _get_attr(card_st, "pace", 80.0) / 100.0
        cam_vis = _get_attr(card_cam, "vision", 82.0) / 100.0
        cam_pass = _get_attr(card_cam, "short_passing", 82.0) / 100.0
        st_pos = _get_attr(card_st, "positioning", 80.0) / 100.0
        cam_drib = _get_attr(card_cam, "dribbling", 80.0) / 100.0
        
        # Creator-Finisher synergy: CAM creation (pass + vis) paired with ST finishing (fin + pos)
        creation_capacity = (cam_vis * 0.55 + cam_pass * 0.45)
        finishing_capacity = (st_fin * 0.60 + st_pos * 0.40)
        complementarity = _harmonic_mean(creation_capacity, finishing_capacity)
        
        # Overlap penalty: both operating exclusively as deep false 9s or both standing on last shoulder
        # If CAM has high finishing but low passing, and ST also is a pure poacher
        overlap = 0.0
        if st_pos > 0.85 and cam_vis < 0.70:
            overlap += 0.15   # Severed supply line
        if abs(st_pace - cam_drib) < 0.05 and st_fin < 0.75 and cam_pass < 0.75:
            overlap += 0.10   # Role confusion
            
        # Friction deductions
        frictions = []
        if tactical_profile == "HIGH_PRESS":
            st_def = _get_attr(card_st, "defending", 35.0)
            cam_sta = _get_attr(card_cam, "stamina", 70.0)
            if st_def < 40.0:
                frictions.append({
                    "rule": "RULE-PART-ST-PRESS-DEF",
                    "penalty": 0.020,
                    "reason": f"{st_name} defending ({st_def:.0f}) impairs frontline press trap."
                })
            if cam_sta < 75.0:
                frictions.append({
                    "rule": "RULE-PART-CAM-STA",
                    "penalty": 0.015,
                    "reason": f"{cam_name} stamina ({cam_sta:.0f}) risks second-half defensive drop-off."
                })
        elif tactical_profile == "COUNTER_ATTACK":
            if st_pace < 0.82:
                frictions.append({
                    "rule": "RULE-PART-ST-PACE",
                    "penalty": 0.025,
                    "reason": f"{st_name} pace ({st_pace*100:.0f}) limits vertical fast-break separation."
                })
                
        tot_friction = sum(f["penalty"] for f in frictions)
        mean_score = (score_st + score_cam) / 2.0
        synergy = max(0.0, min(1.0, mean_score + 0.15 * (complementarity - 0.50) - 0.10 * overlap - tot_friction))
        
        status: PartnershipStatus = (
            "ELITE_PARTNERSHIP" if synergy >= 0.82 else
            "COMPLEMENTARY_PARTNERSHIP" if synergy >= 0.72 else
            "FUNCTIONAL_PARTNERSHIP" if synergy >= 0.60 else
            "ASYMMETRIC_OR_FRICTIONAL"
        )
        
        notes = [
            f"Creation Capacity: {creation_capacity*100:.1f}%, Finishing Capacity: {finishing_capacity*100:.1f}%.",
            f"Complementarity Index: {complementarity*100:.1f}%. Overlap Friction: {overlap*100:.1f}%.",
        ]
        
        return PartnershipEvaluation(
            partnership_type="ST_CAM",
            slot_1=slot_st,
            card_1_name=st_name,
            card_1_score=score_st,
            slot_2=slot_cam,
            card_2_name=cam_name,
            card_2_score=score_cam,
            mean_suitability=round(mean_score, 4),
            capability_complementarity=round(complementarity, 4),
            responsibility_overlap=round(overlap, 4),
            friction_penalties=frictions,
            total_friction=round(tot_friction, 4),
            synergy_score=round(synergy, 4),
            status=status,
            tactical_profile=tactical_profile,
            evidence_classification="MODELED_HEURISTIC",
            explanation=f"{st_name} & {cam_name} provide balanced vertical creation and finishing channels.",
            tactical_notes=notes,
        )

    @staticmethod
    def evaluate_winger_fullback(
        card_winger: Any,
        score_winger: float,
        card_fullback: Any,
        score_fullback: float,
        flank: str = "LEFT",
        tactical_profile: str = "BALANCED",
        slot_winger: str = "LW",
        slot_fullback: str = "LB",
    ) -> PartnershipEvaluation:
        """Evaluates flank unit channel width, overlap mechanics, and defensive cover."""
        w_name = _get_name(card_winger, "Winger")
        fb_name = _get_name(card_fullback, "Fullback")
        
        w_pace = _get_attr(card_winger, "pace", 85.0) / 100.0
        w_drib = _get_attr(card_winger, "dribbling", 82.0) / 100.0
        w_cross = _get_attr(card_winger, "crossing", 75.0) / 100.0
        fb_def = _get_attr(card_fullback, "defending", 80.0) / 100.0
        fb_pace = _get_attr(card_fullback, "pace", 82.0) / 100.0
        fb_cross = _get_attr(card_fullback, "crossing", 72.0) / 100.0
        fb_sta = _get_attr(card_fullback, "stamina", 80.0) / 100.0
        
        # Flank width vs defensive cover balance
        flank_offensive_threat = (w_pace * 0.50 + w_drib * 0.50)
        flank_defensive_security = (fb_def * 0.60 + fb_sta * 0.40)
        complementarity = _harmonic_mean(flank_offensive_threat, flank_defensive_security)
        
        # Overlap dynamics
        overlap = 0.0
        if w_cross > 0.82 and fb_cross > 0.82 and fb_def < 0.75:
            # Both crossing specialists, flank defensively exposed
            overlap += 0.12
            
        frictions = []
        if fb_pace < 0.78:
            frictions.append({
                "rule": "RULE-PART-FB-PACE",
                "penalty": 0.020,
                "reason": f"{fb_name} pace ({fb_pace*100:.0f}) risks wide counterattack isolation behind {w_name}."
            })
        if tactical_profile == "HIGH_PRESS" and fb_sta < 0.80:
            frictions.append({
                "rule": "RULE-PART-FB-STA",
                "penalty": 0.015,
                "reason": f"{fb_name} stamina ({fb_sta*100:.0f}) degrades flank pressing endurance."
            })
            
        tot_friction = sum(f["penalty"] for f in frictions)
        mean_score = (score_winger + score_fullback) / 2.0
        synergy = max(0.0, min(1.0, mean_score + 0.15 * (complementarity - 0.50) - 0.10 * overlap - tot_friction))
        
        status: PartnershipStatus = (
            "ELITE_PARTNERSHIP" if synergy >= 0.82 else
            "COMPLEMENTARY_PARTNERSHIP" if synergy >= 0.72 else
            "FUNCTIONAL_PARTNERSHIP" if synergy >= 0.60 else
            "ASYMMETRIC_OR_FRICTIONAL"
        )
        
        return PartnershipEvaluation(
            partnership_type="WINGER_FULLBACK",
            slot_1=slot_winger,
            card_1_name=w_name,
            card_1_score=score_winger,
            slot_2=slot_fullback,
            card_2_name=fb_name,
            card_2_score=score_fullback,
            mean_suitability=round(mean_score, 4),
            capability_complementarity=round(complementarity, 4),
            responsibility_overlap=round(overlap, 4),
            friction_penalties=frictions,
            total_friction=round(tot_friction, 4),
            synergy_score=round(synergy, 4),
            status=status,
            tactical_profile=tactical_profile,
            explanation=f"{flank} Flank unit: {w_name} attack threat matched with {fb_name} defensive transition cover.",
            tactical_notes=[
                f"Offensive Threat: {flank_offensive_threat*100:.1f}%, Defensive Security: {flank_defensive_security*100:.1f}%.",
                f"Flank Complementarity: {complementarity*100:.1f}%.",
            ],
        )

    @staticmethod
    def evaluate_cm_cdm(
        card_cm: Any,
        score_cm: float,
        card_cdm: Any,
        score_cdm: float,
        tactical_profile: str = "BALANCED",
        slot_cm: str = "CM",
        slot_cdm: str = "CDM",
    ) -> PartnershipEvaluation:
        """Evaluates Central Midfield screening vs progression balance."""
        cm_name = _get_name(card_cm, "Midfielder")
        cdm_name = _get_name(card_cdm, "Anchor")
        
        cdm_def = _get_attr(card_cdm, "defending", 82.0) / 100.0
        cdm_phy = _get_attr(card_cdm, "physicality", 82.0) / 100.0
        cm_pass = _get_attr(card_cm, "short_passing", 82.0) / 100.0
        cm_vis = _get_attr(card_cm, "vision", 80.0) / 100.0
        cm_drib = _get_attr(card_cm, "dribbling", 80.0) / 100.0
        
        screening_capacity = (cdm_def * 0.60 + cdm_phy * 0.40)
        progression_capacity = (cm_pass * 0.50 + cm_vis * 0.30 + cm_drib * 0.20)
        complementarity = _harmonic_mean(screening_capacity, progression_capacity)
        
        overlap = 0.0
        # If both are pure destroyers without progression
        if cdm_def > 0.80 and _get_attr(card_cm, "defending", 70.0) > 80.0 and cm_pass < 0.75:
            overlap += 0.15   # Midfield distribution bottleneck
            
        frictions = []
        if screening_capacity < 0.75:
            frictions.append({
                "rule": "RULE-PART-CDM-SCREEN",
                "penalty": 0.025,
                "reason": f"Central pivot lacks dominant ball-winning screening ({screening_capacity*100:.0f}%)."
            })
        if progression_capacity < 0.75:
            frictions.append({
                "rule": "RULE-PART-CM-PROGRESS",
                "penalty": 0.020,
                "reason": f"Central pivot lacks vertical progression passing ({progression_capacity*100:.0f}%)."
            })
            
        tot_friction = sum(f["penalty"] for f in frictions)
        mean_score = (score_cm + score_cdm) / 2.0
        synergy = max(0.0, min(1.0, mean_score + 0.15 * (complementarity - 0.50) - 0.10 * overlap - tot_friction))
        
        status: PartnershipStatus = (
            "ELITE_PARTNERSHIP" if synergy >= 0.82 else
            "COMPLEMENTARY_PARTNERSHIP" if synergy >= 0.72 else
            "FUNCTIONAL_PARTNERSHIP" if synergy >= 0.60 else
            "ASYMMETRIC_OR_FRICTIONAL"
        )
        
        return PartnershipEvaluation(
            partnership_type="CM_CDM",
            slot_1=slot_cm,
            card_1_name=cm_name,
            card_1_score=score_cm,
            slot_2=slot_cdm,
            card_2_name=cdm_name,
            card_2_score=score_cdm,
            mean_suitability=round(mean_score, 4),
            capability_complementarity=round(complementarity, 4),
            responsibility_overlap=round(overlap, 4),
            friction_penalties=frictions,
            total_friction=round(tot_friction, 4),
            synergy_score=round(synergy, 4),
            status=status,
            tactical_profile=tactical_profile,
            explanation=f"Central pivot: {cdm_name} defensive screening allows {cm_name} box-to-box progression.",
            tactical_notes=[
                f"Screening Capacity: {screening_capacity*100:.1f}%, Progression Capacity: {progression_capacity*100:.1f}%.",
                f"Pivot Complementarity: {complementarity*100:.1f}%.",
            ],
        )

    @staticmethod
    def evaluate_two_strikers(
        card_st1: Any,
        score_st1: float,
        card_st2: Any,
        score_st2: float,
        tactical_profile: str = "BALANCED",
        slot_st1: str = "LST",
        slot_st2: str = "RST",
    ) -> PartnershipEvaluation:
        """Evaluates Two-Striker combos: pace runner vs physical hold-up / target."""
        st1_name = _get_name(card_st1, "Striker 1")
        st2_name = _get_name(card_st2, "Striker 2")
        
        pace1 = _get_attr(card_st1, "pace", 82.0) / 100.0
        phy1 = _get_attr(card_st1, "physicality", 75.0) / 100.0
        pace2 = _get_attr(card_st2, "pace", 82.0) / 100.0
        phy2 = _get_attr(card_st2, "physicality", 75.0) / 100.0
        
        # Complementarity: one fast runner behind defense + one physical hold-up/aerial threat
        pace_threat = max(pace1, pace2)
        physical_anchor = max(phy1, phy2)
        complementarity = _harmonic_mean(pace_threat, physical_anchor)
        
        # Overlap penalty: both pure small pace runners or both slow target men
        overlap = 0.0
        if pace1 > 0.90 and pace2 > 0.90 and phy1 < 0.72 and phy2 < 0.72:
            overlap += 0.15   # Lacks aerial/physical anchor against low blocks
        elif pace1 < 0.75 and pace2 < 0.75:
            overlap += 0.20   # Lacks penetration behind defensive line
            
        frictions = []
        if max(pace1, pace2) < 0.80:
            frictions.append({
                "rule": "RULE-PART-2ST-PACE",
                "penalty": 0.025,
                "reason": "Neither striker possesses elite pace to stretch opponent backline."
            })
            
        tot_friction = sum(f["penalty"] for f in frictions)
        mean_score = (score_st1 + score_st2) / 2.0
        synergy = max(0.0, min(1.0, mean_score + 0.15 * (complementarity - 0.50) - 0.10 * overlap - tot_friction))
        
        status: PartnershipStatus = (
            "ELITE_PARTNERSHIP" if synergy >= 0.82 else
            "COMPLEMENTARY_PARTNERSHIP" if synergy >= 0.72 else
            "FUNCTIONAL_PARTNERSHIP" if synergy >= 0.60 else
            "ASYMMETRIC_OR_FRICTIONAL"
        )
        
        return PartnershipEvaluation(
            partnership_type="TWO_STRIKERS",
            slot_1=slot_st1,
            card_1_name=st1_name,
            card_1_score=score_st1,
            slot_2=slot_st2,
            card_2_name=st2_name,
            card_2_score=score_st2,
            mean_suitability=round(mean_score, 4),
            capability_complementarity=round(complementarity, 4),
            responsibility_overlap=round(overlap, 4),
            friction_penalties=frictions,
            total_friction=round(tot_friction, 4),
            synergy_score=round(synergy, 4),
            status=status,
            tactical_profile=tactical_profile,
            explanation=f"Strike partnership: {st1_name} & {st2_name} balance pace separation with hold-up anchor.",
            tactical_notes=[
                f"Pace Separation: {pace_threat*100:.1f}%, Physical Anchor: {physical_anchor*100:.1f}%.",
                f"Complementarity: {complementarity*100:.1f}%.",
            ],
        )

    @staticmethod
    def evaluate_cb_cb(
        card_cb1: Any,
        score_cb1: float,
        card_cb2: Any,
        score_cb2: float,
        tactical_profile: str = "BALANCED",
        slot_cb1: str = "LCB",
        slot_cb2: str = "RCB",
    ) -> PartnershipEvaluation:
        """Evaluates Central Defensive Unit: aggressive stopper vs recovery sweeper."""
        cb1_name = _get_name(card_cb1, "CB 1")
        cb2_name = _get_name(card_cb2, "CB 2")
        
        pace1 = _get_attr(card_cb1, "pace", 75.0) / 100.0
        phy1 = _get_attr(card_cb1, "physicality", 82.0) / 100.0
        def1 = _get_attr(card_cb1, "defending", 84.0) / 100.0
        pace2 = _get_attr(card_cb2, "pace", 75.0) / 100.0
        phy2 = _get_attr(card_cb2, "physicality", 82.0) / 100.0
        def2 = _get_attr(card_cb2, "defending", 84.0) / 100.0
        
        # Stopper (physical + defending) and Sweeper (pace + defending awareness)
        recovery_pace = max(pace1, pace2)
        physical_stopper = max(phy1, phy2)
        complementarity = _harmonic_mean(recovery_pace, physical_stopper)
        
        overlap = 0.0
        if pace1 < 0.72 and pace2 < 0.72:
            overlap += 0.18   # Fatal recovery speed vulnerability
            
        frictions = []
        if min(def1, def2) < 0.78:
            frictions.append({
                "rule": "RULE-PART-CB-DEF",
                "penalty": 0.020,
                "reason": "One central defender has defending below 78, creating an exploitable defensive seam."
            })
        if recovery_pace < 0.75:
            frictions.append({
                "rule": "RULE-PART-CB-PACE",
                "penalty": 0.025,
                "reason": "Defensive unit lacks recovery pace to withstand high-line through balls."
            })
            
        tot_friction = sum(f["penalty"] for f in frictions)
        mean_score = (score_cb1 + score_cb2) / 2.0
        synergy = max(0.0, min(1.0, mean_score + 0.15 * (complementarity - 0.50) - 0.10 * overlap - tot_friction))
        
        status: PartnershipStatus = (
            "ELITE_PARTNERSHIP" if synergy >= 0.82 else
            "COMPLEMENTARY_PARTNERSHIP" if synergy >= 0.72 else
            "FUNCTIONAL_PARTNERSHIP" if synergy >= 0.60 else
            "ASYMMETRIC_OR_FRICTIONAL"
        )
        
        return PartnershipEvaluation(
            partnership_type="CB_CB",
            slot_1=slot_cb1,
            card_1_name=cb1_name,
            card_1_score=score_cb1,
            slot_2=slot_cb2,
            card_2_name=cb2_name,
            card_2_score=score_cb2,
            mean_suitability=round(mean_score, 4),
            capability_complementarity=round(complementarity, 4),
            responsibility_overlap=round(overlap, 4),
            friction_penalties=frictions,
            total_friction=round(tot_friction, 4),
            synergy_score=round(synergy, 4),
            status=status,
            tactical_profile=tactical_profile,
            explanation=f"Central defense: {cb1_name} & {cb2_name} balance physical stopper engagement with recovery coverage.",
            tactical_notes=[
                f"Recovery Pace: {recovery_pace*100:.1f}%, Physical Dominance: {physical_stopper*100:.1f}%.",
                f"Defensive Unit Complementarity: {complementarity*100:.1f}%.",
            ],
        )
