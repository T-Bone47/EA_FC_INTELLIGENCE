"""Production catalogue policy at HTTP boundaries. No database is required."""
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.deps import CurrentUser, current_user_required
from backend.api.main import create_app
from backend.core.config import Settings
from backend.services.data_license_gate import catalogue_release_permitted


class ProductionCatalogueTests(unittest.TestCase):
    def test_shipped_releases_lack_production_permission(self):
        for version in ("FC26", "FC27", "FC28"):
            for scope in ("game_player", "ut_card"):
                with self.subTest(version=version, scope=scope):
                    self.assertFalse(catalogue_release_permitted(version, scope))

    def test_production_denial_does_not_require_frozen_distribution_files(self):
        from backend.services.data_license_gate import DataLicenseGateFailure, Environment
        from backend.services.reference_distribution import resolve_serving_reference

        with patch("backend.services.reference_distribution.load_reference_distribution",
                   side_effect=AssertionError("unverified reference file must not be opened")):
            with self.assertRaises(DataLicenseGateFailure):
                resolve_serving_reference("FC26", "game_player", False, Environment.PRODUCTION)

    def test_data_routes_deny_before_repository_or_reference_reads(self):
        entity = uuid.uuid4()
        routes = (
            "/players", "/players/facets", f"/players/{entity}",
            "/cards", f"/cards/{entity}", f"/cards/{entity}/versions",
            f"/cards/{entity}/prices", f"/cards/{entity}/value",
            "/card-data-status", "/meta/reference",
        )
        app = create_app()
        user = CurrentUser(str(uuid.uuid4()), "test@example.invalid", "user", "test-session")
        app.dependency_overrides[current_user_required] = lambda: user
        with TestClient(app) as client, patch("backend.api.deps.get_settings") as settings, patch(
            "backend.repositories.player_repository.get_conn",
            side_effect=AssertionError("unverified catalogue must not be read"),
        ), patch("backend.api.routes.meta.query",
                 side_effect=AssertionError("unverified catalogue metadata must not be read")):
            for environment in ("production", "staging", "unknown"):
                settings.return_value = Settings(environment=environment)
                for version in ("FC26", "FC27"):
                    for route in routes:
                        with self.subTest(environment=environment, version=version, route=route):
                            response = client.get("/api" + route, params={"game_version": version})
                            self.assertEqual(response.status_code, 403, response.text)
                            self.assertEqual(response.json()["detail"]["error"], "DATA_LICENSE_GATE_FAILED")
            self.assertEqual(client.get("/api/saved-players").json(), {"items": [], "total": 0})
            self.assertEqual(client.post("/api/saved-players", json={
                "game_version": "FC26", "entity_type": "game_player", "entity_id": str(entity),
            }).status_code, 403)
            self.assertEqual(client.get(f"/api/squads/{entity}/evaluation").status_code, 410)
            self.assertEqual(client.post(f"/api/squads/{entity}/recommend-replacement",
                                         json={"slot_index": 0}).status_code, 410)
            self.assertEqual(client.post("/api/recommendations/parse-intent",
                                         json={"text": "quick midfielder", "game_version": "FC26"}).status_code, 410)
            self.assertEqual(client.get("/api/recommendations/feedback/analytics").status_code, 410)
            self.assertEqual(client.get("/api/meta/game-versions").json()[0]["status"], "NO_DATA")
            with patch("backend.core.db.query_one", return_value={"ready": True}):
                self.assertEqual(client.get("/api/health/ready").json(), {"status": "ready", "database": "up"})
