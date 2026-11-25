"""V3.2.1 regressions for bounded personalization and honest lead evidence."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from backend.domain.card_model import ALL_ATTRS
from backend.domain.user_model import AttributePreference
from backend.services.capability_model import compute_capability
from backend.services.recommendation_engine_v3 import RecommendationEngineV3
from backend.services.v3_response_blocks import evidence_gap
from backend.tests.helpers import make_attrs, make_candidate, make_req


def test_preference_adjustments_preserve_monotonicity_under_missing_data():
    request = make_req(position="ST", tactical_profile="HIGH_PRESS",
                       attribute_preferences=[AttributePreference("volleys", weight=0.1)])
    demand = RecommendationEngineV3().recommend([], request).demand.vector
    assert sum(demand.values()) == pytest.approx(1.0)
    assert all(value > 0 for value in demand.values())
    values = dict.fromkeys(demand, 75)
    low = compute_capability(demand=demand, attributes=values, position="ST", reference=None)
    for attr in demand:
        hidden = compute_capability(demand=demand, attributes={**values, attr: None}, position="ST", reference=None)
        assert hidden.c_lo <= low.c_lo
        assert hidden.kappa < low.kappa


def test_soft_preference_changes_demand_and_rejects_unknown_attributes():
    engine = RecommendationEngineV3()
    request = make_req(position="ST", tactical_profile="HIGH_PRESS")
    base = engine.recommend([], request).demand.vector
    focused = replace(request, attribute_preferences=[AttributePreference("finishing", weight=2)])
    assert engine.recommend([], focused).demand.vector["finishing"] > base["finishing"]
    invalid = replace(request, attribute_preferences=[AttributePreference("finshing", weight=2)])
    with pytest.raises(ValueError, match="Unknown attribute preferences"):
        engine.recommend([], invalid)


def test_playstyle_input_is_normalized_without_erasing_role_affinity():
    engine = RecommendationEngineV3()
    request = make_req(position="ST", tactical_profile="BALANCED", desired_playstyles_plus=["Quick Step"])
    striker = make_candidate(name="Test striker", position="ST", playstyles_plus=["Quick Step"],
                             attrs=make_attrs(**dict.fromkeys(ALL_ATTRS, 80)))
    def score(req, candidate):
        result = engine.recommend([candidate], req)
        return next(mod.capped for mod in result.ranked[0].context.modifiers if mod.name == "playstyle")

    held = score(request, striker)
    assert held == pytest.approx(0.075)
    assert score(replace(request, desired_playstyles_plus=["  quick STEP+  ", "QUICK STEP"]), striker) == held
    keeper_style = replace(request, desired_playstyles_plus=["Far Reach"])
    assert score(keeper_style, replace(striker, playstyles_plus=["Far Reach"])) == pytest.approx(0.035)
    base_only = replace(striker, playstyles_plus=[], playstyles_base=["Quick Step"])
    assert score(request, base_only) == pytest.approx(held * 0.6)
    required = replace(request, required_playstyles=["quick step+"])
    assert engine.recommend([base_only], required).excluded[0].gate == "G6_required_playstyle"


@pytest.mark.parametrize("first,second,status,expected", [
    ((0.85, 0.85), (0.847, 0.847), "NEAR_TIE", (0.003, 0.003)),
    ((0.85, 0.86), (0.82, 0.88), "EVIDENCE_SENSITIVE", (-0.03, 0.04)),
    ((0.85, 0.86), (0.82, 0.848), "EVIDENCE_SENSITIVE", (0.002, 0.04)),
    ((0.85, 0.86), (0.82, 0.83), "CLEAR_SEPARATION", (0.02, 0.04)),
])
def test_comparison_confidence_uses_the_entire_modelled_margin(first, second, status, expected):
    a = SimpleNamespace(r=first[0], r_hi=first[1])
    b = SimpleNamespace(r=second[0], r_hi=second[1])
    result = evidence_gap(a, b, 0.005)
    assert result["status"] == status
    assert (result["margin_low"], result["margin_high"]) == pytest.approx(expected)
