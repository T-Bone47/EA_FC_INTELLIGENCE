"""Phase 40 End-to-End Integration, PersonalGameplayFit, Decision Review, Training BKT & Progression Tests."""
from __future__ import annotations

from backend.services.decision_review_service import DecisionReviewService


def _build_realistic_imported_frames(n_frames: int = 8) -> list[dict]:
    frames = []
    for idx in range(n_frames):
        t = idx * 1.0
        players = [{"track_id": "GK-H", "team": "HOME", "x_norm": 0.05, "y_norm": 0.50, "player_slot": "GK", "is_goalkeeper": True}]
        for j in range(10):
            players.append({
                "track_id": f"H-{j}",
                "team": "HOME",
                "x_norm": min(0.85, 0.20 + (j % 4) * 0.14),
                "y_norm": max(0.08, min(0.92, 0.14 + (j % 3) * 0.34)),
                "player_slot": "CB" if j < 2 else ("CDM" if j == 2 else "CM"),
                "is_goalkeeper": False,
            })
        for j in range(10):
            players.append({
                "track_id": f"A-{j}",
                "team": "AWAY",
                "x_norm": min(0.95, 0.42 + (j % 4) * 0.12),
                "y_norm": 0.18 + (j % 3) * 0.30,
                "player_slot": "CM",
                "is_goalkeeper": False,
            })
        frames.append({
            "frame_index": idx * 10,
            "timestamp_sec": t,
            "match_clock": f"12:{10 + idx:02d}",
            "ball_x_norm": 0.36 + 0.02 * idx,
            "ball_y_norm": 0.50,
            "players": players,
        })
    return frames


def test_decision_review_pre_action_and_abstention():
    svc = DecisionReviewService()

    # Calibrated good frame with candidate lanes -> computes heuristic regret without hindsight
    good_snap = {
        "timestamp_sec": 12.4,
        "calibration_state": "GOOD",
        "observation_coverage_pct": 88.0,
        "home_structure": {"rest_defense_count": 3},
        "passing_lanes": [
            {"target_slot": "CDM", "distance_m": 11.0, "nearest_defender_clearance_m": 6.2, "openness_score": 0.90, "status": "OPEN", "xt_gain": 0.008, "is_progressive": False},
            {"target_slot": "LW", "distance_m": 22.0, "nearest_defender_clearance_m": 7.5, "openness_score": 0.88, "status": "OPEN", "xt_gain": 0.065, "is_progressive": True},
            {"target_slot": "ST", "distance_m": 20.0, "nearest_defender_clearance_m": 1.1, "openness_score": 0.14, "status": "BLOCKED", "xt_gain": 0.045, "is_progressive": True},
        ],
    }
    rev = svc.review_frame("M-1", good_snap, observed_action_label="ST blocked pass")
    assert rev.status == "EVALUATED"
    assert rev.pre_action_only is True
    assert "HEURISTIC_ACTION_VALUE" in rev.model_disclaimer
    assert rev.regret_estimate is not None and rev.regret_estimate > 0.0

    # Poor calibration -> strict abstention
    bad_snap = {"timestamp_sec": 14.0, "calibration_state": "REJECTED", "observation_coverage_pct": 42.0}
    abstained = svc.review_frame("M-1", bad_snap)
    assert abstained.status == "ABSTAINED_INSUFFICIENT_CONTEXT"
    assert abstained.regret_estimate is None


