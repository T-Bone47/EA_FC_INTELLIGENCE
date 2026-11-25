"""Phase 41 API Routes: Decision Intelligence, Counterfactuals, Football IQ,
Blind-Review Decision Replay Lab, Multi-Answer Scenarios & Squad Decision Support.

Strictly scoped by authenticated `user.id` and protects pre-action integrity
with explicit `reveal_outcome` blind-review toggle.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.api.deps import CurrentUser, current_user_required, rate_limit_default
from backend.domain.phase40_models import SquadSlotSnapshot
from backend.domain.phase41_models import (
    CounterfactualComparison,
    DecisionAnnotationRequest,
    FootballDecisionState,
)
from backend.repositories.phase40_repository import get_phase40_repository
from backend.repositories.phase41_repository import (
    DecisionWindowNotFoundError,
    get_phase41_repository,
)
from backend.services.coach_tools import CoachToolRegistry
from backend.services.counterfactual_football_engine import CounterfactualFootballEngine
from backend.services.decision_scenario_service import DecisionScenarioService
from backend.services.decision_state_builder import (
    DecisionOpportunityDetector,
    build_state_from_snapshot,
)
from backend.services.defensive_and_chance_intelligence import OffBallOpportunityEngine
from backend.services.football_iq_engine import FootballIQEngine
from backend.services.personal_gameplay_fit import PersonalGameplayFitService
from backend.services.possession_value_engine import CalibratedEPVInterface
from backend.services.spatial_intelligence import SpatialIntelligenceEngine

router = APIRouter(
    prefix="/api/phase41",
    tags=["phase41-decision-intelligence"],
    dependencies=[Depends(rate_limit_default)],
)

_detector = DecisionOpportunityDetector()
_counterfactual = CounterfactualFootballEngine()
_iq_engine = FootballIQEngine()
_scenario_svc = DecisionScenarioService()
_off_ball = OffBallOpportunityEngine()
_fit_service = PersonalGameplayFitService()
_spatial = SpatialIntelligenceEngine()
_calibrated_gate = CalibratedEPVInterface()


class AnalyzeMatchDecisionsRequest(BaseModel):
    match_id: str = "M-41"
    video_id: Optional[str] = None
    provenance: str = "IMPORTED_MATCH_TRACE"
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = "PATCH_1.02"
    max_windows: int = Field(default=16, ge=1, le=60)
    snapshots: List[Dict[str, Any]] = Field(default_factory=list)
    tactical_events: List[Dict[str, Any]] = Field(default_factory=list)


class EvaluateSnapshotDecisionRequest(BaseModel):
    match_id: str = "ad-hoc-41"
    video_id: Optional[str] = None
    provenance: str = "IMPORTED_MATCH_TRACE"
    decision_type_hint: Optional[str] = None
    observed_action_label: Optional[str] = None
    observed_target_track_id: Optional[str] = None
    reveal_outcome: bool = False
    snapshot: Dict[str, Any] = Field(default_factory=dict)


class SquadDecisionSupportRequest(BaseModel):
    formation: str = "4-3-3"
    tactical_profile: str = "BALANCED"
    position: str = "CM"
    slots: List[SquadSlotSnapshot] = Field(default_factory=list)


def _strip_outcome_dict(row: Dict[str, Any], reveal_outcome: bool) -> Dict[str, Any]:
    out = dict(row)
    if not reveal_outcome:
        out["post_action_outcome"] = None
        if isinstance(out.get("pre_action_state"), dict):
            pre = dict(out["pre_action_state"])
            pre["post_action_outcome"] = None
            out["pre_action_state"] = pre
    return out


@router.get("/health")
def phase41_health() -> Dict[str, Any]:
    return {
        "status": "OK",
        "phase": "41",
        "frozen_v321_preserved": True,
        "tools_registered": len(CoachToolRegistry.ALL_TOOLS),
        "calibrated_epv_status": _calibrated_gate.status_report(),
        "anti_hindsight_enforced": True,
    }


@router.post("/analyze-match", status_code=201)
def analyze_match_decisions(
    body: AnalyzeMatchDecisionsRequest,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    snapshots = list(body.snapshots)
    events = list(body.tactical_events)
    provenance = body.provenance

    # Pull live Phase 39 telemetry from video store if snapshots were omitted and video_id provided
    if not snapshots and body.video_id:
        from backend.api.routes.video_research import (
            _EVENTS_STORE,
            _VIDEOS_STORE,
            _spatial_cache,
            _telemetry_store,
        )
        v_rec = _VIDEOS_STORE.get(body.video_id)
        if v_rec:
            provenance = v_rec.provenance.value
        cached = _spatial_cache.get(body.video_id)
        if cached and cached.get("frames"):
            snapshots = cached["frames"]
        elif _telemetry_store.get(body.video_id):
            spatial_res = _spatial.analyze_timeline(_telemetry_store[body.video_id], include_grid_per_frame=False)
            snapshots = spatial_res.get("frames", [])
        if not events and body.video_id in _EVENTS_STORE:
            events = [e.model_dump() for e in _EVENTS_STORE[body.video_id]]

    if not snapshots:
        raise HTTPException(
            status_code=422,
            detail="No spatial snapshots provided and no telemetry available for the requested video_id.",
        )

    states = _detector.detect_windows(
        body.match_id,
        snapshots,
        video_id=body.video_id,
        provenance=provenance,
        tactical_events=events,
        game_version=body.game_version,
        game_patch=body.game_patch,
        max_windows=body.max_windows,
    )

    repo41 = get_phase41_repository()
    stored_rows: List[Dict[str, Any]] = []
    evaluated_count = 0
    abstained_count = 0

    for st in states:
        comp = _counterfactual.evaluate(st)
        off_ball_runs = _off_ball.detect_runs(st)
        if comp.status == "EVALUATED":
            evaluated_count += 1
        else:
            abstained_count += 1

        st_pre_dict = st.model_copy(update={"post_action_outcome": None}, deep=True).model_dump(mode="json")
        st_pre_dict["off_ball_opportunities"] = [r.model_dump(mode="json") for r in off_ball_runs]

        row = {
            "window_id": st.window_id,
            "match_id": st.match_id,
            "video_id": st.video_id,
            "cluster_id": st.cluster_id,
            "decision_type": st.decision_type.value,
            "status": comp.status,
            "provenance": st.provenance,
            "pre_action_cutoff_sec": st.pre_action_cutoff_sec,
            "action_timestamp_sec": st.action_timestamp_sec,
            "observation_adequacy": st.adequacy.status.value,
            "calibration_state": st.calibration_state,
            "coverage_pct": st.observation_coverage_pct,
            "pre_action_state": st_pre_dict,
            "post_action_outcome": st.post_action_outcome.model_dump(mode="json") if st.post_action_outcome else None,
            "candidate_actions": [c.model_dump(mode="json") for c in comp.candidates],
            "counterfactual_comparison": comp.model_dump(mode="json"),
            "regret_estimate": comp.regret_estimate,
            "normalized_regret": comp.normalized_regret,
            "uncertainty_payload": comp.uncertainty.model_dump(mode="json") if comp.uncertainty else {},
        }
        stored_rows.append(row)

    repo41.save_decision_windows(user.id, stored_rows)
    all_wins = repo41.list_decision_windows(user.id, exclude_synthetic=False, limit=300)
    iq_profile = _iq_engine.compute_profile(user.id, all_wins)
    repo41.save_football_iq_profile(user.id, iq_profile.model_dump(mode="json"))

    return {
        "match_id": body.match_id,
        "video_id": body.video_id,
        "provenance": provenance,
        "windows_detected": len(stored_rows),
        "evaluated_count": evaluated_count,
        "abstained_count": abstained_count,
        "windows": [_strip_outcome_dict(r, reveal_outcome=False) for r in stored_rows],
        "football_iq": iq_profile.model_dump(mode="json"),
    }


@router.post("/evaluate-snapshot")
def evaluate_single_snapshot(
    body: EvaluateSnapshotDecisionRequest,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    if not body.snapshot:
        raise HTTPException(status_code=422, detail="snapshot payload is required.")
    state = build_state_from_snapshot(
        body.match_id,
        body.snapshot,
        video_id=body.video_id,
        provenance=body.provenance,
        decision_type_hint=body.decision_type_hint,
        observed_action_label=body.observed_action_label,
        observed_target_track_id=body.observed_target_track_id,
    )
    comp = _counterfactual.evaluate(state)
    runs = _off_ball.detect_runs(state)
    reg_rec = _counterfactual.to_regret_record(state, comp)
    return {
        "pre_action_state": state.model_copy(update={"post_action_outcome": None}, deep=True).model_dump(mode="json"),
        "counterfactual_comparison": comp.model_dump(mode="json"),
        "off_ball_opportunities": [r.model_dump(mode="json") for r in runs],
        "regret_record": reg_rec.model_dump(mode="json") if reg_rec else None,
        "blind_review_mode": not body.reveal_outcome,
    }


@router.get("/windows")
def list_decision_windows(
    match_id: Optional[str] = Query(None, max_length=120),
    exclude_synthetic: bool = Query(True),
    reveal_outcome: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    rows = get_phase41_repository().list_decision_windows(
        user.id,
        match_id=match_id,
        exclude_synthetic=exclude_synthetic,
        limit=limit,
    )
    return {
        "count": len(rows),
        "blind_review_mode": not reveal_outcome,
        "windows": [_strip_outcome_dict(r, reveal_outcome=reveal_outcome) for r in rows],
    }


@router.get("/windows/{window_id}")
def get_decision_window_detail(
    window_id: str,
    reveal_outcome: bool = Query(False),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    try:
        row = get_phase41_repository().get_decision_window(user.id, window_id)
    except DecisionWindowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "blind_review_mode": not reveal_outcome,
        "window": _strip_outcome_dict(row, reveal_outcome=reveal_outcome),
    }


@router.get("/football-iq")
def get_football_iq(user: CurrentUser = Depends(current_user_required)) -> Dict[str, Any]:
    repo41 = get_phase41_repository()
    all_wins = repo41.list_decision_windows(user.id, exclude_synthetic=False, limit=300)
    iq = _iq_engine.compute_profile(user.id, all_wins)
    repo41.save_football_iq_profile(user.id, iq.model_dump(mode="json"))
    return iq.model_dump(mode="json")


@router.post("/windows/{window_id}/to-scenario", status_code=201)
def convert_window_to_training_scenario(
    window_id: str,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    repo41 = get_phase41_repository()
    try:
        row = repo41.get_decision_window(user.id, window_id)
    except DecisionWindowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if row.get("status") != "EVALUATED":
        raise HTTPException(status_code=422, detail="Cannot convert an abstained window into a training scenario.")

    st = FootballDecisionState.model_validate(row["pre_action_state"])
    comp = CounterfactualComparison.model_validate(row["counterfactual_comparison"])
    scenario = _scenario_svc.build_scenario(st, comp)
    saved = repo41.save_training_scenario(user.id, scenario)
    return {"status": "SAVED", "scenario": saved}


@router.get("/scenarios")
def list_decision_scenarios(
    limit: int = Query(30, ge=1, le=100),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    items = get_phase41_repository().list_training_scenarios(user.id, limit=limit)
    return {"count": len(items), "scenarios": items}


@router.post("/annotations", status_code=201)
def submit_decision_annotation(
    body: DecisionAnnotationRequest,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    repo41 = get_phase41_repository()
    saved = repo41.save_annotation(user.id, body)
    return {"status": "SAVED", "annotation": saved}


@router.post("/squad-decision-support")
def evaluate_squad_decision_support(
    body: SquadDecisionSupportRequest,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    wins = get_phase41_repository().list_decision_windows(user.id, exclude_synthetic=False, limit=150)
    bottleneck = _fit_service.evaluate_decision_capability_bottleneck(wins, position=body.position)
    squad_sim = _fit_service.simulate_squad_decision_support(
        formation=body.formation,
        tactical_profile=body.tactical_profile,
        slots=body.slots,
        windows=wins,
    )
    return {
        "capability_vs_choice": bottleneck,
        "squad_decision_support": squad_sim,
    }
