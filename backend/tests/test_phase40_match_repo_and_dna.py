"""Phase 40 Match Intelligence Repository, Gamer DNA, Synthetic Firewall & Privacy Tests."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.domain.phase40_models import (
    ColdStartPreferences,
    EvidenceClipRef,
    MatchRecordCreate,
    SquadSlotSnapshot,
)
from backend.repositories.phase40_repository import DuplicateMatchError, Phase40Repository
from backend.services.gamer_dna_engine import GamerDNAEngine
from backend.services.recurring_mistake_analyzer import RecurringMistakeAnalyzer


def _make_match_req(
    *,
    video_id: str = "VID-REAL-1",
    provenance: str = "REAL_VIDEO_DECODED",
    patch: str = "PATCH_1.02",
    formation: str = "4-3-3",
    possession: float = 0.60,
    compactness: float = 0.72,
    exposed_trans: int = 1,
    findings: list | None = None,
) -> MatchRecordCreate:
    return MatchRecordCreate(
        video_id=video_id,
        game_version="FC27",
        game_patch=patch,
        gameplay_mode="COMPETITIVE_RIVALS",
        duration_seconds=360.0,
        formation=formation,
        tactical_profile="POSSESSION",
        squad_slots=[
            SquadSlotSnapshot(slot_index=0, slot_position="GK", player_name="Maignan", overall_rating=88),
            SquadSlotSnapshot(slot_index=1, slot_position="CDM", player_name="Tchouameni", overall_rating=86, assigned_role="Holding", playstyles=["Intercept"]),
        ],
        provenance=provenance,  # type: ignore[arg-type]
        observation_quality="HIGH",
        tracking_coverage_pct=91.5,
        feature_metrics={
            "possession_share": possession,
            "attacking_directness": 0.45,
            "passing_tempo": 0.58,
            "passing_risk": 0.42,
            "chance_creation": 0.65,
            "wing_utilization": 0.62,
            "central_progression": 0.67,
            "dribbling_tendency": 0.50,
            "finishing_decisions": 0.60,
            "defensive_compactness": compactness,
            "pressing_intensity": 0.54,
            "defensive_transition_management": max(0.2, 0.85 - 0.15 * exposed_trans),
            "tactical_discipline": 0.74,
            "adaptability": 0.62,
            "decision_making_under_pressure": 0.64,
            "transition_opportunities": 8,
            "exposed_transitions": exposed_trans,
            "central_pass_opportunities": 10,
            "risky_central_passes": 2,
            "sequence_clusters": 12,
        },
        coaching_findings=findings if findings is not None else [
            {
                "diagnostic_id": "DIAG-1",
                "code": "EXPOSED_CENTRAL_CHANNEL",
                "severity": "HIGH",
                "confidence_level": "MODERATE",
                "timestamp_start": 14.5,
                "timestamp_end": 18.0,
            }
        ],
        evidence_clips=[
            EvidenceClipRef(
                match_id="",
                video_id=video_id,
                timestamp_start=14.5,
                timestamp_end=18.0,
                title="Exposed Central Channel",
                diagnostic_code="EXPOSED_CENTRAL_CHANNEL",
                provenance=provenance,
            )
        ],
    )


def test_duplicate_detection_and_immutable_squad_snapshot():
    repo = Phase40Repository(force_memory=True)
    uid = str(uuid.uuid4())
    req = _make_match_req(video_id="VID-100")

    rec = repo.save_match(uid, req)
    assert rec.squad_snapshot is not None
    assert rec.squad_snapshot.slots[1].player_name == "Tchouameni"
    assert rec.evidence_clips[0].deep_link.startswith("/research/gameplay-studio?video_id=VID-100")

    with pytest.raises(DuplicateMatchError):
        repo.save_match(uid, req)

    # Second match changes active squad -> historical snapshot on first match stays immutable
    req2 = _make_match_req(video_id="VID-101", formation="4-2-3-1")
    req2.squad_slots[1] = SquadSlotSnapshot(slot_index=1, slot_position="CDM", player_name="Kante", overall_rating=89)
    rec2 = repo.save_match(uid, req2)

    loaded_1 = repo.get_match(uid, rec.match_id)
    assert loaded_1.formation == "4-3-3"
    assert loaded_1.squad_snapshot.slots[1].player_name == "Tchouameni"
    assert rec2.squad_snapshot.slots[1].player_name == "Kante"


def test_strict_synthetic_firewall_excludes_fixtures_from_gamer_dna_and_mistakes():
    repo = Phase40Repository(force_memory=True)
    uid = str(uuid.uuid4())
    synth = _make_match_req(video_id="VID-SYNTH", provenance="SYNTHETIC_FIXTURE", exposed_trans=4)
    repo.save_match(uid, synth)

    matches = repo.list_matches(uid)
    dna = GamerDNAEngine().build_profile(uid, matches)
    assert dna.eligible_match_count == 0
    assert dna.synthetic_excluded_count == 1
    assert dna.archetype.status == "INSUFFICIENT_EVIDENCE"
    assert all(d.status == "INSUFFICIENT_EVIDENCE" and d.estimated_value is None for d in dna.proficiency_dimensions)

    mistakes = RecurringMistakeAnalyzer().analyze(matches, include_synthetic_preview=False)
    assert mistakes == []


def test_recency_weighting_cluster_cap_and_16_dimensions():
    repo = Phase40Repository(force_memory=True)
    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Older match with lower compactness (30 days old)
    m_old = repo.save_match(uid, _make_match_req(video_id="V-OLD", compactness=0.25))
    m_old.created_at = (now - timedelta(days=30)).isoformat()

    # Two recent matches with high compactness
    m_new1 = repo.save_match(uid, _make_match_req(video_id="V-NEW1", compactness=0.90))
    m_new1.created_at = (now - timedelta(days=1)).isoformat()
    m_new2 = repo.save_match(uid, _make_match_req(video_id="V-NEW2", compactness=0.88))
    m_new2.created_at = now.isoformat()

    dna = GamerDNAEngine(recency_lambda=0.05).build_profile(uid, repo.list_matches(uid), now_dt=now)
    assert len(dna.style_dimensions) == 8
    assert len(dna.proficiency_dimensions) == 8
    assert dna.eligible_match_count == 3

    comp = next(d for d in dna.proficiency_dimensions if d.dimension == "defensive_compactness")
    assert comp.status == "OBSERVED"
    assert comp.estimated_value is not None and comp.estimated_value > 0.70
    assert comp.ci_low is not None and comp.ci_high is not None and comp.ci_low < comp.estimated_value < comp.ci_high
    # Cluster correlation cap keeps effective_sample_size bounded well below raw synthetic frame counts (e.g. < 50)
    assert 2.0 <= comp.effective_sample_size <= 40.0

    cons = next(d for d in dna.proficiency_dimensions if d.dimension == "match_to_match_consistency")
    assert cons.status == "OBSERVED"
    assert cons.relevant_match_count == 3


def test_cold_start_preferences_via_api_and_privacy_reset(auth_client):
    r = auth_client.post(
        "/api/phase40/gamer-dna/cold-start",
        json=ColdStartPreferences(
            preferred_tempo="FAST_DIRECT",
            pressing_comfort="MID_BLOCK",
            width_preference="WIDE_WINGPLAY",
            preferred_formation="4-4-2",
        ).model_dump(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_cold_start_preferences"] is True
    assert body["eligible_match_count"] == 0
    assert body["archetype"]["status"] == "UNCERTAIN_COLD_START"
    assert body["pro_comparison"]["named_pro_similarity_blocked"] is True

    # Delete privacy reset
    r_del = auth_client.delete("/api/phase40/privacy/reset")
    assert r_del.status_code == 200
    assert r_del.json()["status"] == "RESET_COMPLETE"
