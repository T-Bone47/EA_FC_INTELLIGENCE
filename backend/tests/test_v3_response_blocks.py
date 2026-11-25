"""Phase 24 / Plan A -- pure unit tests for the v3 response-block builders (no DB)."""
from __future__ import annotations

from types import SimpleNamespace

from backend.services.v3_response_blocks import division_block


def _c(division):
    return SimpleNamespace(extra={} if division is None else {"division": division})


def test_division_block_counts_unknown_division_separately():
    b = division_block(None, [_c("Men's Football"), _c("Women's Football"), _c(None)])
    assert b["scope"] == "ALL_DIVISIONS"
    assert b["candidate_counts"] == {"Men's Football": 1, "UNKNOWN": 1, "Women's Football": 1}


def test_division_block_filtered_and_not_applicable():
    assert division_block("Men's Football", [_c("Men's Football")])["scope"] == "FILTERED"
    assert division_block(None, [_c("male")], applicable=False) == {
        "requested": None, "scope": "NOT_APPLICABLE", "candidate_counts": {}}


def test_confidence_block_is_none_without_context_confidence():
    from types import SimpleNamespace

    from backend.services.v3_response_blocks import confidence_block
    assert confidence_block(SimpleNamespace(confidence=None)) is None


def test_confidence_block_maps_engine_fields_and_marks_reporting_only():
    from types import SimpleNamespace

    from backend.services.v3_response_blocks import confidence_block
    ctx = SimpleNamespace(confidence={"level": "HIGH", "score_v2": 0.91, "reasons": ["a"], "composition": {"k": 1}})
    assert confidence_block(ctx) == {"level": "HIGH", "score": 0.91, "reasons": ["a"],
                                     "composition": {"k": 1}, "reporting_only": True}


def test_partial_evidence_candidate_reports_missing_attributes_and_wider_interval():
    import dataclasses

    from backend.services.recommendation_engine_v3 import RecommendationEngineV3
    from backend.services.v3_response_blocks import evidence_block
    from backend.tests._v32_support import fc26_pool, fc26_reference
    from backend.tests.helpers import make_req
    c = next(x for x in fc26_pool() if x.position_primary == "CM")
    from backend.domain.card_model import PlayerAttributes
    thin = dataclasses.replace(c, attributes=PlayerAttributes(
        values={k: v for i, (k, v) in enumerate(c.attributes.values.items()) if i % 5}))
    ref = fc26_reference()
    res = RecommendationEngineV3(reference=ref, data_version=ref.version).recommend(
        [thin], make_req(position="CM", tactical_profile="BALANCED", limit=5))
    ev = evidence_block(res.ranked[0].context, thin)
    assert ev["missing_attributes"] and ev["coverage"] < 1.0 and ev["interval"]["width"] > 0
