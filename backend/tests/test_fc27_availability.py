"""Regression checks for release status and the FC27 serving boundary."""
from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout
import pytest

from backend.api.main import create_app
from backend.core import db
from backend.core.config import get_settings
from backend.services import fc27_card_research
from backend.services.recommendation_service_v3 import RecommendationServiceV3, ServiceRefusal
from backend.api.schemas_v3 import RecommendationRequestV3
from backend.tests.conftest import requires_db


@pytest.fixture
def local_client(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "fc27_card_research_enabled", True)
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        yield client


def scopes(client):
    result = client.get("/api/meta/availability")
    assert result.status_code == 200
    assert result.headers["Cache-Control"] == "private, no-store"
    return result.json()["versions"]["FC27"]


@requires_db
def test_reports_actual_scoped_counts_and_research_metadata(local_client):
    result = scopes(local_client)
    if any(result[s]["research"]["status"] == "DATA_NOT_INGESTED" for s in result):
        pytest.skip("Run against a PostgreSQL database with both FC27 research releases")
    params = {"game_version": "FC27", "include_research_data": True, "page_size": 1}
    players = local_client.get("/api/players", params=params).json()
    cards = local_client.get("/api/research/fc27/cards?include_research_data=true").json()
    for scope, served in (("game_player", players), ("ut_card", cards)):
        research = result[scope]["research"]
        assert research["status"] == "RESEARCH_RELEASE_AVAILABLE"
        assert research["record_count"] == served["total"] > 0
        assert research["reference_ready"] and served["research_only"]
        assert result[scope]["production"]["status"] == "PRODUCTION_NOT_APPROVED"
    assert result["ut_card"]["research"]["goalkeeper_reference_ready"] is False
    reference = local_client.get("/api/meta/reference", params=params).json()
    assert reference["status"] == "ACTIVE" and reference["research_only"]
    assert "ST" in reference["positions"] and reference["playstyles"]


@requires_db
def test_distinguishes_disabled_and_missing_card_reference(local_client, monkeypatch, tmp_path):
    before = scopes(local_client)["ut_card"]["research"]
    if before["status"] == "DATA_NOT_INGESTED":
        pytest.skip("Run against a PostgreSQL database with the pinned FC27 card release")
    assert before["status"] == "RESEARCH_RELEASE_AVAILABLE"
    with monkeypatch.context() as patch:
        patch.setattr(fc27_card_research, "research_artifact_path", lambda: tmp_path)
        failed = scopes(local_client)["ut_card"]["research"]
        assert failed["status"] == "REFERENCE_UNAVAILABLE"
        assert failed["record_count"] == before["record_count"]
        assert not failed["reference_ready"]
        assert local_client.get("/api/research/fc27/cards?include_research_data=true").status_code == 503
    monkeypatch.setattr(get_settings(), "fc27_card_research_enabled", False)
    disabled = scopes(local_client)["ut_card"]["research"]
    assert disabled["status"] == "RESEARCH_ACCESS_DISABLED" and disabled["record_count"] is None


def test_reports_database_connection_failure(local_client, monkeypatch):
    def offline():
        raise PoolTimeout("Offline")

    monkeypatch.setattr(db, "get_pool", offline)
    status = local_client.get("/api/meta/availability").json()
    assert status["database_status"] == "DATABASE_NOT_CONNECTED" and status["versions"] == {}


@requires_db
def test_production_does_not_expose_research_memberships(local_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "environment", "production")
    result = scopes(local_client)
    for scope in result.values():
        assert scope["local"] is None
        assert scope["research"]["status"] == "RESEARCH_ACCESS_DISABLED"
        assert scope["research"]["record_count"] is None
        assert scope["production"]["status"] == "PRODUCTION_NOT_APPROVED"
    params = {"game_version": "FC27", "include_research_data": True}
    for path in ("/api/players", "/api/meta/reference", "/api/research/fc27/cards"):
        assert local_client.get(path, params=params).status_code == 403
    payload = {"game_version": "FC27", "position": "ST", "include_research_data": True}
    assert local_client.post("/api/v3/recommendations", json=payload).status_code == 403


@requires_db
def test_service_uses_active_deployment_after_construction(local_client, monkeypatch):
    settings = get_settings()
    body = RecommendationRequestV3(game_version="FC27", position="ST", include_research_data=True)
    with monkeypatch.context() as patch:
        patch.setattr(settings, "environment", "production")
        service = RecommendationServiceV3()
        with pytest.raises(ServiceRefusal):
            service._resolve(body)
    reference, _ = service._resolve(body)
    assert reference.game_version == "FC27"
    assert reference.data_status == "RESEARCH_ONLY"
