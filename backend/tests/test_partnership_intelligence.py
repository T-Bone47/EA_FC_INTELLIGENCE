"""Unit tests for Partnership Intelligence V2 Engine (Phase 35)."""
import pytest
from backend.services.partnership_intelligence import (
    PartnershipIntelligenceEngine,
    _harmonic_mean,
)


def _make_dummy_card(name: str, attrs: dict):
    return {
        "name": name,
        "card_name": name,
        "attributes": attrs,
    }


def test_harmonic_mean_properties():
    assert round(_harmonic_mean(0.8, 0.8), 4) == 0.8
    # harmonic mean penalizes imbalance: (0.9, 0.5) is less than arithmetic mean 0.7
    h = _harmonic_mean(0.9, 0.5)
    assert h < 0.70
    assert round(h, 4) == 0.6429


def test_st_cam_complementary_dynamics():
    st = _make_dummy_card("Erling Haaland", {
        "finishing": 93, "positioning": 94, "pace": 89, "defending": 45, "stamina": 77
    })
    cam = _make_dummy_card("Kevin De Bruyne", {
        "vision": 94, "short_passing": 93, "dribbling": 87, "stamina": 83, "defending": 65
    })
    
    res = PartnershipIntelligenceEngine.evaluate_st_cam(
        st, 0.88, cam, 0.87, tactical_profile="BALANCED"
    )
    
    assert res.partnership_type == "ST_CAM"
    assert res.status == "ELITE_PARTNERSHIP"
    assert res.capability_complementarity > 0.85
    assert res.total_friction == 0.0
    assert res.synergy_score >= 0.85


def test_winger_fullback_flank_synergy():
    winger = _make_dummy_card("Vinicius Jr", {
        "pace": 96, "dribbling": 92, "crossing": 80, "defending": 32, "stamina": 82
    })
    fullback = _make_dummy_card("Ferland Mendy", {
        "pace": 91, "defending": 84, "stamina": 88, "crossing": 75
    })
    
    res = PartnershipIntelligenceEngine.evaluate_winger_fullback(
        winger, 0.89, fullback, 0.85, flank="LEFT", tactical_profile="BALANCED"
    )
    
    assert res.partnership_type == "WINGER_FULLBACK"
    assert res.status == "ELITE_PARTNERSHIP"
    assert res.capability_complementarity > 0.80
    assert res.synergy_score >= 0.85


def test_cm_cdm_pivot_balance():
    cdm = _make_dummy_card("Rodri", {
        "defending": 89, "physicality": 87, "short_passing": 88, "vision": 84
    })
    cm = _make_dummy_card("Federico Valverde", {
        "short_passing": 86, "vision": 84, "dribbling": 84, "pace": 88, "stamina": 92
    })
    
    res = PartnershipIntelligenceEngine.evaluate_cm_cdm(
        cm, 0.86, cdm, 0.89, tactical_profile="BALANCED"
    )
    
    assert res.partnership_type == "CM_CDM"
    assert res.status == "ELITE_PARTNERSHIP"
    assert res.total_friction == 0.0


def test_two_strikers_differentiation():
    target = _make_dummy_card("Harry Kane", {
        "pace": 72, "physicality": 84, "finishing": 93, "short_passing": 85
    })
    speedster = _make_dummy_card("Kylian Mbappé", {
        "pace": 97, "physicality": 77, "finishing": 92, "dribbling": 92
    })
    
    res = PartnershipIntelligenceEngine.evaluate_two_strikers(
        target, 0.84, speedster, 0.90, tactical_profile="BALANCED"
    )
    
    assert res.partnership_type == "TWO_STRIKERS"
    assert res.status == "ELITE_PARTNERSHIP"
    assert res.capability_complementarity > 0.80


def test_cb_cb_recovery_and_stopper():
    stopper = _make_dummy_card("Rúben Dias", {
        "pace": 74, "defending": 89, "physicality": 87
    })
    sweeper = _make_dummy_card("William Saliba", {
        "pace": 84, "defending": 87, "physicality": 82
    })
    
    res = PartnershipIntelligenceEngine.evaluate_cb_cb(
        stopper, 0.85, sweeper, 0.87, tactical_profile="BALANCED"
    )
    
    assert res.partnership_type == "CB_CB"
    assert res.status == "ELITE_PARTNERSHIP"
    assert res.capability_complementarity > 0.80


def test_high_press_friction_triggers():
    lazy_st = _make_dummy_card("Low Defending Striker", {
        "finishing": 90, "defending": 28, "stamina": 75, "pace": 90
    })
    cam = _make_dummy_card("Playmaker", {
        "vision": 85, "short_passing": 85, "stamina": 70
    })
    
    res = PartnershipIntelligenceEngine.evaluate_st_cam(
        lazy_st, 0.82, cam, 0.80, tactical_profile="HIGH_PRESS"
    )
    
    # Should detect defensive friction on striker and stamina on CAM
    assert res.total_friction > 0.0
    assert len(res.friction_penalties) == 2
    assert any("RULE-PART-ST-PRESS-DEF" in f["rule"] for f in res.friction_penalties)
    assert any("RULE-PART-CAM-STA" in f["rule"] for f in res.friction_penalties)
