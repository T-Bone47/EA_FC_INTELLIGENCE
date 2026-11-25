"""Unit tests for Recommendation Stability Engine (Phase 35)."""
import pytest
from unittest.mock import MagicMock
from backend.services.recommendation_stability import (
    CandidateStabilityProfile,
    RecommendationStabilityEngine,
)


def test_candidate_stability_profile_dataclass():
    prof = CandidateStabilityProfile(
        card_item_id="item-001",
        card_name="Test Striker",
        overall_rating=88,
        baseline_rank=1,
        baseline_score=0.885,
        min_rank=1,
        max_rank=2,
        rank_range=1,
        mean_rank=1.2,
        median_rank=1.0,
        rank_volatility=0.4,
        top_1_frequency_pct=80.0,
        top_3_frequency_pct=100.0,
        top_5_frequency_pct=100.0,
        stability_category="ROBUST_ACROSS_CONTEXTS",
        dominant_tactical_fit="BALANCED",
        vulnerable_tactical_fit="POSSESSION",
        robustness_explanation="Rock-solid performer across contexts.",
    )
    d = prof.to_dict()
    assert d["card_name"] == "Test Striker"
    assert d["stability_category"] == "ROBUST_ACROSS_CONTEXTS"
    assert d["top_1_frequency_pct"] == 80.0


def test_stability_engine_runs_scenarios():
    mock_service = MagicMock()
    
    # Mock return of run()
    mock_ranked_candidate = MagicMock()
    mock_ranked_candidate.context.candidate_entity_id = "card-123"
    mock_ranked_candidate.context.candidate_name = "Elite Forward"
    mock_ranked_candidate.context.r = 0.85
    mock_ranked_candidate.candidate.name = "Elite Forward"
    mock_ranked_candidate.candidate.overall_rating = 89
    
    mock_result = MagicMock()
    mock_result.ranked = [mock_ranked_candidate]
    mock_service.run.return_value = (mock_result, None, None, None)
    
    engine = RecommendationStabilityEngine(mock_service)
    report = engine.evaluate_position_stability(
        position="ST",
        formation="4-3-3",
    )
    
    assert report["evaluation_engine"] == "RecommendationStabilityLab-v1"
    assert report["position"] == "ST"
    assert report["total_scenarios_evaluated"] >= 6
    assert len(report["candidates"]) == 1
    
    cand = report["candidates"][0]
    assert cand["card_name"] == "Elite Forward"
    assert cand["baseline_rank"] == 1
    assert cand["stability_category"] == "ROBUST_ACROSS_CONTEXTS"
