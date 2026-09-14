"""Confidence services: entity data confidence + recommendation confidence."""
from __future__ import annotations

import pytest

from backend.services import recommendation_confidence
from backend.services.confidence_service import entity_data_confidence
from backend.services.fit_value import FitValue
from backend.services.scoring_config import COMPONENT_WEIGHTS
from backend.tests.helpers import make_attrs, make_candidate


def test_full_data_high_confidence():
    c = make_candidate(attrs=make_attrs(**{
        "short_passing": 85, "vision": 85, "long_passing": 80, "stamina": 88,
        "ball_control": 84, "composure": 82, "defensive_awareness": 70,
        "interceptions": 66, "positioning": 74, "dribbling_detail": 80}))
    rel = ["short_passing", "vision", "long_passing", "stamina", "ball_control",
           "composure", "defensive_awareness", "interceptions", "positioning",
           "dribbling_detail"]
    conf = entity_data_confidence(c, rel)
    assert conf.score > 0.85


def test_missing_playstyle_data_lowers_confidence_with_note():
    c = make_candidate(playstyle_published=False)
    conf = entity_data_confidence(c, ["stamina"])
    assert any("PlayStyles unpublished" in n for n in conf.notes)


def test_price_unknown_note_when_budget_relevant():
    c = make_candidate(price=None)
    conf = entity_data_confidence(c, ["stamina"], price_relevant=True)
    assert any("no verified market price" in n for n in conf.notes)


def test_recommendation_confidence_tracks_coverage():
    all_known = {n: FitValue.known(0.8) for n in COMPONENT_WEIGHTS}
    full = recommendation_confidence.compute(all_known)
    assert full.evidence_coverage == pytest.approx(1.0)
    partial = dict(all_known)
    partial["team_fit"] = FitValue.unknown("no squad")
    partial["playstyle_fit"] = FitValue.unknown("no request")
    p = recommendation_confidence.compute(partial)
    assert p.evidence_coverage == pytest.approx(1.0 - 0.10 - 0.15)
    assert p.score < full.score
    assert "team_fit" in p.unknown_components


def test_zero_known_components_low_confidence():
    comps = {n: FitValue.unknown("x") for n in COMPONENT_WEIGHTS}
    c = recommendation_confidence.compute(comps)
    assert c.evidence_coverage == 0.0
    assert c.score <= 0.3
