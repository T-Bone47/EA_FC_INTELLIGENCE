"""Integration test suite for Phase 37 FastAPI Endpoints."""
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def test_get_fused_telemetry():
    # VID-001 exists in register
    response = client.get("/api/research/fused-telemetry/VID-001?frame_count=20")
    assert response.status_code == 200
    data = response.json()
    assert data["video_id"] == "VID-001"
    assert data["total_frames"] == 20
    assert len(data["frames"]) == 20

    first_frame = data["frames"][0]
    assert "home_players" in first_frame
    assert "away_players" in first_frame
    assert len(first_frame["home_players"]) >= 8
    assert len(first_frame["away_players"]) == 11
    assert first_frame["home_shape"] is not None
    assert first_frame["home_shape"]["convex_hull_area_m2"] > 0.0


def test_run_automated_detection():
    response = client.post("/api/research/automated-detection/VID-001")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["events_proposed_count"] >= 3
    assert len(data["events"]) >= 3

    # Verify SHA-256 integrity seal and review status on proposed events
    first_ev = data["events"][0]
    assert first_ev["integrity_hash"] is not None
    assert len(first_ev["integrity_hash"]) == 64
    assert first_ev["review_status"] == "UNDER_REVIEW"
    assert first_ev["observation_method"] == "AUTOMATED_DETECTOR"


def test_get_bayesian_calibration():
    response = client.get("/api/research/bayesian-calibration")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "V3.3-CANDIDATE"
    assert data["baseline_frozen_version"] == "V3.2.1"
    assert data["total_parameters_calibrated"] >= 8

    # Find high press modifier
    hp = next(p for p in data["parameters"] if p["parameter_name"] == "mod_high_press_forward_def")
    assert hp["v321_prior_mean"] == 1.15
    assert hp["posterior_mean"] > 1.15
    assert 0.0 < hp["shrinkage_factor"] < 1.0


def test_simulate_recommendation_score():
    payload = {
        "card_name": "Ousmane Dembélé",
        "card_item_id": "dembele-86-gold",
        "tactical_context": "HIGH_PRESS",
        "card_attributes": {
            "PAC": 93.0, "SHO": 78.0, "PAS": 82.0, "DRI": 90.0, "DEF": 55.0, "PHY": 65.0
        }
    }
    response = client.post("/api/research/bayesian-calibration/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["card_name"] == "Ousmane Dembélé"
    assert data["v321_baseline_score"] > 0.0
    assert data["v33_posterior_score"] > 0.0
    assert data["score_delta"] > 0.0
    assert "shrinkage" in data["shrinkage_explanation"].lower()
