"""Unit and regression tests for Phase 34B Squad Synergy & Tactical Rules."""
from uuid import uuid4
import pytest

from backend.domain.card_model import PlayerAttributes
from backend.services.formations import FORMATION_SLOTS
from backend.services.squad_synergy import (
    FORMATION_CHANNELS,
    TACTICAL_RULES,
    compute_channel_metrics,
    compute_experimental_alignment_index,
    compute_whole_xi_synergy,
    evaluate_tactical_rules,
)


class MockCard:
    def __init__(self, name: str, pos: str, attrs: dict):
        self.entity_id = str(uuid4())
        self.name = name
        self.position_primary = pos
        self.attributes = PlayerAttributes(attrs)


def test_all_12_formations_mapped_completely_without_overlap():
    """Verify all 12 supported formations map to disjoint channels without loss."""
    assert len(FORMATION_CHANNELS) == len(FORMATION_SLOTS) == 12
    for form_name, slots in FORMATION_SLOTS.items():
        assert form_name in FORMATION_CHANNELS
        ch = FORMATION_CHANNELS[form_name]
        left, center, right = set(ch["LEFT_FLANK"]), set(ch["CENTRAL_SPINE"]), set(ch["RIGHT_FLANK"])
        
        # Disjointness check
        assert left.isdisjoint(center), f"{form_name}: Left and Center overlap"
        assert right.isdisjoint(center), f"{form_name}: Right and Center overlap"
        assert left.isdisjoint(right), f"{form_name}: Left and Right overlap"
        
        # Completeness check
        all_mapped = left | center | right
        formation_slots = {s.slot for s in slots}
        assert all_mapped == formation_slots, f"{form_name}: Mapped slots do not match formation slots"


def test_alignment_index_mathematical_precision():
    """Verify formula: I_align = max(0, min(1, r_bar - 0.5 * sigma_r - delta_friction))."""
    # Case 1: Identical scores (sigma = 0), no friction
    slots = [{"slot": f"S{i}", "score": 0.85} for i in range(10)]
    res = compute_experimental_alignment_index(slots, "HIGH_PRESS", [])
    assert res["mean_suitability"] == 0.85
    assert res["suitability_dispersion"] == 0.0
    assert res["friction_penalty"] == 0.0
    assert res["alignment_index_pct"] == 85.0
    assert res["status"] == "HIGH_ALIGNMENT"

    # Case 2: High dispersion penalty
    slots_mixed = [{"slot": "S1", "score": 0.95}, {"slot": "S2", "score": 0.55}]
    res_mixed = compute_experimental_alignment_index(slots_mixed, "HIGH_PRESS", [])
    assert res_mixed["mean_suitability"] == 0.75
    assert res_mixed["suitability_dispersion"] == 0.20
    # 0.75 - 0.5 * 0.20 = 0.65 -> 65.0%
    assert res_mixed["alignment_index_pct"] == 65.0
    assert res_mixed["status"] == "PARTIAL_ALIGNMENT"

    # Case 3: Empty squad
    res_empty = compute_experimental_alignment_index([], "HIGH_PRESS", [])
    assert res_empty["alignment_index_pct"] is None
    assert res_empty["status"] == "INSUFFICIENT_EVIDENCE"


