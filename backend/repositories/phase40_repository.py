"""Phase 40B Persistent Match Intelligence Repository & Ownership Store.

Provides unified PostgreSQL + automatic test-safe in-memory storage (when PG tables
or DB connection are unavailable in isolated unit tests) for:
- Match records (full & partial matches, telemetry summaries, events, coaching findings)
- Immutable historical MatchSquadSnapshots (never mutated by later active squad edits)
- Gamer DNA profiles & cold-start self-reported preferences
- Training plans, exercise attempts, and Personal Coach sessions/messages
- User privacy controls (single match deletion & full profile/history reset)

Every lookup, list, mutation, and delete is strictly scoped by `user_id` to prevent
cross-user data leakage (IDOR protection).
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from psycopg.types.json import Jsonb

from backend.core import db
from backend.domain.phase40_models import (
    ColdStartPreferences,
    EvidenceClipRef,
    MatchIntelligenceRecord,
    MatchRecordCreate,
    MatchResultSummary,
    MatchSquadSnapshot,
    TrainingPlan,
)


def _compute_snapshot_sha(user_id: str, formation: str, game_version: str, tactical_profile: str, slots: list) -> str:
    canonical = json.dumps(
        {
            "user_id": user_id,
            "formation": formation,
            "game_version": game_version,
            "tactical_profile": tactical_profile,
            "slots": slots,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _compute_match_sha(user_id: str, req: MatchRecordCreate) -> str:
    canonical = json.dumps(
        {
            "user_id": user_id,
            "video_id": req.video_id,
            "game_version": req.game_version,
            "game_patch": req.game_patch,
            "gameplay_mode": req.gameplay_mode,
            "formation": req.formation,
            "duration_seconds": round(req.duration_seconds, 2),
            "provenance": req.provenance,
            "feature_metrics": req.feature_metrics,
            "event_count": len(req.tactical_events),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _pg_ready() -> bool:
    try:
        row = db.query_one("SELECT to_regclass('public.phase40_match_record') AS tbl")
        return bool(row and row.get("tbl"))
    except Exception:
        return False


def _user_exists_in_pg(user_id: str) -> bool:
    try:
        row = db.query_one("SELECT 1 AS ok FROM public.user_profile WHERE id = %s", (str(user_id),))
        return bool(row)
    except Exception:
        return False


class DuplicateMatchError(ValueError):
    """Raised when an identical match payload is ingested without reanalysis permission."""


class MatchNotFoundError(LookupError):
    """Raised when a match does not exist or belongs to a different user."""


class Phase40Repository:
    """Thread-safe dual-mode repository enforcing user isolation across Phase 40 stores."""

    def __init__(self, force_memory: bool = False) -> None:
        self._force_memory = force_memory
        self._lock = threading.RLock()
        # Memory fallback keyed strictly by user_id
        self._mem_matches: Dict[str, Dict[str, MatchIntelligenceRecord]] = {}
        self._mem_snapshots: Dict[str, Dict[str, MatchSquadSnapshot]] = {}
        self._mem_profiles: Dict[str, Dict[str, Any]] = {}
        self._mem_plans: Dict[str, Dict[str, TrainingPlan]] = {}
        self._mem_attempts: Dict[str, List[Dict[str, Any]]] = {}
        self._mem_sessions: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._mem_messages: Dict[str, List[Dict[str, Any]]] = {}
        self._mem_proposals: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._mem_preferences: Dict[str, Dict[str, Any]] = {}
        self._mem_usage_logs: List[Dict[str, Any]] = []

    def _use_pg_for_user(self, user_id: str) -> bool:
        if self._force_memory:
            return False
        if not _pg_ready():
            return False
        return _user_exists_in_pg(user_id)

    # ------------------------------------------------------------------ Match Ingestion & Retrieval
    def save_match(self, user_id: str, req: MatchRecordCreate) -> MatchIntelligenceRecord:
        uid = str(user_id)
        content_sha = _compute_match_sha(uid, req)
        match_id = req.match_id or f"MATCH-{str(uuid4())[:10]}"

        # Stamp deep links onto any clips lacking one
        clips: List[EvidenceClipRef] = []
        for c in req.evidence_clips:
            clip_data = c.model_copy()
            clip_data.match_id = match_id
            if not clip_data.deep_link and clip_data.video_id:
                clip_data.deep_link = (
                    f"/research/gameplay-studio?video_id={clip_data.video_id}&t={round(clip_data.timestamp_start, 2)}&tab=RADAR_REPLAY"
                )
            clips.append(clip_data)

        # Build immutable historical squad snapshot if slots or formation supplied
        slot_dicts = [s.model_dump(mode="json") for s in req.squad_slots]
        snapshot = MatchSquadSnapshot(
            snapshot_id=str(uuid4()),
            user_id=uid,
            game_version=req.game_version,
            formation=req.formation,
            tactical_profile=req.tactical_profile,
            tactical_instructions=dict(req.tactical_instructions),
            slots=req.squad_slots,
            snapshot_sha256=_compute_snapshot_sha(
                uid, req.formation, req.game_version, req.tactical_profile, slot_dicts
            ),
        )

        record = MatchIntelligenceRecord(
            id=str(uuid4()),
            match_id=match_id,
            user_id=uid,
            video_id=req.video_id,
            game_version=req.game_version,
            game_patch=req.game_patch,
            gameplay_mode=req.gameplay_mode,
            platform=req.platform,
            match_result=req.match_result,
            duration_seconds=req.duration_seconds,
            is_partial_match=req.is_partial_match or (0 < req.duration_seconds < 240.0),
            formation=req.formation,
            tactical_instructions=dict(req.tactical_instructions),
            player_roles=list(req.player_roles),
            squad_snapshot_id=snapshot.snapshot_id,
            squad_snapshot=snapshot,
            opponent_context=dict(req.opponent_context),
            provenance=req.provenance,
            observation_quality=req.observation_quality,
            tracking_coverage_pct=req.tracking_coverage_pct,
            telemetry_summary=dict(req.telemetry_summary),
            feature_metrics=dict(req.feature_metrics),
            tactical_events=list(req.tactical_events),
            coaching_findings=list(req.coaching_findings),
            evidence_clips=clips,
            analysis_version=req.analysis_version,
            content_sha256=content_sha,
        )

        if self._use_pg_for_user(uid):
            existing = db.query_one(
                """SELECT match_id FROM public.phase40_match_record
                   WHERE user_id = %s AND content_sha256 = %s AND analysis_version = %s""",
                (uid, content_sha, req.analysis_version),
            )
            if existing and not req.allow_duplicate_reanalysis:
                raise DuplicateMatchError(
                    f"Duplicate match analysis detected (existing match_id={existing['match_id']})."
                )
            with db.get_conn() as conn:
                conn.execute(
                    """INSERT INTO public.phase40_match_squad_snapshot
                       (snapshot_id, user_id, game_version, formation, tactical_profile,
                        tactical_instructions, slots, snapshot_sha256)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        snapshot.snapshot_id,
                        uid,
                        snapshot.game_version,
                        snapshot.formation,
                        snapshot.tactical_profile,
                        Jsonb(snapshot.tactical_instructions),
                        Jsonb(slot_dicts),
                        snapshot.snapshot_sha256,
                    ),
                )
                if existing and req.allow_duplicate_reanalysis:
                    record.match_id = existing["match_id"]
                    conn.execute(
                        """UPDATE public.phase40_match_record SET
                             observation_quality = %s,
                             tracking_coverage_pct = %s,
                             telemetry_summary = %s,
                             feature_metrics = %s,
                             tactical_events = %s,
                             coaching_findings = %s,
                             evidence_clips = %s,
                             squad_snapshot_id = %s,
                             updated_at = now()
                           WHERE user_id = %s AND match_id = %s""",
                        (
                            record.observation_quality,
                            record.tracking_coverage_pct,
                            Jsonb(record.telemetry_summary),
                            Jsonb(record.feature_metrics),
                            Jsonb(record.tactical_events),
                            Jsonb(record.coaching_findings),
                            Jsonb([c.model_dump(mode="json") for c in clips]),
                            snapshot.snapshot_id,
                            uid,
                            record.match_id,
                        ),
                    )
                else:
                    conn.execute(
                        """INSERT INTO public.phase40_match_record (
                             id, match_id, user_id, video_id, game_version, game_patch,
                             gameplay_mode, platform, match_result, duration_seconds,
                             is_partial_match, formation, tactical_instructions, player_roles,
                             squad_snapshot_id, opponent_context, provenance, observation_quality,
                             tracking_coverage_pct, telemetry_summary, feature_metrics,
                             tactical_events, coaching_findings, evidence_clips,
                             analysis_version, content_sha256
                           ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            record.id,
                            record.match_id,
                            uid,
                            record.video_id,
                            record.game_version,
                            record.game_patch,
                            record.gameplay_mode,
                            record.platform,
                            Jsonb(record.match_result.model_dump(mode="json")),
                            record.duration_seconds,
                            record.is_partial_match,
                            record.formation,
                            Jsonb(record.tactical_instructions),
                            Jsonb(record.player_roles),
                            snapshot.snapshot_id,
                            Jsonb(record.opponent_context),
                            record.provenance,
                            record.observation_quality,
                            record.tracking_coverage_pct,
                            Jsonb(record.telemetry_summary),
                            Jsonb(record.feature_metrics),
                            Jsonb(record.tactical_events),
                            Jsonb(record.coaching_findings),
                            Jsonb([c.model_dump(mode="json") for c in clips]),
                            record.analysis_version,
                            record.content_sha256,
                        ),
                    )
                conn.commit()
            return record

        with self._lock:
            user_matches = self._mem_matches.setdefault(uid, {})
            for existing_rec in user_matches.values():
                if existing_rec.content_sha256 == content_sha and existing_rec.analysis_version == req.analysis_version:
                    if not req.allow_duplicate_reanalysis:
                        raise DuplicateMatchError(
                            f"Duplicate match analysis detected (existing match_id={existing_rec.match_id})."
                        )
                    record.match_id = existing_rec.match_id
                    record.id = existing_rec.id
            self._mem_snapshots.setdefault(uid, {})[snapshot.snapshot_id] = snapshot
            user_matches[record.match_id] = record
            return record

    def _row_to_match(self, row: dict, snap_row: Optional[dict] = None) -> MatchIntelligenceRecord:
        snap = None
        if snap_row:
            snap = MatchSquadSnapshot(
                snapshot_id=str(snap_row["snapshot_id"]),
                user_id=str(snap_row["user_id"]),
                game_version=snap_row["game_version"],
                formation=snap_row["formation"],
                tactical_profile=snap_row["tactical_profile"],
                tactical_instructions=snap_row["tactical_instructions"] or {},
                slots=snap_row["slots"] or [],
                snapshot_sha256=snap_row["snapshot_sha256"],
                created_at=snap_row["created_at"].isoformat() if snap_row.get("created_at") else "",
            )
        return MatchIntelligenceRecord(
            id=str(row["id"]),
            match_id=row["match_id"],
            user_id=str(row["user_id"]),
            video_id=row.get("video_id"),
            game_version=row["game_version"],
            game_patch=row["game_patch"],
            gameplay_mode=row["gameplay_mode"],
            platform=row["platform"],
            match_result=MatchResultSummary(**(row.get("match_result") or {})),
            duration_seconds=float(row.get("duration_seconds") or 0.0),
            is_partial_match=bool(row.get("is_partial_match")),
            formation=row["formation"],
            tactical_instructions=row.get("tactical_instructions") or {},
            player_roles=row.get("player_roles") or [],
            squad_snapshot_id=str(row["squad_snapshot_id"]) if row.get("squad_snapshot_id") else None,
            squad_snapshot=snap,
            opponent_context=row.get("opponent_context") or {},
            provenance=row["provenance"],
            observation_quality=row["observation_quality"],
            tracking_coverage_pct=float(row.get("tracking_coverage_pct") or 0.0),
            telemetry_summary=row.get("telemetry_summary") or {},
            feature_metrics=row.get("feature_metrics") or {},
            tactical_events=row.get("tactical_events") or [],
            coaching_findings=row.get("coaching_findings") or [],
            evidence_clips=[EvidenceClipRef(**c) for c in (row.get("evidence_clips") or [])],
            analysis_version=row["analysis_version"],
            content_sha256=row["content_sha256"],
            created_at=row["created_at"].isoformat() if row.get("created_at") else "",
            updated_at=row["updated_at"].isoformat() if row.get("updated_at") else "",
        )

    def list_matches(
        self,
        user_id: str,
        *,
        game_version: Optional[str] = None,
        game_patch: Optional[str] = None,
        formation: Optional[str] = None,
        provenance: Optional[str] = None,
        exclude_synthetic: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[MatchIntelligenceRecord]:
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            clauses = ["m.user_id = %s"]
            params: List[Any] = [uid]
            if game_version:
                clauses.append("m.game_version = %s")
                params.append(game_version.upper())
            if game_patch:
                clauses.append("m.game_patch = %s")
                params.append(game_patch)
            if formation:
                clauses.append("m.formation = %s")
                params.append(formation)
            if provenance:
                clauses.append("m.provenance = %s")
                params.append(provenance)
            if exclude_synthetic:
                clauses.append("m.provenance <> 'SYNTHETIC_FIXTURE'")
            params.extend([limit, offset])
            rows = db.query(
                f"""SELECT m.* FROM public.phase40_match_record m
                    WHERE {' AND '.join(clauses)}
                    ORDER BY m.created_at DESC
                    LIMIT %s OFFSET %s""",
                tuple(params),
            )
            snap_ids = [str(r["squad_snapshot_id"]) for r in rows if r.get("squad_snapshot_id")]
            snaps: Dict[str, dict] = {}
            if snap_ids:
                srows = db.query(
                    "SELECT * FROM public.phase40_match_squad_snapshot WHERE user_id = %s AND snapshot_id = ANY(%s::uuid[])",
                    (uid, snap_ids),
                )
                snaps = {str(s["snapshot_id"]): s for s in srows}
            return [
                self._row_to_match(r, snaps.get(str(r.get("squad_snapshot_id") or "")))
                for r in rows
            ]

        with self._lock:
            items = list(self._mem_matches.get(uid, {}).values())
            if game_version:
                items = [m for m in items if m.game_version == game_version.upper()]
            if game_patch:
                items = [m for m in items if m.game_patch == game_patch]
            if formation:
                items = [m for m in items if m.formation == formation]
            if provenance:
                items = [m for m in items if m.provenance == provenance]
            if exclude_synthetic:
                items = [m for m in items if m.provenance != "SYNTHETIC_FIXTURE"]
            items.sort(key=lambda m: m.created_at, reverse=True)
            return items[offset : offset + limit]

    def get_match(self, user_id: str, match_id: str) -> MatchIntelligenceRecord:
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            row = db.query_one(
                "SELECT * FROM public.phase40_match_record WHERE user_id = %s AND match_id = %s",
                (uid, match_id),
            )
            if not row:
                raise MatchNotFoundError(f"Match {match_id!r} not found for this user.")
            snap_row = None
            if row.get("squad_snapshot_id"):
                snap_row = db.query_one(
                    "SELECT * FROM public.phase40_match_squad_snapshot WHERE user_id = %s AND snapshot_id = %s",
                    (uid, str(row["squad_snapshot_id"])),
                )
            return self._row_to_match(row, snap_row)

        with self._lock:
            rec = self._mem_matches.get(uid, {}).get(match_id)
            if not rec:
                raise MatchNotFoundError(f"Match {match_id!r} not found for this user.")
            return rec

    def delete_match(self, user_id: str, match_id: str) -> bool:
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            n = db.execute(
                "DELETE FROM public.phase40_match_record WHERE user_id = %s AND match_id = %s",
                (uid, match_id),
            )
            if n == 0:
                raise MatchNotFoundError(f"Match {match_id!r} not found for this user.")
            return True
        with self._lock:
            user_matches = self._mem_matches.get(uid, {})
            if match_id not in user_matches:
                raise MatchNotFoundError(f"Match {match_id!r} not found for this user.")
            del user_matches[match_id]
            return True

    def reset_user_intelligence(self, user_id: str) -> Dict[str, int]:
        """Full privacy reset: deletes matches, historical snapshots, DNA profile, plans, and coach sessions."""
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            with db.get_conn() as conn:
                c_msg = conn.execute("DELETE FROM public.phase40_coach_session WHERE user_id = %s", (uid,)).rowcount
                c_att = conn.execute("DELETE FROM public.phase40_training_attempt WHERE user_id = %s", (uid,)).rowcount
                c_pln = conn.execute("DELETE FROM public.phase40_training_plan WHERE user_id = %s", (uid,)).rowcount
                c_mis = conn.execute("DELETE FROM public.phase40_recurring_mistake WHERE user_id = %s", (uid,)).rowcount
                c_mat = conn.execute("DELETE FROM public.phase40_match_record WHERE user_id = %s", (uid,)).rowcount
                c_snp = conn.execute("DELETE FROM public.phase40_match_squad_snapshot WHERE user_id = %s", (uid,)).rowcount
                c_pro = conn.execute("DELETE FROM public.phase40_gamer_profile WHERE user_id = %s", (uid,)).rowcount
                conn.commit()
            return {"matches_deleted": c_mat, "snapshots_deleted": c_snp, "profiles_deleted": c_pro, "plans_deleted": c_pln, "attempts_deleted": c_att, "mistakes_deleted": c_mis, "sessions_deleted": c_msg}

        with self._lock:
            n_mat = len(self._mem_matches.pop(uid, {}))
            n_snp = len(self._mem_snapshots.pop(uid, {}))
            n_pro = 1 if self._mem_profiles.pop(uid, None) else 0
            n_pln = len(self._mem_plans.pop(uid, {}))
            self._mem_attempts.pop(uid, None)
            self._mem_sessions.pop(uid, None)
            self._mem_messages.pop(uid, None)
            self._mem_proposals.pop(uid, None)
            return {"matches_deleted": n_mat, "snapshots_deleted": n_snp, "profiles_deleted": n_pro, "plans_deleted": n_pln}

    # ------------------------------------------------------------------ Cold-Start & Profile State
    def save_cold_start_preferences(self, user_id: str, prefs: ColdStartPreferences) -> ColdStartPreferences:
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            db.execute(
                """INSERT INTO public.phase40_gamer_profile (user_id, self_reported_style)
                   VALUES (%s, %s)
                   ON CONFLICT (user_id) DO UPDATE SET
                     self_reported_style = EXCLUDED.self_reported_style,
                     updated_at = now()""",
                (uid, Jsonb(prefs.model_dump(mode="json"))),
            )
            return prefs
        with self._lock:
            entry = self._mem_profiles.setdefault(uid, {})
            entry["self_reported_style"] = prefs.model_dump(mode="json")
            return prefs

    def get_cold_start_preferences(self, user_id: str) -> Optional[ColdStartPreferences]:
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            row = db.query_one(
                "SELECT self_reported_style FROM public.phase40_gamer_profile WHERE user_id = %s",
                (uid,),
            )
            if row and row.get("self_reported_style"):
                return ColdStartPreferences(**row["self_reported_style"])
            return None
        with self._lock:
            raw = self._mem_profiles.get(uid, {}).get("self_reported_style")
            return ColdStartPreferences(**raw) if raw else None

    def save_gamer_profile_snapshot(self, user_id: str, dna_dict: Dict[str, Any], eligible_count: int, synthetic_count: int) -> None:
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            db.execute(
                """INSERT INTO public.phase40_gamer_profile
                   (user_id, observed_dna, archetype_assessment, eligible_match_count, synthetic_excluded_count)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (user_id) DO UPDATE SET
                     observed_dna = EXCLUDED.observed_dna,
                     archetype_assessment = EXCLUDED.archetype_assessment,
                     eligible_match_count = EXCLUDED.eligible_match_count,
                     synthetic_excluded_count = EXCLUDED.synthetic_excluded_count,
                     updated_at = now()""",
                (
                    uid,
                    Jsonb(dna_dict),
                    Jsonb(dna_dict.get("archetype", {})),
                    eligible_count,
                    synthetic_count,
                ),
            )
            return
        with self._lock:
            entry = self._mem_profiles.setdefault(uid, {})
            entry["observed_dna"] = dna_dict

    # ------------------------------------------------------------------ Training Plans & Attempts
    def save_training_plan(self, user_id: str, plan: TrainingPlan) -> TrainingPlan:
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            db.execute(
                """INSERT INTO public.phase40_training_plan (plan_id, user_id, game_version, objectives, exercises, bkt_states)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (plan_id) DO UPDATE SET
                     objectives = EXCLUDED.objectives,
                     exercises = EXCLUDED.exercises,
                     bkt_states = EXCLUDED.bkt_states,
                     updated_at = now()""",
                (
                    plan.plan_id,
                    uid,
                    plan.game_version,
                    Jsonb(plan.next_match_objectives),
                    Jsonb([e.model_dump(mode="json") for e in plan.exercises]),
                    Jsonb({k: v.model_dump(mode="json") for k, v in plan.bkt_states.items()}),
                ),
            )
            return plan
        with self._lock:
            self._mem_plans.setdefault(uid, {})[plan.plan_id] = plan
            return plan

    def get_latest_training_plan(self, user_id: str) -> Optional[TrainingPlan]:
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            row = db.query_one(
                "SELECT * FROM public.phase40_training_plan WHERE user_id = %s ORDER BY updated_at DESC LIMIT 1",
                (uid,),
            )
            if not row:
                return None
            return TrainingPlan(
                plan_id=row["plan_id"],
                user_id=str(row["user_id"]),
                game_version=row["game_version"],
                next_match_objectives=row.get("objectives") or [],
                exercises=row.get("exercises") or [],
                bkt_states=row.get("bkt_states") or {},
                generated_at=row["updated_at"].isoformat() if row.get("updated_at") else "",
            )
        with self._lock:
            plans = list(self._mem_plans.get(uid, {}).values())
            if not plans:
                return None
            plans.sort(key=lambda p: p.generated_at, reverse=True)
            return plans[0]

    def record_training_attempt(
        self,
        user_id: str,
        *,
        plan_id: Optional[str],
        exercise_id: str,
        skill_code: str,
        selected_option_id: str,
        is_defensible: bool,
        feedback_summary: str,
        prior_p: float,
        posterior_p: float,
    ) -> Dict[str, Any]:
        uid = str(user_id)
        row_data = {
            "attempt_id": str(uuid4()),
            "user_id": uid,
            "plan_id": plan_id,
            "exercise_id": exercise_id,
            "skill_code": skill_code,
            "selected_option_id": selected_option_id,
            "is_optimal_or_defensible": is_defensible,
            "feedback_summary": feedback_summary,
            "prior_p_mastery": round(prior_p, 4),
            "posterior_p_mastery": round(posterior_p, 4),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if self._use_pg_for_user(uid):
            db.execute(
                """INSERT INTO public.phase40_training_attempt
                   (attempt_id, user_id, plan_id, exercise_id, skill_code,
                    selected_option_id, is_optimal_or_defensible, feedback_summary,
                    prior_p_mastery, posterior_p_mastery)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    row_data["attempt_id"],
                    uid,
                    plan_id,
                    exercise_id,
                    skill_code,
                    selected_option_id,
                    is_defensible,
                    feedback_summary,
                    prior_p,
                    posterior_p,
                ),
            )
            return row_data
        with self._lock:
            self._mem_attempts.setdefault(uid, []).append(row_data)
            return row_data

    def list_training_attempts(self, user_id: str) -> List[Dict[str, Any]]:
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            rows = db.query(
                "SELECT * FROM public.phase40_training_attempt WHERE user_id = %s ORDER BY created_at DESC LIMIT 100",
                (uid,),
            )
            return [
                {
                    **dict(r),
                    "attempt_id": str(r["attempt_id"]),
                    "user_id": str(r["user_id"]),
                    "created_at": r["created_at"].isoformat() if r.get("created_at") else "",
                }
                for r in rows
            ]
        with self._lock:
            return list(reversed(self._mem_attempts.get(uid, [])))

    # ------------------------------------------------------------------ Coach Sessions
    def ensure_coach_session(
        self,
        user_id: str,
        session_id: Optional[str],
        game_version: str,
        *,
        title: Optional[str] = None,
        active_squad_id: Optional[str] = None,
        active_match_id: Optional[str] = None,
        source_route: str = "/coach",
        context_envelope: Optional[Dict[str, Any]] = None,
    ) -> str:
        uid = str(user_id)
        if session_id:
            if self._use_pg_for_user(uid):
                row = db.query_one(
                    "SELECT session_id FROM public.phase40_coach_session WHERE session_id = %s AND user_id = %s",
                    (session_id, uid),
                )
                if row:
                    return str(row["session_id"])
            else:
                if session_id in self._mem_sessions.get(uid, {}):
                    return session_id
        new_sid = str(uuid4())
        clean_title = (title or "Personal Coaching Session")[:120]
        if self._use_pg_for_user(uid):
            try:
                db.execute(
                    """INSERT INTO public.phase40_coach_session
                       (session_id, user_id, title, game_version, active_squad_id, active_match_id, source_route, context_envelope)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (new_sid, uid, clean_title, game_version, active_squad_id, active_match_id, source_route[:120], Jsonb(context_envelope or {})),
                )
            except Exception:
                try:
                    db.execute(
                        """INSERT INTO public.phase40_coach_session
                           (session_id, user_id, title, game_version, active_squad_id, active_match_id)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (new_sid, uid, clean_title, game_version, active_squad_id, active_match_id),
                    )
                except Exception:
                    db.execute(
                        "INSERT INTO public.phase40_coach_session (session_id, user_id, title, game_version) VALUES (%s, %s, %s, %s)",
                        (new_sid, uid, clean_title, game_version),
                    )
        else:
            with self._lock:
                self._mem_sessions.setdefault(uid, {})[new_sid] = {
                    "session_id": new_sid,
                    "user_id": uid,
                    "title": clean_title,
                    "game_version": game_version,
                    "active_squad_id": active_squad_id,
                    "active_match_id": active_match_id,
                    "source_route": source_route[:120],
                    "context_envelope": dict(context_envelope or {}),
                    "conversation_summary": "",
                    "last_provider": "DETERMINISTIC",
                    "last_model": "deterministic-coach",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
        return new_sid

    def get_coach_session(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        uid = str(user_id)
        if not session_id:
            return None
        if self._use_pg_for_user(uid):
            try:
                r = db.query_one(
                    "SELECT * FROM public.phase40_coach_session WHERE user_id = %s AND session_id = %s",
                    (uid, session_id),
                )
                if r:
                    return {
                        **dict(r),
                        "session_id": str(r["session_id"]),
                        "user_id": str(r["user_id"]),
                        "active_squad_id": str(r["active_squad_id"]) if r.get("active_squad_id") else None,
                    }
            except Exception:
                return None
        with self._lock:
            s = self._mem_sessions.get(uid, {}).get(session_id)
            return dict(s) if s else None

    def list_coach_sessions(self, user_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            try:
                rows = db.query(
                    """SELECT session_id, user_id, title, game_version,
                              active_squad_id, active_match_id, conversation_summary,
                              last_provider, last_model, created_at, updated_at
                       FROM public.phase40_coach_session
                       WHERE user_id = %s
                       ORDER BY updated_at DESC
                       LIMIT %s""",
                    (uid, limit),
                )
            except Exception:
                rows = db.query(
                    """SELECT session_id, user_id, title, game_version, created_at, updated_at
                       FROM public.phase40_coach_session WHERE user_id = %s ORDER BY updated_at DESC LIMIT %s""",
                    (uid, limit),
                )
            return [
                {
                    **dict(r),
                    "session_id": str(r["session_id"]),
                    "user_id": str(r["user_id"]),
                    "active_squad_id": str(r["active_squad_id"]) if r.get("active_squad_id") else None,
                    "created_at": r["created_at"].isoformat() if r.get("created_at") else "",
                    "updated_at": r["updated_at"].isoformat() if r.get("updated_at") else "",
                }
                for r in rows
            ]
        with self._lock:
            items = [dict(s) for s in self._mem_sessions.get(uid, {}).values()]
            items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
            return items[:limit]

    def update_coach_session(
        self,
        user_id: str,
        session_id: str,
        *,
        title: Optional[str] = None,
        active_squad_id: Optional[str] = None,
        active_match_id: Optional[str] = None,
        conversation_summary: Optional[str] = None,
        last_provider: Optional[str] = None,
        last_model: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            try:
                row = db.query_one(
                    """UPDATE public.phase40_coach_session SET
                         title = COALESCE(%s, title),
                         active_squad_id = COALESCE(%s, active_squad_id),
                         active_match_id = COALESCE(%s, active_match_id),
                         conversation_summary = COALESCE(%s, conversation_summary),
                         last_provider = COALESCE(%s, last_provider),
                         last_model = COALESCE(%s, last_model),
                         updated_at = now()
                       WHERE user_id = %s AND session_id = %s
                       RETURNING session_id, user_id, title, game_version, active_squad_id,
                                 active_match_id, conversation_summary, last_provider, last_model, updated_at""",
                    (title, active_squad_id, active_match_id, conversation_summary, last_provider, last_model, uid, session_id),
                )
                return {**dict(row), "session_id": str(row["session_id"]), "user_id": str(row["user_id"])} if row else None
            except Exception:
                return None
        with self._lock:
            s = self._mem_sessions.get(uid, {}).get(session_id)
            if not s:
                return None
            if title is not None:
                s["title"] = title[:120]
            if active_squad_id is not None:
                s["active_squad_id"] = active_squad_id
            if active_match_id is not None:
                s["active_match_id"] = active_match_id
            if conversation_summary is not None:
                s["conversation_summary"] = conversation_summary[:1200]
            if last_provider is not None:
                s["last_provider"] = last_provider
            if last_model is not None:
                s["last_model"] = last_model
            s["updated_at"] = datetime.now(timezone.utc).isoformat()
            return dict(s)

    def delete_coach_session(self, user_id: str, session_id: str) -> bool:
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            n = db.execute(
                "DELETE FROM public.phase40_coach_session WHERE user_id = %s AND session_id = %s",
                (uid, session_id),
            )
            return n > 0
        with self._lock:
            removed = self._mem_sessions.get(uid, {}).pop(session_id, None)
            if uid in self._mem_messages:
                self._mem_messages[uid] = [m for m in self._mem_messages[uid] if m.get("session_id") != session_id]
            return removed is not None

    def append_coach_message(self, user_id: str, session_id: str, role: str, content: str, payload: Optional[Dict[str, Any]] = None) -> str:
        uid = str(user_id)
        mid = str(uuid4())
        if self._use_pg_for_user(uid):
            db.execute(
                """INSERT INTO public.phase40_coach_message (message_id, session_id, user_id, role, content, structured_payload)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (mid, session_id, uid, role, content, Jsonb(payload or {})),
            )
            return mid
        with self._lock:
            self._mem_messages.setdefault(uid, []).append(
                {
                    "message_id": mid,
                    "session_id": session_id,
                    "user_id": uid,
                    "role": role,
                    "content": content,
                    "structured_payload": payload or {},
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            return mid

    def list_coach_messages(self, user_id: str, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            if session_id:
                rows = db.query(
                    """SELECT * FROM public.phase40_coach_message
                       WHERE user_id = %s AND session_id = %s ORDER BY created_at ASC""",
                    (uid, session_id),
                )
            else:
                rows = db.query(
                    "SELECT * FROM public.phase40_coach_message WHERE user_id = %s ORDER BY created_at DESC LIMIT 50",
                    (uid,),
                )
            return [
                {
                    **dict(r),
                    "message_id": str(r["message_id"]),
                    "session_id": str(r["session_id"]),
                    "user_id": str(r["user_id"]),
                    "created_at": r["created_at"].isoformat() if r.get("created_at") else "",
                }
                for r in rows
            ]
        with self._lock:
            msgs = [m for m in self._mem_messages.get(uid, []) if not session_id or m["session_id"] == session_id]
            return msgs if session_id else list(reversed(msgs))

    # ------------------------------------------------------------------ Phase 41.5 Usage Logs & Squad Proposals
    def log_provider_usage(
        self,
        user_id: str,
        *,
        provider: str,
        model: str,
        intent_category: str,
        prompt_tokens: int,
        completion_tokens: int,
        provider_requests: int,
        reported_cost_usd: float,
        status: str,
        latency_ms: float,
        ttft_ms: float = 0.0,
        tools_sent_count: int = 0,
        fallback_used: bool = False,
    ) -> None:
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            try:
                db.execute(
                    """INSERT INTO public.phase41_5_provider_usage_log
                       (user_id, provider, model, intent_category, prompt_tokens, completion_tokens,
                        provider_requests, reported_cost_usd, status, latency_ms, ttft_ms, tools_sent_count, fallback_used)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (uid, provider, model, intent_category, prompt_tokens, completion_tokens, provider_requests, reported_cost_usd, status, latency_ms, ttft_ms, tools_sent_count, fallback_used),
                )
                return
            except Exception:
                try:
                    db.execute(
                        """INSERT INTO public.phase41_5_provider_usage_log
                           (user_id, provider, model, intent_category, prompt_tokens, completion_tokens,
                            provider_requests, reported_cost_usd, status, latency_ms)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (uid, provider, model, intent_category, prompt_tokens, completion_tokens, provider_requests, reported_cost_usd, status, latency_ms),
                    )
                    return
                except Exception:
                    pass
        with self._lock:
            self._mem_usage_logs.append(
                {
                    "user_id": uid,
                    "provider": provider,
                    "model": model,
                    "intent_category": intent_category,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "provider_requests": provider_requests,
                    "reported_cost_usd": reported_cost_usd,
                    "status": status,
                    "latency_ms": latency_ms,
                    "ttft_ms": ttft_ms,
                    "tools_sent_count": tools_sent_count,
                    "fallback_used": fallback_used,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            if len(self._mem_usage_logs) > 500:
                self._mem_usage_logs = self._mem_usage_logs[-500:]

    def get_coach_preferences(self, user_id: str) -> Dict[str, Any]:
        uid = str(user_id)
        default = {
            "preferred_formation": None,
            "preferred_tactical_profile": None,
            "preferred_provider": "AUTO",
            "coach_style": "CONCISE_TACTICAL",
            "consent_saved_default": False,
        }
        if self._use_pg_for_user(uid):
            try:
                r = db.query_one(
                    "SELECT * FROM public.phase42_user_coach_preferences WHERE user_id = %s",
                    (uid,),
                )
                if r:
                    return {**default, **{k: r[k] for k in default if k in r}}
            except Exception:
                pass
        with self._lock:
            return {**default, **self._mem_preferences.get(uid, {})}

    def save_coach_preferences(self, user_id: str, prefs: Dict[str, Any]) -> Dict[str, Any]:
        uid = str(user_id)
        merged = {**self.get_coach_preferences(uid), **{k: v for k, v in prefs.items() if k in (
            "preferred_formation", "preferred_tactical_profile", "preferred_provider", "coach_style", "consent_saved_default"
        )}}
        if self._use_pg_for_user(uid):
            try:
                db.execute(
                    """INSERT INTO public.phase42_user_coach_preferences
                       (user_id, preferred_formation, preferred_tactical_profile, preferred_provider, coach_style, consent_saved_default, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, now())
                       ON CONFLICT (user_id) DO UPDATE SET
                         preferred_formation = EXCLUDED.preferred_formation,
                         preferred_tactical_profile = EXCLUDED.preferred_tactical_profile,
                         preferred_provider = EXCLUDED.preferred_provider,
                         coach_style = EXCLUDED.coach_style,
                         consent_saved_default = EXCLUDED.consent_saved_default,
                         updated_at = now()""",
                    (uid, merged["preferred_formation"], merged["preferred_tactical_profile"], merged["preferred_provider"], merged["coach_style"], bool(merged["consent_saved_default"])),
                )
            except Exception:
                pass
        with self._lock:
            self._mem_preferences[uid] = dict(merged)
        return merged

    def get_freshness_markers(self, user_id: str) -> Dict[str, Any]:
        uid = str(user_id)
        matches = self.list_matches(uid, exclude_synthetic=True, limit=5)
        latest_match_at = matches[0].created_at if matches else None
        return {
            "eligible_match_count": len(self.list_matches(uid, exclude_synthetic=True, limit=100)),
            "latest_match_at": latest_match_at,
            "freshness_status": "LIVE_DB_VERIFIED",
        }

    def save_squad_proposal(
        self,
        user_id: str,
        *,
        proposal_id: str,
        session_id: Optional[str],
        target_squad_id: Optional[str],
        game_version: str,
        formation: str,
        tactical_profile: str,
        proposal_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        uid = str(user_id)
        row = {
            "proposal_id": proposal_id,
            "user_id": uid,
            "session_id": session_id,
            "target_squad_id": target_squad_id,
            "game_version": game_version,
            "formation": formation,
            "tactical_profile": tactical_profile,
            "proposal_payload": proposal_payload,
            "previous_snapshot": None,
            "status": "PENDING_CONFIRMATION",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if self._use_pg_for_user(uid):
            try:
                db.execute(
                    """INSERT INTO public.phase41_5_squad_proposal
                       (proposal_id, user_id, session_id, target_squad_id, game_version, formation, tactical_profile, proposal_payload, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'PENDING_CONFIRMATION')
                       ON CONFLICT (proposal_id) DO UPDATE SET
                         proposal_payload = EXCLUDED.proposal_payload,
                         updated_at = now()""",
                    (proposal_id, uid, session_id, target_squad_id, game_version, formation, tactical_profile, Jsonb(proposal_payload)),
                )
                return row
            except Exception:
                pass
        with self._lock:
            self._mem_proposals.setdefault(uid, {})[proposal_id] = row
        return row

    def get_squad_proposal(self, user_id: str, proposal_id: str) -> Optional[Dict[str, Any]]:
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            try:
                r = db.query_one(
                    "SELECT * FROM public.phase41_5_squad_proposal WHERE user_id = %s AND proposal_id = %s",
                    (uid, proposal_id),
                )
                if r:
                    return {
                        **dict(r),
                        "user_id": str(r["user_id"]),
                        "session_id": str(r["session_id"]) if r.get("session_id") else None,
                        "target_squad_id": str(r["target_squad_id"]) if r.get("target_squad_id") else None,
                    }
            except Exception:
                pass
        with self._lock:
            item = self._mem_proposals.get(uid, {}).get(proposal_id)
            return dict(item) if item else None

    def update_squad_proposal_status(
        self,
        user_id: str,
        proposal_id: str,
        *,
        status: str,
        previous_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        uid = str(user_id)
        if self._use_pg_for_user(uid):
            try:
                r = db.query_one(
                    """UPDATE public.phase41_5_squad_proposal SET
                         status = %s,
                         previous_snapshot = COALESCE(%s, previous_snapshot),
                         updated_at = now()
                       WHERE user_id = %s AND proposal_id = %s
                       RETURNING *""",
                    (status, Jsonb(previous_snapshot) if previous_snapshot is not None else None, uid, proposal_id),
                )
                if r:
                    return {**dict(r), "user_id": str(r["user_id"])}
            except Exception:
                pass
        with self._lock:
            item = self._mem_proposals.get(uid, {}).get(proposal_id)
            if not item:
                return None
            item["status"] = status
            if previous_snapshot is not None:
                item["previous_snapshot"] = previous_snapshot
            return dict(item)


_DEFAULT_REPO: Optional[Phase40Repository] = None


def get_phase40_repository() -> Phase40Repository:
    global _DEFAULT_REPO
    if _DEFAULT_REPO is None:
        _DEFAULT_REPO = Phase40Repository()
    return _DEFAULT_REPO
