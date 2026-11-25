"""Unit tests for Video Research FastAPI Endpoints (Phase 36)."""
import pytest
from starlette.testclient import TestClient
from backend.api.main import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_list_registered_videos(client):
    res = client.get("/api/research/videos")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 7
    ids = [v["video_id"] for v in data]
    assert "VID-001" in ids
    assert "VID-012" in ids


def test_filter_videos_by_tier(client):
    res = client.get("/api/research/videos?evidence_tier=TIER_A")
    assert res.status_code == 200
    data = res.json()
    for v in data:
        assert v["evidence_tier"] == "TIER_A"


def test_create_and_reject_duplicate_video(client):
    unique_url = "https://www.youtube.com/watch?v=unique-test-vid-123"
    body = {
        "source_url": unique_url,
        "title": "Test Tactical Match",
        "creator_name": "TestCreator",
        "publication_date": "2026-11-20",
        "video_type": "FULL_MATCH",
        "rights_status": "PUBLIC_EMBED_ONLY",
        "evidence_tier": "TIER_B"
    }
    res = client.post("/api/research/videos", json=body)
    assert res.status_code == 201
    created = res.json()
    assert created["source_url"] == unique_url

    # Duplicate must fail with 409
    res_dup = client.post("/api/research/videos", json=body)
    assert res_dup.status_code == 409


def test_create_and_review_tactical_event(client):
    evt_body = {
        "timestamp_start": 34.5,
        "timestamp_end": 37.0,
        "event_type": "INTERCEPTION",
        "team_identity": "HOME",
        "player_identity": "Virgil van Dijk",
        "formation_slot": "LCB",
        "tactical_context": "BALANCED",
        "pitch_zone": 6,
        "observed_action": "Interception in central defensive channel",
        "observed_outcome": "CLEAN_POSSESSION",
        "related_hypothesis": "HYP-PIVOT-SCREEN"
    }
    res = client.post("/api/research/videos/VID-001/events", json=evt_body)
    assert res.status_code == 201
    event_data = res.json()
    event_id = event_data["event_id"]
    assert event_data["integrity_hash"] is not None
    assert event_data["review_status"] == "DRAFT"

    # Review event to ACCEPTED
    review_body = {
        "review_status": "ACCEPTED",
        "reviewer_id": "senior-analyst-07",
        "review_notes": "Clean ground-truth interception verified against radar."
    }
    res_rev = client.post(f"/api/research/events/{event_id}/review", json=review_body)
    assert res_rev.status_code == 200
    rev_data = res_rev.json()
    assert rev_data["review_status"] == "ACCEPTED"
    assert rev_data["reviewer_id"] == "senior-analyst-07"
    assert len(rev_data["correction_history"]) >= 1


def test_local_video_analysis_enforces_rights(client):
    # Attempting to run CV analysis on YouTube URL must fail with 403 Forbidden
    res_yt = client.post("/api/research/local-video-analysis", json={"video_id": "VID-001"})
    assert res_yt.status_code == 403
    assert "restricted to Path A" in res_yt.json()["detail"]

    # Running CV on authorized local recording (VID-012) succeeds
    res_local = client.post("/api/research/local-video-analysis", json={"video_id": "VID-012"})
    assert res_local.status_code == 200
    local_data = res_local.json()
    assert local_data["status"] == "COMPLETED"
    assert local_data["fps_achieved"] >= 30.0


def test_gameplay_features_and_prediction_challenges(client):
    # Test feature vectors
    res_fv = client.get("/api/research/gameplay-features?tactical_context=HIGH_PRESS")
    assert res_fv.status_code == 200
    fvs = res_fv.json()
    assert len(fvs) >= 1

    # Test prediction challenges
    res_pc = client.get("/api/research/prediction-challenges")
    assert res_pc.status_code == 200
    pcs = res_pc.json()
    assert len(pcs) >= 1
    assert pcs[0]["hypothesis_code"] == "HYP-RULE-HP-FWD-DEF"