def test_complete_end_to_end_phase40_workflow(auth_client):
    auth_client.delete("/api/phase40/privacy/reset")

    # Step 1: Import genuine tracking trace via existing Phase 39 endpoint
    trace_vid = "VID-P40-TRACE-01"
    tr = auth_client.post(
        "/api/research/traces/import",
        json={"video_id": trace_vid, "frames": _build_realistic_imported_frames(8)},
    )
    assert tr.status_code == 200, tr.text

    # Step 2: Persist analyzed match from imported video into Phase 40 Match Repository (Match 1, Patch 1.01, 4-3-3)
    m1 = auth_client.post(
        f"/api/phase40/matches/from-video/{trace_vid}",
        params={"game_version": "FC27", "game_patch": "PATCH_1.01", "formation": "4-3-3", "tactical_profile": "HIGH_PRESS"},
    )
    assert m1.status_code == 201, m1.text
    m1_data = m1.json()
    assert m1_data["provenance"] == "IMPORTED_MATCH_TRACE"
    m1_id = m1_data["match_id"]

    # Step 3: Check Gamer DNA updated & check Recurring Mistakes
    dna_res = auth_client.get("/api/phase40/gamer-dna")
    assert dna_res.status_code == 200
    dna = dna_res.json()
    assert dna["eligible_match_count"] == 1
    assert dna["pro_comparison"]["named_pro_similarity_blocked"] is True

    mis_res = auth_client.get("/api/phase40/recurring-mistakes")
    assert mis_res.status_code == 200

    # Step 4: Ask Personal AI Coach
    coach_res = auth_client.post(
        "/api/phase40/coach/ask",
        json={"question": "Should I change tactics instead of spending coins, and what should I practise?", "game_version": "FC27"},
    )
    assert coach_res.status_code == 200
    c_body = coach_res.json()
    assert c_body["abstained"] is False
    assert c_body["training_objective"]

    # Step 5: Personalized Squad Lab Analysis + PersonalGameplayFit recommendations
    sq = auth_client.post(
        "/api/phase40/squad-intelligence/analyze",
        json={
            "game_version": "FC27",
            "formation": "4-3-3",
            "tactical_profile": "HIGH_PRESS",
            "budget_coins": 120000,
            "slots": [
                {"slot_index": 0, "slot_position": "GK", "player_name": "Courtois", "overall_rating": 89},
                {"slot_index": 1, "slot_position": "CDM", "player_name": "Rodri", "overall_rating": 91},
            ],
        },
    )
    assert sq.status_code == 200, sq.text
    sq_data = sq.json()
    assert sq_data["frozen_v321_untouched"] is True
    assert sq_data["chemistry"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert isinstance(sq_data["no_purchase_improvements"], list)

    fit = auth_client.get("/api/phase40/recommendations/personal-fit", params={"game_version": "FC27", "position": "CDM"})
    assert fit.status_code == 200
    assert fit.json()["frozen_v321_untouched"] is True
    assert fit.json()["coefficient_disclosure"]["status"] == "ADVISORY_SHADOW_HEURISTIC_UNOPTIMIZED"

    # Step 6: Generate Training Plan & Submit Exercise Attempt (Experimental BKT update)
    plan_res = auth_client.get("/api/phase40/training/plan")
    assert plan_res.status_code == 200
    plan = plan_res.json()
    assert len(plan["exercises"]) >= 1
    ex = plan["exercises"][0]
    chosen = ex["defensible_option_ids"][0]
    att_res = auth_client.post(
        "/api/phase40/training/attempt",
        json={
            "plan_id": plan["plan_id"],
            "exercise_id": ex["exercise_id"],
            "skill_code": ex["skill_code"],
            "selected_option_id": chosen,
            "defensible_option_ids": ex["defensible_option_ids"],
        },
    )
    assert att_res.status_code == 200
    assert att_res.json()["bkt_state"]["attempts_count"] == 1
    assert att_res.json()["bkt_state"]["p_mastery"] > 0.25

    # Step 7: Record Subsequent Match under New Patch & Formation -> Compare & Track Progression
    m2 = auth_client.post(
        "/api/phase40/matches",
        json={
            "video_id": "VID-P40-SUBSEQ-02",
            "game_version": "FC27",
            "game_patch": "PATCH_1.02",
            "formation": "4-2-3-1",
            "provenance": "REAL_VIDEO_DECODED",
            "observation_quality": "HIGH",
            "tracking_coverage_pct": 92.0,
            "duration_seconds": 300.0,
            "feature_metrics": {"defensive_compactness": 0.84, "central_progression": 0.78, "transition_opportunities": 8, "exposed_transitions": 0, "sequence_clusters": 10},
            "coaching_findings": [],
        },
    )
    assert m2.status_code == 201
    m2_id = m2.json()["match_id"]

    cmp_res = auth_client.get(f"/api/phase40/matches/compare/{m1_id}/{m2_id}")
    assert cmp_res.status_code == 200
    warnings = cmp_res.json()["comparability_warnings"]
    assert any("Patch change" in w for w in warnings)
    assert any("Formation changed" in w for w in warnings)

    prog_res = auth_client.get("/api/phase40/progression")
    assert prog_res.status_code == 200
    prog = prog_res.json()
    assert prog["total_eligible_matches"] == 2
    assert prog["within_person_experiment_contract"]["contract_version"] == "phase41.n_of_1.v1"
