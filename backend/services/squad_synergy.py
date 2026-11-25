"""Squad synergy, formation channel mappings, and reconstructable tactical rules (Phase 34B).

Provides deterministic, mathematically transparent Whole-XI tactical analysis:
- Exact formation-to-channel slot mappings across all 12 supported formations
- Experimental Tactical Alignment Index (heuristic with explicit mathematical definition)
- Reconstructable tactical friction alerts with rule provenance and real attribute values
- Channel evaluations (Left Flank, Central Spine, Right Flank) handling unscored GK & unfilled slots
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Literal, Optional, Set
from uuid import UUID

from backend.services.formations import FORMATION_SLOTS

EvidenceClass = Literal["EMPIRICALLY_SUPPORTED", "MODELED_HEURISTIC"]
AlignmentStatus = Literal["HIGH_ALIGNMENT", "MODERATE_ALIGNMENT", "PARTIAL_ALIGNMENT", "TACTICAL_DISSONANCE"]


# 1. Exact Formation Channel Partitioning across all 12 formations
FORMATION_CHANNELS: Dict[str, Dict[str, List[str]]] = {
    "4-2-3-1": {
        "LEFT_FLANK": ["LB", "LDM", "LAM"],
        "CENTRAL_SPINE": ["GK", "LCB", "RCB", "CAM", "ST"],
        "RIGHT_FLANK": ["RB", "RDM", "RAM"],
    },
    "4-3-3": {
        "LEFT_FLANK": ["LB", "LCM", "LW"],
        "CENTRAL_SPINE": ["GK", "LCB", "RCB", "CDM", "ST"],
        "RIGHT_FLANK": ["RB", "RCM", "RW"],
    },
    "4-4-2": {
        "LEFT_FLANK": ["LB", "LM", "LCM"],
        "CENTRAL_SPINE": ["GK", "LCB", "RCB", "LST", "RST"],
        "RIGHT_FLANK": ["RB", "RCM", "RM"],
    },
    "4-3-2-1": {
        "LEFT_FLANK": ["LB", "LCM", "LF"],
        "CENTRAL_SPINE": ["GK", "LCB", "RCB", "CDM", "ST"],
        "RIGHT_FLANK": ["RB", "RCM", "RF"],
    },
    "4-5-1": {
        "LEFT_FLANK": ["LB", "LM", "LCM"],
        "CENTRAL_SPINE": ["GK", "LCB", "RCB", "CDM", "ST"],
        "RIGHT_FLANK": ["RB", "RCM", "RM"],
    },
    "4-1-2-1-2": {
        "LEFT_FLANK": ["LB", "LCM"],
        "CENTRAL_SPINE": ["GK", "LCB", "RCB", "CDM", "CAM", "LST", "RST"],
        "RIGHT_FLANK": ["RB", "RCM"],
    },
    "3-5-2": {
        "LEFT_FLANK": ["LWB", "LCM"],
        "CENTRAL_SPINE": ["GK", "LCB", "CB", "RCB", "CDM", "LST", "RST"],
        "RIGHT_FLANK": ["RCM", "RWB"],
    },
    "3-4-2-1": {
        "LEFT_FLANK": ["LM", "LCM", "LAM"],
        "CENTRAL_SPINE": ["GK", "LCB", "CB", "RCB", "ST"],
        "RIGHT_FLANK": ["RCM", "RM", "RAM"],
    },
    "3-4-3": {
        "LEFT_FLANK": ["LWB", "LCM", "LW"],
        "CENTRAL_SPINE": ["GK", "LCB", "CB", "RCB", "ST"],
        "RIGHT_FLANK": ["RCM", "RWB", "RW"],
    },
    "5-3-2": {
        "LEFT_FLANK": ["LWB", "LCM"],
        "CENTRAL_SPINE": ["GK", "LCB", "CB", "RCB", "CDM", "LST", "RST"],
        "RIGHT_FLANK": ["RWB", "RCM"],
    },
    "5-2-1-2": {
        "LEFT_FLANK": ["LWB", "LCDM"],
        "CENTRAL_SPINE": ["GK", "LCB", "CB", "RCB", "CAM", "LST", "RST"],
        "RIGHT_FLANK": ["RWB", "RCDM"],
    },
    "4-2-2-2": {
        "LEFT_FLANK": ["LB", "LDM", "LAM"],
        "CENTRAL_SPINE": ["GK", "LCB", "RCB", "LST", "RST"],
        "RIGHT_FLANK": ["RB", "RDM", "RAM"],
    },
}


# 2. Formalized Tactical Rules with explicit mathematical provenance
TACTICAL_RULES: List[Dict[str, Any]] = [
    {
        "rule_id": "RULE-HP-FWD-DEF",
        "rule_version": "1.0.0",
        "tactical_profile": "HIGH_PRESS",
        "target_positions": ["ST", "CF", "LW", "RW", "LF", "RF", "LST", "RST"],
        "evaluated_capability": "High-turnover defensive disruption",
        "source_attribute": "defending",
        "threshold": 40,
        "operator": "<",
        "evidence_classification": "EMPIRICALLY_SUPPORTED",
        "friction_penalty": 0.025,
        "explanation": "Forward defending attribute is below 40, significantly reducing turnover winning rates in opponent third.",
        "recommended_action": "Deploy a pressing forward specialist (e.g. Dembélé, Alvarez) or transition team tactical profile to COUNTER_ATTACK.",
        "empirical_reference": "Phase 33 Experiment 001: Dembélé (55 Def) produced +2.0 tackles/90 and +2.0 interceptions/90 vs Mbappé (29 Def)."
    },
    {
        "rule_id": "RULE-HP-MID-STA",
        "rule_version": "1.0.0",
        "tactical_profile": "HIGH_PRESS",
        "target_positions": ["CM", "CDM", "LCM", "RCM", "LM", "RM", "LDM", "RDM", "LCDM", "RCDM"],
        "evaluated_capability": "Sustained 90-minute press recovery",
        "source_attribute": "stamina",
        "threshold": 75,
        "operator": "<",
        "evidence_classification": "MODELED_HEURISTIC",
        "friction_penalty": 0.020,
        "explanation": "Midfielder stamina is below 75, causing severe second-half pressing decay and central defensive transition vulnerabilities.",
        "recommended_action": "Equip Relentless PlayStyle or substitute prior to minute 65.",
        "empirical_reference": None
    },
    {
        "rule_id": "RULE-CA-FWD-PAC",
        "rule_version": "1.0.0",
        "tactical_profile": "COUNTER_ATTACK",
        "target_positions": ["ST", "CF", "LW", "RW", "LF", "RF", "LST", "RST"],
        "evaluated_capability": "Transition breakaway separation",
        "source_attribute": "pace",
        "threshold": 80,
        "operator": "<",
        "evidence_classification": "EMPIRICALLY_SUPPORTED",
        "friction_penalty": 0.030,
        "explanation": "Forward pace is below 80, preventing breakaway separation against recovering opponent center-backs.",
        "recommended_action": "Deploy a pace specialist with Quick Step / Rapid (e.g. Mbappé, Pajor) or shift tactical profile to POSSESSION.",
        "empirical_reference": "Phase 33 Experiment 001: Mbappé (96 Pace) generated +2.0 Shots on Target/90 on counter breakaways vs Dembélé (90 Pace)."
    },
    {
        "rule_id": "RULE-POS-MID-PAS",
        "rule_version": "1.0.0",
        "tactical_profile": "POSSESSION",
        "target_positions": ["CM", "CDM", "CAM", "LCM", "RCM", "LDM", "RDM", "LAM", "RAM"],
        "evaluated_capability": "Progressive build-up pass retention",
        "source_attribute": "short_passing",
        "threshold": 80,
        "operator": "<",
        "evidence_classification": "MODELED_HEURISTIC",
        "friction_penalty": 0.020,
        "explanation": "Central midfielder short passing is below 80, increasing dangerous middle-third turnover probability under pressure.",
        "recommended_action": "Prioritize an incisive playmaker with Tiki Taka or Incisive Pass PlayStyles.",
        "empirical_reference": None
    },
    {
        "rule_id": "RULE-WP-FLK-CRO",
        "rule_version": "1.0.0",
        "tactical_profile": "WING_PLAY",
        "target_positions": ["LW", "RW", "LM", "RM", "LB", "RB", "LWB", "RWB", "LF", "RF"],
        "evaluated_capability": "Wide crossing delivery",
        "source_attribute": "crossing",
        "threshold": 75,
        "operator": "<",
        "evidence_classification": "MODELED_HEURISTIC",
        "friction_penalty": 0.020,
        "explanation": "Wide flank crossing is below 75, reducing aerial target completion in the box.",
        "recommended_action": "Equip Whipped Cross PlayStyle or shift delivery to an overlapping wingback.",
        "empirical_reference": None
    }
]


def evaluate_tactical_rules(
    slots_data: List[Dict[str, Any]],
    tactical_profile: str,
    cards_by_id: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Evaluate explicit tactical rules against card attributes with complete provenance."""
    alerts = []
    
    for s in slots_data:
        slot_name = s["slot"]
        item_id = s.get("entity_id") or (s["item"]["entity_id"] if s.get("item") else None)
        if not item_id:
            continue
            
        card = cards_by_id.get(str(item_id)) or cards_by_id.get(item_id)
        if not card:
            continue

        pos = s.get("position") or getattr(card, "position_primary", "")
        attrs = getattr(card, "attributes", None)
        if attrs is None:
            continue

        for rule in TACTICAL_RULES:
            if rule["tactical_profile"] != tactical_profile:
                continue
            if pos not in rule["target_positions"] and slot_name not in rule["target_positions"]:
                continue

            attr_name = rule["source_attribute"]
            if hasattr(attrs, "get"):
                val = attrs.get(attr_name)
            elif hasattr(attrs, "values") and isinstance(attrs.values, dict):
                val = attrs.values.get(attr_name)
            elif isinstance(attrs, dict):
                val = attrs.get(attr_name)
            else:
                val = getattr(attrs, attr_name, None)
            
            if val is None:
                # Missing attribute handling
                alerts.append({
                    "rule_id": rule["rule_id"],
                    "rule_version": rule["rule_version"],
                    "slot": slot_name,
                    "position": pos,
                    "card_item_id": str(item_id),
                    "card_name": getattr(card, "name", "Unknown Card"),
                    "tactical_context": tactical_profile,
                    "evaluated_capability": rule["evaluated_capability"],
                    "attribute_name": attr_name,
                    "attribute_value": None,
                    "threshold": rule["threshold"],
                    "evidence_classification": "MISSING_DATA",
                    "friction_penalty": 0.0,
                    "explanation": f"Attribute {attr_name} is unpublished for {getattr(card, 'name', 'card')}.",
                    "recommended_action": "Review official EA card database updates.",
                    "missing_data_limitation": f"Card lacks published {attr_name} attribute."
                })
                continue

            # Evaluate rule condition
            violated = False
            if rule["operator"] == "<" and val < rule["threshold"]:
                violated = True
            elif rule["operator"] == "<=" and val <= rule["threshold"]:
                violated = True
            elif rule["operator"] == ">" and val > rule["threshold"]:
                violated = True

            if violated:
                alerts.append({
                    "rule_id": rule["rule_id"],
                    "rule_version": rule["rule_version"],
                    "slot": slot_name,
                    "position": pos,
                    "card_item_id": str(item_id),
                    "card_name": getattr(card, "name", "Unknown Card"),
                    "tactical_context": tactical_profile,
                    "evaluated_capability": rule["evaluated_capability"],
                    "attribute_name": attr_name,
                    "attribute_value": val,
                    "threshold": rule["threshold"],
                    "evidence_classification": rule["evidence_classification"],
                    "friction_penalty": rule["friction_penalty"],
                    "explanation": rule["explanation"].replace("is below", f"({val}) is below"),
                    "recommended_action": rule["recommended_action"],
                    "empirical_reference": rule.get("empirical_reference"),
                    "missing_data_limitation": None
                })
                
    return alerts


