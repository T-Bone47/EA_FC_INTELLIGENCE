"""Phase 41 Persistent Decision Intelligence Repository & Ownership Store.

Provides unified PostgreSQL + test-safe in-memory fallback (for isolated unit tests
when Postgres is intentionally mocked or tables absent) scoped strictly by `user_id`
for IDOR protection across decision windows, Football IQ profiles, blind-review
annotations, and Phase 42 training scenarios.
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional
from uuid import uuid4

from psycopg.types.json import Jsonb

from backend.core import db
from backend.domain.phase41_models import DecisionAnnotationRequest, DecisionTrainingScenario


class DecisionWindowNotFoundError(LookupError):
    """Raised when a decision window is missing or belongs to another user."""


def _pg_ready() -> bool:
    try:
        row = db.query_one("SELECT to_regclass('public.phase41_decision_opportunity') AS tbl")
        return bool(row and row.get("tbl"))
    except Exception:
        return False


def _user_exists_in_pg(user_id: str) -> bool:
    try:
        row = db.query_one("SELECT 1 AS ok FROM public.user_profile WHERE id = %s", (str(user_id),))
        return bool(row)
    except Exception:
        return False


class Phase41Repository:
    """User-scoped persistence for Phase 41 Decision Opportunities, IQ, Scenarios, and Annotations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: Dict[str, Dict[str, Dict[str, Any]]] = {}  # user_id -> {window_id: row}
        self._iq_profiles: Dict[str, Dict[str, Any]] = {}
        self._scenarios: Dict[str, List[Dict[str, Any]]] = {}
        self._annotations: Dict[str, List[Dict[str, Any]]] = {}

    def _use_pg(self, user_id: str) -> bool:
        return _pg_ready() and _user_exists_in_pg(user_id)

    def save_decision_windows(self, user_id: str, rows: List[Dict[str, Any]]) -> int:
        uid = str(user_id)
        if not rows:
            return 0
        if self._use_pg(uid):
            for row in rows:
                db.execute(
                    """
                    INSERT INTO public.phase41_decision_opportunity (
                        window_id, match_id, user_id, video_id, cluster_id,
                        decision_type, status, provenance, pre_action_cutoff_sec,
                        action_timestamp_sec, observation_adequacy, calibration_state,
                        coverage_pct, pre_action_state, post_action_outcome,
                        candidate_actions, counterfactual_comparison, regret_estimate,
                        normalized_regret, uncertainty_payload
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s
                    )
                    ON CONFLICT (window_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        pre_action_state = EXCLUDED.pre_action_state,
                        post_action_outcome = EXCLUDED.post_action_outcome,
                        candidate_actions = EXCLUDED.candidate_actions,
                        counterfactual_comparison = EXCLUDED.counterfactual_comparison,
                        regret_estimate = EXCLUDED.regret_estimate,
                        normalized_regret = EXCLUDED.normalized_regret,
                        uncertainty_payload = EXCLUDED.uncertainty_payload
                    """,
                    (
                        row["window_id"],
                        row["match_id"],
                        uid,
                        row.get("video_id"),
                        row["cluster_id"],
                        row["decision_type"],
                        row["status"],
                        row["provenance"],
                        float(row["pre_action_cutoff_sec"]),
                        float(row["action_timestamp_sec"]),
                        row["observation_adequacy"],
                        row.get("calibration_state", "GOOD"),
                        float(row.get("coverage_pct", 0.0)),
                        Jsonb(row.get("pre_action_state") or {}),
                        Jsonb(row["post_action_outcome"]) if row.get("post_action_outcome") is not None else None,
                        Jsonb(row.get("candidate_actions") or []),
                        Jsonb(row.get("counterfactual_comparison") or {}),
                        row.get("regret_estimate"),
                        row.get("normalized_regret"),
                        Jsonb(row.get("uncertainty_payload") or {}),
                    ),
                )
            return len(rows)

        with self._lock:
            store = self._windows.setdefault(uid, {})
            for r in rows:
                store[r["window_id"]] = dict(r)
        return len(rows)

    def list_decision_windows(
        self,
        user_id: str,
        *,
        match_id: Optional[str] = None,
        exclude_synthetic: bool = False,
        limit: int = 120,
    ) -> List[Dict[str, Any]]:
        uid = str(user_id)
        if self._use_pg(uid):
            clauses = ["user_id = %s"]
            params: List[Any] = [uid]
            if match_id:
                clauses.append("match_id = %s")
                params.append(match_id)
            if exclude_synthetic:
                clauses.append("provenance <> 'SYNTHETIC_FIXTURE'")
            params.append(limit)
            return db.query(
                f"""
                SELECT window_id, match_id, video_id, cluster_id, decision_type,
                       status, provenance, pre_action_cutoff_sec, action_timestamp_sec,
                       observation_adequacy, calibration_state, coverage_pct,
                       pre_action_state, post_action_outcome, candidate_actions,
                       counterfactual_comparison, regret_estimate, normalized_regret,
                       uncertainty_payload, created_at
                FROM public.phase41_decision_opportunity
                WHERE {' AND '.join(clauses)}
                ORDER BY action_timestamp_sec ASC, created_at DESC
                LIMIT %s
                """,
                tuple(params),
            )

        with self._lock:
            items = list(self._windows.get(uid, {}).values())
        if match_id:
            items = [i for i in items if i.get("match_id") == match_id]
        if exclude_synthetic:
            items = [i for i in items if i.get("provenance") != "SYNTHETIC_FIXTURE"]
        items.sort(key=lambda i: float(i.get("action_timestamp_sec", 0.0)))
        return items[:limit]

    def get_decision_window(self, user_id: str, window_id: str) -> Dict[str, Any]:
        uid = str(user_id)
        if self._use_pg(uid):
            row = db.query_one(
                """
                SELECT window_id, match_id, video_id, cluster_id, decision_type,
                       status, provenance, pre_action_cutoff_sec, action_timestamp_sec,
                       observation_adequacy, calibration_state, coverage_pct,
                       pre_action_state, post_action_outcome, candidate_actions,
                       counterfactual_comparison, regret_estimate, normalized_regret,
                       uncertainty_payload, created_at
                FROM public.phase41_decision_opportunity
                WHERE user_id = %s AND window_id = %s
                """,
                (uid, window_id),
            )
            if not row:
                raise DecisionWindowNotFoundError(f"Decision window {window_id!r} not found.")
            return row

        with self._lock:
            row = self._windows.get(uid, {}).get(window_id)
        if not row:
            raise DecisionWindowNotFoundError(f"Decision window {window_id!r} not found.")
        return dict(row)

    def save_football_iq_profile(self, user_id: str, profile: Dict[str, Any]) -> None:
        uid = str(user_id)
        if self._use_pg(uid):
            db.execute(
                """
                INSERT INTO public.phase41_football_iq_profile (
                    user_id, eligible_match_count, eligible_decision_windows,
                    synthetic_excluded_count, overall_football_iq, confidence,
                    dimensions, top_regret_clusters, calibration_caveat, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (user_id) DO UPDATE SET
                    eligible_match_count = EXCLUDED.eligible_match_count,
                    eligible_decision_windows = EXCLUDED.eligible_decision_windows,
                    synthetic_excluded_count = EXCLUDED.synthetic_excluded_count,
                    overall_football_iq = EXCLUDED.overall_football_iq,
                    confidence = EXCLUDED.confidence,
                    dimensions = EXCLUDED.dimensions,
                    top_regret_clusters = EXCLUDED.top_regret_clusters,
                    calibration_caveat = EXCLUDED.calibration_caveat,
                    updated_at = now()
                """,
                (
                    uid,
                    int(profile.get("eligible_match_count", 0)),
                    int(profile.get("eligible_decision_windows", 0)),
                    int(profile.get("synthetic_excluded_count", 0)),
                    profile.get("overall_football_iq"),
                    profile.get("confidence", "INSUFFICIENT"),
                    Jsonb(profile.get("dimensions") or []),
                    Jsonb(profile.get("top_regret_clusters") or []),
                    str(profile.get("calibration_caveat", "")),
                ),
            )
            return
        with self._lock:
            self._iq_profiles[uid] = dict(profile)

    def save_training_scenario(self, user_id: str, scenario: DecisionTrainingScenario) -> Dict[str, Any]:
        uid = str(user_id)
        payload = scenario.model_dump(mode="json")
        if self._use_pg(uid):
            db.execute(
                """
                INSERT INTO public.phase41_training_scenario (
                    scenario_id, user_id, match_id, window_id, skill_dimension, provenance, payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (scenario_id) DO UPDATE SET payload = EXCLUDED.payload
                """,
                (
                    scenario.scenario_id,
                    uid,
                    scenario.match_id,
                    scenario.window_id,
                    scenario.skill_dimension,
                    scenario.provenance,
                    Jsonb(payload),
                ),
            )
            return payload

        with self._lock:
            lst = self._scenarios.setdefault(uid, [])
            lst = [s for s in lst if s.get("scenario_id") != scenario.scenario_id]
            lst.insert(0, payload)
            self._scenarios[uid] = lst[:100]
        return payload

    def list_training_scenarios(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        uid = str(user_id)
        if self._use_pg(uid):
            rows = db.query(
                """
                SELECT payload FROM public.phase41_training_scenario
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (uid, limit),
            )
            return [r["payload"] for r in rows]
        with self._lock:
            return list(self._scenarios.get(uid, []))[:limit]

    def save_annotation(self, user_id: str, req: DecisionAnnotationRequest) -> Dict[str, Any]:
        uid = str(user_id)
        if self._use_pg(uid):
            row = db.query_one(
                """
                INSERT INTO public.phase41_decision_annotation (
                    user_id, window_id, match_id, annotator_role,
                    best_option_id, defensible_option_ids, disagreement_note, blind_review_completed
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING annotation_id::text, window_id, match_id, annotator_role,
                          best_option_id, defensible_option_ids, disagreement_note,
                          blind_review_completed, created_at
                """,
                (
                    uid,
                    req.window_id,
                    req.match_id,
                    req.annotator_role,
                    req.best_option_id,
                    Jsonb(req.defensible_option_ids),
                    req.disagreement_note,
                    req.blind_review_completed,
                ),
            )
            return dict(row or {})

        rec = {
            "annotation_id": str(uuid4()),
            "window_id": req.window_id,
            "match_id": req.match_id,
            "annotator_role": req.annotator_role,
            "best_option_id": req.best_option_id,
            "defensible_option_ids": list(req.defensible_option_ids),
            "disagreement_note": req.disagreement_note,
            "blind_review_completed": req.blind_review_completed,
        }
        with self._lock:
            self._annotations.setdefault(uid, []).insert(0, rec)
        return rec

    def reset_user_decision_data(self, user_id: str) -> None:
        uid = str(user_id)
        if self._use_pg(uid):
            for tbl in (
                "phase41_decision_annotation",
                "phase41_training_scenario",
                "phase41_football_iq_profile",
                "phase41_decision_opportunity",
            ):
                db.execute(f"DELETE FROM public.{tbl} WHERE user_id = %s", (uid,))
            return
        with self._lock:
            self._windows.pop(uid, None)
            self._iq_profiles.pop(uid, None)
            self._scenarios.pop(uid, None)
            self._annotations.pop(uid, None)


_GLOBAL_PHASE41_REPO = Phase41Repository()


def get_phase41_repository() -> Phase41Repository:
    return _GLOBAL_PHASE41_REPO
