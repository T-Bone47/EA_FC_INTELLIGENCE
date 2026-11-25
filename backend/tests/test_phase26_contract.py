"""API contract and service-path regressions. Run with backend requirements installed."""
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.schemas_v3 import RecommendationRequestV3
from backend.services.data_license_gate import Environment
from backend.services.recommendation_service_v3 import RecommendationServiceV3
from backend.tests.helpers import make_candidate


class TestPhase26Contract(unittest.TestCase):
    def test_v3_rejects_nonnull_squad_and_duplicate_compare_ids(self):
        client = TestClient(app)
        request = {"game_version": "FC26", "position": "CM"}
        player = str(uuid.uuid4())
        self.assertEqual(client.post("/api/v3/recommendations", json=dict(request, squad_id=player)).status_code, 422)
        self.assertEqual(client.post("/api/v3/compare", json={"request": request, "entity_ids": [player, player]}).status_code, 422)
        self.assertIsNone(RecommendationRequestV3(**request, squad_id=None).squad_id)

    def test_production_refuses_legacy_and_cannot_downgrade_licence_environment(self):
        with patch("backend.api.deps.get_settings") as deps_settings, patch(
            "backend.core.config.get_settings", return_value=SimpleNamespace(environment="production")
        ):
            from backend.core.config import Settings
            deps_settings.return_value = Settings(environment="production")
            client = TestClient(app)
            self.assertEqual(client.post("/api/recommendations", json={"game_version": "FC26", "position": "CM"}).status_code, 410)
            self.assertEqual(client.post("/api/compare", json={"game_version": "FC26", "entity_ids": [str(uuid.uuid4()), str(uuid.uuid4())]}).status_code, 410)
            for game in ("FC26", "FC27"):
                service = RecommendationServiceV3(
                    environment=Environment.LOCAL, reference_version=game.lower() + "-players-2026-09-r1")
                result = service.recommend(RecommendationRequestV3(game_version=game, position="CM", include_research_data=True))
                self.assertEqual(result["error"], "RESEARCH_DATA_REFUSED_IN_PRODUCTION" if game == "FC27" else "DATA_LICENSE_GATE_FAILED")

    def test_what_if_correlation_and_pool_counts(self):
        candidates = [make_candidate(position="CM")]
        repository = SimpleNamespace(load_candidates=lambda *_args, **_kwargs: candidates)
        with patch("backend.core.config.get_settings", return_value=SimpleNamespace(environment="test")):
            response = RecommendationServiceV3(repository=repository).what_if(
                RecommendationRequestV3(game_version="FC26", position="CM"), [("press", {"tactical_profile": "HIGH_PRESS"})])
        variant = response["variants"][0]
        self.assertEqual(response["candidate_count"], 1)
        self.assertEqual(variant["candidate_count"], 1)
        self.assertEqual(response["request_id"], variant["parent_request_id"])
        self.assertNotEqual(response["request_id"], variant["request_id"])