def compute_experimental_alignment_index(
    slots_data: List[Dict[str, Any]],
    tactical_profile: str,
    alerts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Compute mathematically reproducible Experimental Tactical Alignment Index.

    Formula:
      r_bar = (1 / |S|) * sum(r_i)  for scored slots
      sigma_r = sqrt((1 / |S|) * sum((r_i - r_bar)^2))
      delta_friction = sum(friction_penalty for confirmed alert violations)
      I_align = max(0.0, min(1.0, r_bar - 0.5 * sigma_r - delta_friction))
      Alignment Percentage = round(100 * I_align, 1)
    """
    scored = [s for s in slots_data if s.get("score") is not None]
    unscored = [s["slot"] for s in slots_data if s.get("score") is None]
    
    if not scored:
        return {
            "alignment_index_pct": None,
            "status": "INSUFFICIENT_EVIDENCE",
            "status_convention": "Zero scored slots available in squad.",
            "mean_suitability": None,
            "suitability_dispersion": None,
            "friction_penalty": 0.0,
            "active_friction_count": 0,
            "scored_slots_count": 0,
            "total_slots_count": len(slots_data),
            "unscored_slots": unscored
        }

    scores = [s["score"] for s in scored]
    n = len(scores)
    mean_fit = sum(scores) / n
    dispersion = math.sqrt(sum((x - mean_fit) ** 2 for x in scores) / n) if n > 1 else 0.0
    
    # Active friction penalty from non-missing data violations
    total_friction = sum(a["friction_penalty"] for a in alerts if a.get("friction_penalty"))
    
    raw_index = mean_fit - (0.5 * dispersion) - total_friction
    bounded_index = max(0.0, min(1.0, raw_index))
    pct = round(100.0 * bounded_index, 1)

    # Documented Model Convention Boundaries
    if pct >= 82.0:
        status: AlignmentStatus = "HIGH_ALIGNMENT"
    elif pct >= 72.0:
        status = "MODERATE_ALIGNMENT"
    elif pct >= 60.0:
        status = "PARTIAL_ALIGNMENT"
    else:
        status = "TACTICAL_DISSONANCE"

    return {
        "alignment_index_pct": pct,
        "status": status,
        "status_convention": "Explicit model convention: HIGH (>=82.0%), MODERATE (72.0-81.9%), PARTIAL (60.0-71.9%), DISSONANCE (<60.0%).",
        "mean_suitability": round(mean_fit, 4),
        "suitability_dispersion": round(dispersion, 4),
        "friction_penalty": round(total_friction, 4),
        "active_friction_count": len([a for a in alerts if a.get("friction_penalty", 0) > 0]),
        "scored_slots_count": n,
        "total_slots_count": len(slots_data),
        "unscored_slots": unscored
    }


def compute_channel_metrics(
    formation: str,
    slots_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Compute channel metrics across Left Flank, Central Spine, and Right Flank."""
    channels = FORMATION_CHANNELS.get(formation)
    if not channels:
        # Fallback to 4-3-3 if formation unknown
        channels = FORMATION_CHANNELS["4-3-3"]

    slots_by_name = {s["slot"]: s for s in slots_data}
    output = {}

    for ch_name, slot_names in channels.items():
        ch_slots = [slots_by_name[s] for s in slot_names if s in slots_by_name]
        scored_slots = [s for s in ch_slots if s.get("score") is not None]
        unscored_slots = [s["slot"] for s in ch_slots if s.get("score") is None]
        
        scores = [s["score"] for s in scored_slots]
        mean_fit = round(sum(scores) / len(scores), 4) if scores else None

        if mean_fit is None:
            status = "INSUFFICIENT_DATA"
        elif mean_fit >= 0.84:
            status = "OPTIMAL_ALIGNMENT"
        elif mean_fit >= 0.78:
            status = "SOLID_ALIGNMENT"
        else:
            status = "TACTICAL_VULNERABILITY"

        output[ch_name] = {
            "channel_name": ch_name,
            "assigned_slots": slot_names,
            "scored_count": len(scored_slots),
            "unscored_slots": unscored_slots,
            "mean_suitability": mean_fit,
            "status": status,
            "contributing_items": [
                {
                    "slot": s["slot"],
                    "player_name": s["item"]["name"] if s.get("item") else "Unfilled",
                    "score": s.get("score")
                }
                for s in ch_slots
            ]
        }

    return output


def compute_whole_xi_synergy(
    formation: str,
    tactical_profile: str,
    slots_data: List[Dict[str, Any]],
    cards_by_id: Dict[str, Any]
) -> Dict[str, Any]:
    """Master evaluator generating mathematically reconstructable Whole-XI analysis."""
    alerts = evaluate_tactical_rules(slots_data, tactical_profile, cards_by_id)
    alignment = compute_experimental_alignment_index(slots_data, tactical_profile, alerts)
    channels = compute_channel_metrics(formation, slots_data)

    return {
        "formation": formation,
        "tactical_profile": tactical_profile,
        "experimental_tactical_alignment": alignment,
        "channels": channels,
        "tactical_friction_alerts": alerts
    }
