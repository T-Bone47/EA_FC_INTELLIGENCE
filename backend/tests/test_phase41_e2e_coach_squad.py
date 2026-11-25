"""Phase 41 E2E API Tests: Auth/IDOR Isolation, 12 New Coach Tools, Fit Bottleneck, Squad Simulation & Blind Review."""
from __future__ import annotations

import uuid

from backend.services.coach_tools import CoachToolRegistry


def _timeline_snapshots() -> list[dict]:
    snaps = []
    for i in range(6):
        snaps.append({
            "timestamp_sec": 10.0 + i * 3.0,
            "calibration_state": "GOOD",
            "uncertainty_band": "LOW",
            "observation_coverage_pct": 90.0,
            "possession_team": "HOME" if i < 4 else "AWAY",
            "ball_carrier_track_id": "H-CM" if i < 4 else "A-CAM",
            "ball_xy": [54.0 + i * 3.0, 34.0],
            "home_structure": {"rest_defense_count": 3, "def_to_mid_gap_m": 12.0},
            "kinematics": [
                {"track_id": "H-GK", "team": "HOME", "player_slot": "GK", "is_goalkeeper": True, "x_m": 5.0, "y_m": 34.0},
                {"track_id": "H-CM", "team": "HOME", "player_slot": "CM", "x_m": 54.0 + i * 3.0, "y_m": 34.0, "vx_mps": 1.2, "vy_mps": 0.0},
                {"track_id": "H-ST", "team": "HOME", "player_slot": "ST", "x_m": 76.0, "y_m": 35.0, "vx_mps": 2.4, "vy_mps": 0.0},
                {"track_id": "H-LW", "team": "HOME", "player_slot": "LW", "x_m": 72.0, "y_m": 56.0, "vx_mps": 3.0, "vy_mps": 0.0},
                {"track_id": "H-CDM", "team": "HOME", "player_slot": "CDM", "x_m": 44.0, "y_m": 33.0},
                {"track_id": "H-CB1", "team": "HOME", "player_slot": "CB", "x_m": 32.0, "y_m": 28.0},
                {"track_id": "A-CDM", "team": "AWAY", "player_slot": "CDM", "x_m": 61.0 + i * 2.0, "y_m": 34.3},
                {"track_id": "A-CAM", "team": "AWAY", "player_slot": "CAM", "x_m": 58.0, "y_m": 34.0},
                {"track_id": "A-CB1", "team": "AWAY", "player_slot": "CB", "x_m": 71.0, "y_m": 35.0},
                {"track_id": "A-GK", "team": "AWAY", "player_slot": "GK", "is_goalkeeper": True, "x_m": 99.0, "y_m": 34.0},
            ],
        })
    return snaps


def test_all_12_phase41_tools_registered_and_auth_required(app):
    from fastapi.testclient import TestClient

    assert len(CoachToolRegistry.PHASE41_TOOLS) == 12
    assert len(CoachToolRegistry.ALL_TOOLS) == 34

    with TestClient(app) as anon:
        assert anon.get("/api/phase41/health").status_code == 200
        assert anon.get("/api/phase41/windows").status_code == 401
        assert anon.get("/api/phase41/football-iq").status_code == 401


def test_complete_phase41_e2e_and_cross_user_isolation(app, auth_client):
    from fastapi.testclient import TestClient

    auth_client.delete("/api/phase40/privacy/reset")

    match_id = f"M-41-{uuid.uuid4().hex[:6]}"
    analyze = auth_client.post(
        "/api/phase41/analyze-match",
        json={
            "match_id": match_id,
            "provenance": "IMPORTED_MATCH_TRACE",
            "game_version": "FC27",
            "game_patch": "PATCH_1.02",
            "snapshots": _timeline_snapshots(),
        },
    )
    assert analyze.status_code == 201, analyze.text
    res = analyze.json()
    assert res["windows_detected"] >= 2
    assert res["evaluated_count"] >= 2
    win_id = res["windows"][0]["window_id"]

    # Blind review hides outcome by default, reveal_outcome=true unlocks when desired
    blind_res = auth_client.get(f"/api/phase41/windows/{win_id}?reveal_outcome=false")
    assert blind_res.status_code == 200
    assert blind_res.json()["blind_review_mode"] is True
    assert blind_res.json()["window"]["post_action_outcome"] is None

    # Save annotation + export to training scenario
    ann = auth_client.post(
        "/api/phase41/annotations",
        json={"window_id": win_id, "match_id": match_id, "best_option_id": "CAND-1", "defensible_option_ids": ["CAND-1"]},
    )
    assert ann.status_code == 201

    scn = auth_client.post(f"/api/phase41/windows/{win_id}/to-scenario")
    assert scn.status_code == 201
    assert scn.json()["scenario"]["hide_outcome_by_default"] is True

    # Coach integration answers decision/regret/Football IQ query cleanly using Phase 41 tools
    coach_res = auth_client.post(
        "/api/phase40/coach/ask",
        json={"question": "What is my Football IQ and passing decision regret across my analyzed windows?"},
    )
    assert coach_res.status_code == 200, coach_res.text
    c_json = coach_res.json()
    assert c_json["abstained"] is False
    tools_used = {t["tool"] for t in c_json["tool_trace"]}
    assert "get_football_iq_profile" in tools_used

    # Squad Decision Support + Capability Bottleneck endpoint
    sq = auth_client.post(
        "/api/phase41/squad-decision-support",
        json={"formation": "4-3-3", "tactical_profile": "BALANCED", "position": "CM", "slots": []},
    )
    assert sq.status_code == 200
    assert sq.json()["squad_decision_support"]["passing_outlets_score"] > 0.0
    assert sq.json()["squad_decision_support"]["frozen_v321_untouched"] is True

    # IDOR check: Second user MUST get 404 for User A's window
    with TestClient(app) as other:
        em = f"idor-{uuid.uuid4().hex[:8]}@example.com"
        s = other.post("/api/auth/signup", json={"email": em, "password": "Test-Passw0rd!xyz", "display_name": "Other"})
        assert s.status_code == 201
        other.headers["Authorization"] = f"Bearer {s.json()['access_token']}"
        assert other.get(f"/api/phase41/windows/{win_id}").status_code == 404