def test_tactical_rules_provenance_and_reconstruction():
    """Verify tactical rule alerts contain real card attribute values and proper provenance."""
    # Create Mbappé-like forward: Defending 29, Pace 96
    low_def_fwd = MockCard("Kylian Mbappé", "ST", {
        "acceleration": 97, "sprint_speed": 96, "pace": 96, "finishing": 95,
        "defending": 29, "stamina": 83, "short_passing": 87
    })
    
    # Create Dembélé-like forward: Defending 55, Pace 90
    high_def_fwd = MockCard("Ousmane Dembélé", "ST", {
        "acceleration": 93, "sprint_speed": 88, "pace": 90, "finishing": 90,
        "defending": 55, "stamina": 75, "short_passing": 89
    })

    cards = {low_def_fwd.entity_id: low_def_fwd, high_def_fwd.entity_id: high_def_fwd}

    # Evaluate under HIGH_PRESS: Low def forward should trigger RULE-HP-FWD-DEF
    slots_hp = [{"slot": "ST", "position": "ST", "entity_id": low_def_fwd.entity_id, "score": 0.83}]
    alerts_hp = evaluate_tactical_rules(slots_hp, "HIGH_PRESS", cards)
    assert len(alerts_hp) == 1
    alert = alerts_hp[0]
    assert alert["rule_id"] == "RULE-HP-FWD-DEF"
    assert alert["attribute_value"] == 29
    assert alert["threshold"] == 40
    assert alert["evidence_classification"] == "EMPIRICALLY_SUPPORTED"
    assert "29" in alert["explanation"]
    assert "Dembélé" in alert["recommended_action"]

    # High def forward should NOT trigger the rule under HIGH_PRESS
    slots_high_def = [{"slot": "ST", "position": "ST", "entity_id": high_def_fwd.entity_id, "score": 0.85}]
    alerts_clean = evaluate_tactical_rules(slots_high_def, "HIGH_PRESS", cards)
    assert len(alerts_clean) == 0


def test_channel_metrics_handles_unscored_gk_and_unfilled_slots():
    """Verify channel calculation does not fail or divide by zero when GK is unscored or slots unfilled."""
    slots_433 = [
        {"slot": "GK", "item": None, "score": None}, # Unscored GK
        {"slot": "LCB", "item": {"name": "Van Dijk"}, "score": 0.88},
        {"slot": "RCB", "item": {"name": "Saliba"}, "score": 0.86},
        {"slot": "LB", "item": {"name": "Karchaoui"}, "score": 0.85},
        {"slot": "RB", "item": {"name": "Hakimi"}, "score": 0.86},
    ]
    
    channels = compute_channel_metrics("4-3-3", slots_433)
    spine = channels["CENTRAL_SPINE"]
    assert "GK" in spine["unscored_slots"]
    assert spine["scored_count"] == 2 # LCB and RCB
    assert spine["mean_suitability"] == 0.87 # (0.88 + 0.86) / 2
    assert spine["status"] == "OPTIMAL_ALIGNMENT"


def test_whole_xi_synergy_master_evaluator():
    """Verify master evaluator combines index, channels, and alerts deterministically."""
    low_def_fwd = MockCard("Kylian Mbappé", "ST", {
        "pace": 96, "finishing": 95, "defending": 29, "stamina": 83, "short_passing": 87
    })
    cards = {low_def_fwd.entity_id: low_def_fwd}
    
    slots = [
        {"slot": "GK", "score": None},
        {"slot": "LB", "score": 0.85},
        {"slot": "LCB", "score": 0.88},
        {"slot": "RCB", "score": 0.86},
        {"slot": "RB", "score": 0.86},
        {"slot": "LCM", "score": 0.84},
        {"slot": "CDM", "score": 0.85},
        {"slot": "RCM", "score": 0.87},
        {"slot": "LW", "score": 0.83},
        {"slot": "ST", "position": "ST", "entity_id": low_def_fwd.entity_id, "score": 0.83},
        {"slot": "RW", "score": 0.86},
    ]

    res = compute_whole_xi_synergy("4-3-3", "HIGH_PRESS", slots, cards)
    assert res["formation"] == "4-3-3"
    assert res["tactical_profile"] == "HIGH_PRESS"
    assert len(res["tactical_friction_alerts"]) == 1
    assert res["tactical_friction_alerts"][0]["rule_id"] == "RULE-HP-FWD-DEF"
    assert res["experimental_tactical_alignment"]["active_friction_count"] == 1
    assert res["experimental_tactical_alignment"]["status"] in ("HIGH_ALIGNMENT", "MODERATE_ALIGNMENT")
