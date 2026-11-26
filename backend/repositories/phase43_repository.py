"""Phase 43 Repository: User-Scoped Persistence for Tactical Snapshots, Fingerprints, Experiments & Personal Meta.

Supports seamless PostgreSQL persistence (`db.migrations/019_phase43_tactical_experimentation.sql`)
with automatic test-safe in-memory storage when running isolated unit tests without DB rows.
All queries strictly enforce `user_id` ownership (zero cross-user IDOR leakage).
"""
from __future__ import annotations

import threading
import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from psycopg.types.json import Jsonb

from backend.core import db
from backend.domain.phase43_models import (
    ExperimentArm,
    ExperimentMatchLinkCreate,
    ExperimentStatisticalAnalysis,
    ExperimentStatus,
    ExperimentType,
    FingerprintMetricDetail,
    MidMatchTacticalChange,
    PersonalMetaProfile,
    RecommendationFeedbackRecord,
    TacticalConfigurationSnapshot,
    TacticalExperimentRecord,
    TacticalFingerprint,
    TacticalSlotConfig,
)


def _pg_phase43_ready() -> bool:
    try:
        row = db.query_one("SELECT to_regclass('public.phase43_tactical_snapshot') AS tbl")
        return bool(row and row.get("tbl"))
    except Exception:
        return False


def _pg_phase43_v2_ready() -> bool:
    try:
        row = db.query_one("SELECT to_regclass('public.phase43_recommendation_feedback') AS tbl")
        return bool(row and row.get("tbl"))
    except Exception:
        return False


def _user_in_pg(user_id: str) -> bool:
    try:
        uuid_lib.UUID(str(user_id))
        row = db.query_one("SELECT 1 AS ok FROM public.user_profile WHERE id = %s", (str(user_id),))
        return bool(row)
    except Exception:
        return False


class SnapshotNotFoundError(LookupError):
    pass


class ExperimentNotFoundError(LookupError):
    pass


class Phase43Repository:
    def __init__(self, *, force_memory: bool = False) -> None:
        self._force_memory = force_memory
        self._lock = threading.RLock()
        self._snapshots: Dict[str, Dict[str, TacticalConfigurationSnapshot]] = {}
        self._fingerprints: Dict[str, Dict[str, TacticalFingerprint]] = {}
        self._experiments: Dict[str, Dict[str, TacticalExperimentRecord]] = {}
        self._links: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        self._assignments: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        self._feedback: Dict[str, List[RecommendationFeedbackRecord]] = {}
        self._meta: Dict[str, Dict[str, PersonalMetaProfile]] = {}

    def _use_pg(self, user_id: str) -> bool:
        if self._force_memory:
            return False
        return _pg_phase43_ready() and _user_in_pg(user_id)

    # ------------------------------------------------------------------ Snapshots
    def save_snapshot(self, snap: TacticalConfigurationSnapshot) -> TacticalConfigurationSnapshot:
        uid = str(snap.user_id)
        if self._use_pg(uid):
            if _pg_phase43_v2_ready():
                db.execute(
                    """INSERT INTO public.phase43_tactical_snapshot
                       (snapshot_id, user_id, label, game_version, game_patch, gameplay_mode,
                        source_squad_id, formation, tactical_profile, build_up_style, defensive_approach,
                        line_height, width_setting, tactical_instructions, slots, chemistry_summary,
                        cohesion_summary, partnership_summary, unknown_fields, config_hash,
                        version_number, parent_snapshot_id, is_immutable, mid_match_changes_json, notes)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        snap.snapshot_id,
                        uid,
                        snap.label,
                        snap.game_version,
                        snap.game_patch,
                        snap.gameplay_mode,
                        snap.source_squad_id,
                        snap.formation,
                        snap.tactical_profile,
                        snap.build_up_style,
                        snap.defensive_approach,
                        snap.line_height,
                        snap.width_setting,
                        Jsonb(snap.tactical_instructions),
                        Jsonb([s.model_dump(mode="json") for s in snap.slots]),
                        Jsonb(snap.chemistry_summary) if snap.chemistry_summary is not None else None,
                        Jsonb(snap.cohesion_summary) if snap.cohesion_summary is not None else None,
                        Jsonb(snap.partnership_summary) if snap.partnership_summary is not None else None,
                        Jsonb(snap.unknown_fields),
                        snap.config_hash,
                        snap.version_number,
                        snap.parent_snapshot_id,
                        snap.is_immutable,
                        Jsonb([m.model_dump(mode="json") for m in snap.mid_match_changes]),
                        snap.notes,
                    ),
                )
            else:
                db.execute(
                    """INSERT INTO public.phase43_tactical_snapshot
                       (snapshot_id, user_id, label, game_version, game_patch, gameplay_mode,
                        source_squad_id, formation, tactical_profile, build_up_style, defensive_approach,
                        line_height, width_setting, tactical_instructions, slots, chemistry_summary,
                        cohesion_summary, partnership_summary, unknown_fields, config_hash,
                        version_number, parent_snapshot_id, is_immutable)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        snap.snapshot_id,
                        uid,
                        snap.label,
                        snap.game_version,
                        snap.game_patch,
                        snap.gameplay_mode,
                        snap.source_squad_id,
                        snap.formation,
                        snap.tactical_profile,
                        snap.build_up_style,
                        snap.defensive_approach,
                        snap.line_height,
                        snap.width_setting,
                        Jsonb(snap.tactical_instructions),
                        Jsonb([s.model_dump(mode="json") for s in snap.slots]),
                        Jsonb(snap.chemistry_summary) if snap.chemistry_summary is not None else None,
                        Jsonb(snap.cohesion_summary) if snap.cohesion_summary is not None else None,
                        Jsonb(snap.partnership_summary) if snap.partnership_summary is not None else None,
                        Jsonb(snap.unknown_fields),
                        snap.config_hash,
                        snap.version_number,
                        snap.parent_snapshot_id,
                        snap.is_immutable,
                    ),
                )
            return snap
        with self._lock:
            self._snapshots.setdefault(uid, {})[snap.snapshot_id] = snap
        return snap

    def get_snapshot(self, user_id: str, snapshot_id: str) -> TacticalConfigurationSnapshot:
        uid = str(user_id)
        if self._use_pg(uid):
            row = db.query_one(
                "SELECT * FROM public.phase43_tactical_snapshot WHERE user_id = %s AND snapshot_id = %s",
                (uid, snapshot_id),
            )
            if not row:
                raise SnapshotNotFoundError(f"Tactical snapshot {snapshot_id!r} not found.")
            return self._row_to_snapshot(row)
        with self._lock:
            snap = self._snapshots.get(uid, {}).get(snapshot_id)
            if not snap:
                raise SnapshotNotFoundError(f"Tactical snapshot {snapshot_id!r} not found.")
            return snap

    def list_snapshots(
        self,
        user_id: str,
        *,
        game_version: Optional[str] = None,
        game_patch: Optional[str] = None,
        limit: int = 50,
    ) -> List[TacticalConfigurationSnapshot]:
        uid = str(user_id)
        if self._use_pg(uid):
            sql = "SELECT * FROM public.phase43_tactical_snapshot WHERE user_id = %s"
            params: List[Any] = [uid]
            if game_version:
                sql += " AND game_version = %s"
                params.append(game_version.upper())
            if game_patch:
                sql += " AND game_patch = %s"
                params.append(game_patch)
            sql += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            return [self._row_to_snapshot(r) for r in db.query(sql, tuple(params))]
        with self._lock:
            items = list(self._snapshots.get(uid, {}).values())
            if game_version:
                items = [s for s in items if s.game_version == game_version.upper()]
            if game_patch:
                items = [s for s in items if s.game_patch == game_patch]
            items.sort(key=lambda s: s.created_at, reverse=True)
            return items[:limit]

    @staticmethod
    def _row_to_snapshot(row: Dict[str, Any]) -> TacticalConfigurationSnapshot:
        return TacticalConfigurationSnapshot(
            snapshot_id=str(row["snapshot_id"]),
            user_id=str(row["user_id"]),
            label=str(row.get("label") or ""),
            game_version=row["game_version"],
            game_patch=str(row.get("game_patch") or "PATCH_1.04"),
            gameplay_mode=str(row.get("gameplay_mode") or "COMPETITIVE_RIVALS"),
            source_squad_id=str(row["source_squad_id"]) if row.get("source_squad_id") else None,
            formation=str(row["formation"]),
            tactical_profile=str(row.get("tactical_profile") or "BALANCED"),
            build_up_style=row.get("build_up_style"),
            defensive_approach=row.get("defensive_approach"),
            line_height=row.get("line_height"),
            width_setting=row.get("width_setting"),
            tactical_instructions=dict(row.get("tactical_instructions") or {}),
            mid_match_changes=[MidMatchTacticalChange(**m) for m in (row.get("mid_match_changes_json") or [])],
            notes=str(row.get("notes") or ""),
            slots=[TacticalSlotConfig(**s) for s in (row.get("slots") or [])],
            chemistry_summary=row.get("chemistry_summary"),
            cohesion_summary=row.get("cohesion_summary"),
            partnership_summary=row.get("partnership_summary"),
            unknown_fields=list(row.get("unknown_fields") or []),
            config_hash=str(row.get("config_hash") or ""),
            version_number=int(row.get("version_number") or 1),
            parent_snapshot_id=row.get("parent_snapshot_id"),
            is_immutable=bool(row.get("is_immutable", True)),
            created_at=row["created_at"].isoformat() if hasattr(row.get("created_at"), "isoformat") else str(row.get("created_at") or ""),
        )

    # ------------------------------------------------------------------ Fingerprints
    def save_fingerprint(self, fp: TacticalFingerprint) -> TacticalFingerprint:
        uid = str(fp.user_id)
        fp_key = f"{fp.match_id}::{fp.snapshot_id or 'UNLINKED'}"
        phase_map = {p.phase: p.model_dump(mode="json") for p in fp.phases}
        obs_shapes = {
            "in_possession": fp.observed_in_possession_shape,
            "out_of_possession": fp.observed_out_of_possession_shape,
            "evidence_grade": fp.evidence_grade.value,
            "visible_outfield_players": fp.visible_outfield_players,
            "team_compactness_abstained": fp.team_compactness_abstained,
            "abstention_reason": fp.abstention_reason,
            "model_version": fp.model_version,
            "metric_details": {k: v.model_dump(mode="json") for k, v in fp.metric_details.items()},
        }
        if self._use_pg(uid):
            db.execute(
                """INSERT INTO public.phase43_tactical_fingerprint
                   (fingerprint_id, fingerprint_key, user_id, match_id, snapshot_id,
                    game_version, game_patch, formation, provenance,
                    in_possession_metrics, out_of_possession_metrics,
                    attacking_transition_metrics, defensive_transition_metrics,
                    observed_shapes, intended_vs_observed_deltas,
                    coverage_pct, calibration_state, uncertainty_notes, unsupported_metrics)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (user_id, fingerprint_key) DO UPDATE SET
                     in_possession_metrics = EXCLUDED.in_possession_metrics,
                     out_of_possession_metrics = EXCLUDED.out_of_possession_metrics,
                     attacking_transition_metrics = EXCLUDED.attacking_transition_metrics,
                     defensive_transition_metrics = EXCLUDED.defensive_transition_metrics,
                     observed_shapes = EXCLUDED.observed_shapes,
                     intended_vs_observed_deltas = EXCLUDED.intended_vs_observed_deltas,
                     coverage_pct = EXCLUDED.coverage_pct,
                     calibration_state = EXCLUDED.calibration_state,
                     uncertainty_notes = EXCLUDED.uncertainty_notes,
                     unsupported_metrics = EXCLUDED.unsupported_metrics""",
                (
                    fp.fingerprint_id,
                    fp_key,
                    uid,
                    fp.match_id,
                    fp.snapshot_id,
                    fp.game_version,
                    fp.game_patch,
                    fp.nominal_formation,
                    fp.provenance,
                    Jsonb(phase_map.get("IN_POSSESSION", {})),
                    Jsonb(phase_map.get("OUT_OF_POSSESSION", {})),
                    Jsonb(phase_map.get("ATTACKING_TRANSITION", {})),
                    Jsonb(phase_map.get("DEFENSIVE_TRANSITION", {})),
                    Jsonb(obs_shapes),
                    Jsonb([d.model_dump(mode="json") for d in fp.intended_vs_observed_deltas]),
                    fp.coverage_pct,
                    fp.calibration_state,
                    Jsonb(fp.uncertainty_notes),
                    Jsonb(fp.unsupported_metrics),
                ),
            )
            return fp
        with self._lock:
            self._fingerprints.setdefault(uid, {})[fp_key] = fp
        return fp

    def list_fingerprints(
        self,
        user_id: str,
        *,
        match_id: Optional[str] = None,
        game_version: Optional[str] = None,
        limit: int = 50,
    ) -> List[TacticalFingerprint]:
        uid = str(user_id)
        if self._use_pg(uid):
            sql = "SELECT * FROM public.phase43_tactical_fingerprint WHERE user_id = %s"
            params: List[Any] = [uid]
            if match_id:
                sql += " AND match_id = %s"
                params.append(match_id)
            if game_version:
                sql += " AND game_version = %s"
                params.append(game_version.upper())
            sql += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            rows = db.query(sql, tuple(params))
            return [self._row_to_fingerprint(r) for r in rows]
        with self._lock:
            fps = list(self._fingerprints.get(uid, {}).values())
            if match_id:
                fps = [f for f in fps if f.match_id == match_id]
            if game_version:
                fps = [f for f in fps if f.game_version == game_version.upper()]
            fps.sort(key=lambda f: f.created_at, reverse=True)
            return fps[:limit]

    @staticmethod
    def _row_to_fingerprint(row: Dict[str, Any]) -> TacticalFingerprint:
        from backend.domain.phase43_models import EvidenceGrade, IntendedVsObservedDelta, PhaseMetricBlock

        phases = []
        for col in (
            "in_possession_metrics",
            "out_of_possession_metrics",
            "attacking_transition_metrics",
            "defensive_transition_metrics",
        ):
            blk = row.get(col)
            if blk and blk.get("phase"):
                phases.append(PhaseMetricBlock(**blk))
        obs = dict(row.get("observed_shapes") or {})
        return TacticalFingerprint(
            fingerprint_id=str(row["fingerprint_id"]),
            user_id=str(row["user_id"]),
            match_id=str(row["match_id"]),
            snapshot_id=row.get("snapshot_id"),
            game_version=row["game_version"],
            game_patch=str(row.get("game_patch") or "PATCH_1.04"),
            nominal_formation=str(row.get("formation") or "UNKNOWN"),
            observed_in_possession_shape=str(obs.get("in_possession") or "UNKNOWN_INSUFFICIENT_SPATIAL_DATA"),
            observed_out_of_possession_shape=str(obs.get("out_of_possession") or "UNKNOWN_INSUFFICIENT_SPATIAL_DATA"),
            provenance=str(row["provenance"]),
            phases=phases,
            metric_details={k: FingerprintMetricDetail(**v) for k, v in (obs.get("metric_details") or {}).items()},
            intended_vs_observed_deltas=[IntendedVsObservedDelta(**d) for d in (row.get("intended_vs_observed_deltas") or [])],
            coverage_pct=float(row.get("coverage_pct") or 0.0),
            calibration_state=str(row.get("calibration_state") or "UNKNOWN"),
            visible_outfield_players=obs.get("visible_outfield_players"),
            team_compactness_abstained=bool(obs.get("team_compactness_abstained", False)),
            abstention_reason=obs.get("abstention_reason"),
            uncertainty_notes=list(row.get("uncertainty_notes") or []),
            unsupported_metrics=list(row.get("unsupported_metrics") or []),
            evidence_grade=EvidenceGrade(obs.get("evidence_grade") or "OBSERVED_ASSOCIATION"),
            model_version=str(obs.get("model_version") or "phase43.fingerprint.v1"),
            created_at=row["created_at"].isoformat() if hasattr(row.get("created_at"), "isoformat") else str(row.get("created_at") or ""),
        )

    # ------------------------------------------------------------------ Experiments
    def create_experiment(self, rec: TacticalExperimentRecord) -> TacticalExperimentRecord:
        uid = str(rec.user_id)
        if self._use_pg(uid):
            if _pg_phase43_v2_ready():
                db.execute(
                    """INSERT INTO public.phase43_experiment
                       (experiment_id, user_id, title, hypothesis, experiment_type,
                        game_version, baseline_patch, gameplay_mode,
                        baseline_snapshot_id, variant_snapshot_id, primary_metric,
                        secondary_metrics, target_min_matches_per_arm, assignment_design, status,
                        protocol_version, design_type, minimum_meaningful_improvement,
                        planned_observations, required_coverage_pct, stopping_criteria_json,
                        confounders_json, random_seed)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        rec.experiment_id,
                        uid,
                        rec.title,
                        rec.hypothesis,
                        rec.experiment_type.value,
                        rec.game_version,
                        rec.baseline_patch,
                        rec.gameplay_mode,
                        rec.baseline_snapshot_id,
                        rec.variant_snapshot_id,
                        rec.primary_metric,
                        Jsonb(rec.secondary_metrics),
                        rec.target_min_matches_per_arm,
                        rec.assignment_design,
                        rec.status.value,
                        rec.protocol_version,
                        rec.design_type,
                        rec.minimum_meaningful_improvement,
                        rec.planned_observations,
                        rec.required_coverage_pct,
                        Jsonb(rec.stopping_criteria),
                        Jsonb(rec.confounder_controls),
                        rec.random_seed,
                    ),
                )
                db.execute(
                    """INSERT INTO public.phase43_experiment_protocol_version
                       (protocol_id, experiment_id, user_id, version_number, hypothesis, design_type,
                        primary_metric, secondary_metrics, minimum_meaningful_improvement,
                        planned_observations, required_coverage_pct, stopping_criteria_json,
                        confounder_controls_json, baseline_snapshot_id, variant_snapshot_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (experiment_id, version_number) DO NOTHING""",
                    (
                        str(uuid4()),
                        rec.experiment_id,
                        uid,
                        rec.protocol_version,
                        rec.hypothesis,
                        rec.design_type,
                        rec.primary_metric,
                        Jsonb(rec.secondary_metrics),
                        rec.minimum_meaningful_improvement,
                        rec.planned_observations,
                        rec.required_coverage_pct,
                        Jsonb(rec.stopping_criteria),
                        Jsonb(rec.confounder_controls),
                        rec.baseline_snapshot_id,
                        rec.variant_snapshot_id,
                    ),
                )
            else:
                db.execute(
                    """INSERT INTO public.phase43_experiment
                       (experiment_id, user_id, title, hypothesis, experiment_type,
                        game_version, baseline_patch, gameplay_mode,
                        baseline_snapshot_id, variant_snapshot_id, primary_metric,
                        secondary_metrics, target_min_matches_per_arm, assignment_design, status)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        rec.experiment_id,
                        uid,
                        rec.title,
                        rec.hypothesis,
                        rec.experiment_type.value,
                        rec.game_version,
                        rec.baseline_patch,
                        rec.gameplay_mode,
                        rec.baseline_snapshot_id,
                        rec.variant_snapshot_id,
                        rec.primary_metric,
                        Jsonb(rec.secondary_metrics),
                        rec.target_min_matches_per_arm,
                        rec.assignment_design,
                        rec.status.value,
                    ),
                )
            return rec
        with self._lock:
            self._experiments.setdefault(uid, {})[rec.experiment_id] = rec
            self._links.setdefault(uid, {}).setdefault(rec.experiment_id, [])
            self._assignments.setdefault(uid, {}).setdefault(rec.experiment_id, [])
        return rec

    def save_experiment_assignments(
        self,
        user_id: str,
        experiment_id: str,
        assignments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        uid = str(user_id)
        _ = self.get_experiment(uid, experiment_id)
        if self._use_pg(uid) and _pg_phase43_v2_ready():
            db.execute(
                "DELETE FROM public.phase43_experiment_assignment WHERE user_id = %s AND experiment_id = %s AND status = 'PENDING'",
                (uid, experiment_id),
            )
            saved: List[Dict[str, Any]] = []
            for item in assignments:
                aid = str(item.get("assignment_id") or uuid4())
                arm_short = "A" if str(item.get("assigned_arm") or "BASELINE_A") in ("A", "BASELINE_A") else "B"
                row = db.query_one(
                    """INSERT INTO public.phase43_experiment_assignment
                       (assignment_id, experiment_id, user_id, block_index, sequence_index,
                        assigned_arm, assigned_snapshot_id, status)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (experiment_id, sequence_index) DO UPDATE SET
                         assigned_arm = EXCLUDED.assigned_arm,
                         assigned_snapshot_id = EXCLUDED.assigned_snapshot_id,
                         updated_at = now()
                       RETURNING *""",
                    (
                        aid,
                        experiment_id,
                        uid,
                        int(item.get("block_index") or 1),
                        int(item.get("sequence_index") or 1),
                        arm_short,
                        str(item["assigned_snapshot_id"]),
                        str(item.get("status") or "PENDING"),
                    ),
                )
                if row:
                    saved.append({**dict(row), "assignment_id": str(row["assignment_id"]), "user_id": str(row["user_id"])})
            return saved
        with self._lock:
            out: List[Dict[str, Any]] = []
            for item in assignments:
                out.append({"assignment_id": str(item.get("assignment_id") or uuid4()), "experiment_id": experiment_id, "user_id": uid, **item})
            self._assignments.setdefault(uid, {})[experiment_id] = out
            return out

    def list_experiment_assignments(self, user_id: str, experiment_id: str) -> List[Dict[str, Any]]:
        uid = str(user_id)
        if self._use_pg(uid) and _pg_phase43_v2_ready():
            rows = db.query(
                "SELECT * FROM public.phase43_experiment_assignment WHERE user_id = %s AND experiment_id = %s ORDER BY sequence_index ASC",
                (uid, experiment_id),
            )
            return [
                {
                    **dict(r),
                    "assignment_id": str(r["assignment_id"]),
                    "user_id": str(r["user_id"]),
                    "created_at": r["created_at"].isoformat() if hasattr(r.get("created_at"), "isoformat") else str(r.get("created_at") or ""),
                    "updated_at": r["updated_at"].isoformat() if hasattr(r.get("updated_at"), "isoformat") else str(r.get("updated_at") or ""),
                }
                for r in rows
            ]
        with self._lock:
            return list(self._assignments.get(uid, {}).get(experiment_id, []))

    def update_experiment_status(
        self,
        user_id: str,
        experiment_id: str,
        new_status: ExperimentStatus,
        *,
        reason: Optional[str] = None,
    ) -> TacticalExperimentRecord:
        uid = str(user_id)
        exp = self.get_experiment(uid, experiment_id)
        if self._use_pg(uid):
            db.execute(
                """UPDATE public.phase43_experiment SET
                     status = %s,
                     completed_at = CASE WHEN %s IN ('COMPLETED','INCONCLUSIVE','INSUFFICIENT_EVIDENCE') THEN COALESCE(completed_at, now()) ELSE completed_at END,
                     cancelled_at = CASE WHEN %s = 'CANCELLED' THEN COALESCE(cancelled_at, now()) ELSE cancelled_at END,
                     updated_at = now()
                   WHERE user_id = %s AND experiment_id = %s""",
                (new_status.value, new_status.value, new_status.value, uid, experiment_id),
            )
            return self.get_experiment(uid, experiment_id)
        with self._lock:
            target = self._experiments.get(uid, {}).get(experiment_id)
            if not target:
                raise ExperimentNotFoundError(f"Experiment {experiment_id!r} not found.")
            target.status = new_status
            if reason:
                target.stopping_criteria["last_status_reason"] = reason
            target.updated_at = datetime.now(timezone.utc).isoformat()
            return self.get_experiment(uid, experiment_id)

    def link_match_to_experiment(
        self,
        user_id: str,
        experiment_id: str,
        req: ExperimentMatchLinkCreate,
        *,
        game_version: str,
        game_patch: str,
        gameplay_mode: str,
        excluded_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        uid = str(user_id)
        _ = self.get_experiment(uid, experiment_id)
        link_id = str(uuid4())
        entry = {
            "link_id": link_id,
            "experiment_id": experiment_id,
            "user_id": uid,
            "match_id": req.match_id,
            "arm": req.arm.value,
            "snapshot_id": req.snapshot_id,
            "game_version": game_version,
            "game_patch": game_patch,
            "gameplay_mode": gameplay_mode,
            "opponent_archetype": req.opponent_archetype,
            "match_order": req.match_order,
            "weight": 0.0 if excluded_reason else 1.0,
            "excluded_reason": excluded_reason,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if self._use_pg(uid):
            row = db.query_one(
                """INSERT INTO public.phase43_experiment_match_link
                   (experiment_id, user_id, match_id, arm, snapshot_id,
                    game_version, game_patch, gameplay_mode, opponent_archetype,
                    match_order, weight, excluded_reason)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (experiment_id, match_id) DO UPDATE SET
                     arm = EXCLUDED.arm,
                     snapshot_id = EXCLUDED.snapshot_id,
                     opponent_archetype = EXCLUDED.opponent_archetype,
                     match_order = EXCLUDED.match_order,
                     weight = EXCLUDED.weight,
                     excluded_reason = EXCLUDED.excluded_reason
                   RETURNING *""",
                (
                    experiment_id,
                    uid,
                    req.match_id,
                    req.arm.value,
                    req.snapshot_id,
                    game_version,
                    game_patch,
                    gameplay_mode,
                    req.opponent_archetype,
                    req.match_order,
                    entry["weight"],
                    excluded_reason,
                ),
            )
            db.execute(
                "UPDATE public.phase43_experiment SET status = CASE WHEN status IN ('DRAFT','READY') THEN 'ACTIVE' ELSE status END, updated_at = now() WHERE experiment_id = %s AND user_id = %s",
                (experiment_id, uid),
            )
            if _pg_phase43_v2_ready():
                obs_arm = "A" if req.arm.value == "BASELINE_A" else "B"
                db.execute(
                    """INSERT INTO public.phase43_experiment_observation
                       (observation_id, experiment_id, user_id, match_id, arm, snapshot_id,
                        game_version, game_patch, gameplay_mode, opponent_archetype,
                        metric_values, coverage_pct, adherent, model_version, excluded_reason)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (experiment_id, match_id) DO UPDATE SET
                         arm = EXCLUDED.arm,
                         snapshot_id = EXCLUDED.snapshot_id,
                         opponent_archetype = EXCLUDED.opponent_archetype,
                         excluded_reason = EXCLUDED.excluded_reason""",
                    (
                        str(uuid4()),
                        experiment_id,
                        uid,
                        req.match_id,
                        obs_arm,
                        req.snapshot_id,
                        game_version,
                        game_patch,
                        gameplay_mode,
                        req.opponent_archetype,
                        Jsonb({}),
                        0.0,
                        excluded_reason is None,
                        "phase43.stats.v1",
                        excluded_reason,
                    ),
                )
                pending = db.query_one(
                    """SELECT * FROM public.phase43_experiment_assignment
                       WHERE user_id = %s AND experiment_id = %s AND status = 'PENDING'
                       ORDER BY sequence_index ASC LIMIT 1""",
                    (uid, experiment_id),
                )
                if pending:
                    adherent = (pending["assigned_arm"] == obs_arm) and (
                        not req.snapshot_id or pending["assigned_snapshot_id"] == req.snapshot_id
                    )
                    db.execute(
                        """UPDATE public.phase43_experiment_assignment SET
                             observed_match_id = %s,
                             observed_snapshot_id = %s,
                             observed_arm = %s,
                             adherent = %s,
                             status = %s,
                             deviation_reason = %s,
                             updated_at = now()
                           WHERE assignment_id = %s""",
                        (
                            req.match_id,
                            req.snapshot_id,
                            obs_arm,
                            adherent,
                            "COMPLETED" if adherent else "DEVIATED",
                            None if adherent else f"Expected {pending['assigned_arm']} ({pending['assigned_snapshot_id']}), observed {obs_arm}",
                            str(pending["assignment_id"]),
                        ),
                    )
            return {**entry, **dict(row or {}), "link_id": str((row or {}).get("link_id") or link_id)}

        with self._lock:
            links = self._links.setdefault(uid, {}).setdefault(experiment_id, [])
            links = [l for l in links if l["match_id"] != req.match_id]
            links.append(entry)
            self._links[uid][experiment_id] = links
            assigns = self._assignments.setdefault(uid, {}).setdefault(experiment_id, [])
            obs_arm = "A" if req.arm.value == "BASELINE_A" else "B"
            for item in assigns:
                if item.get("status") == "PENDING":
                    adherent = (item.get("assigned_arm") == obs_arm) and (
                        not req.snapshot_id or item.get("assigned_snapshot_id") == req.snapshot_id
                    )
                    item["observed_match_id"] = req.match_id
                    item["observed_snapshot_id"] = req.snapshot_id
                    item["observed_arm"] = obs_arm
                    item["adherent"] = adherent
                    item["status"] = "COMPLETED" if adherent else "DEVIATED"
                    item["deviation_reason"] = None if adherent else f"Expected {item.get('assigned_arm')}, observed {obs_arm}"
                    break
            exp = self._experiments[uid][experiment_id]
            if exp.status in (ExperimentStatus.DRAFT, ExperimentStatus.READY):
                exp.status = ExperimentStatus.ACTIVE
            exp.updated_at = datetime.now(timezone.utc).isoformat()
        return entry

    def get_experiment(self, user_id: str, experiment_id: str) -> TacticalExperimentRecord:
        uid = str(user_id)
        if self._use_pg(uid):
            row = db.query_one(
                "SELECT * FROM public.phase43_experiment WHERE user_id = %s AND experiment_id = %s",
                (uid, experiment_id),
            )
            if not row:
                raise ExperimentNotFoundError(f"Experiment {experiment_id!r} not found.")
            links = db.query(
                """SELECT * FROM public.phase43_experiment_match_link
                   WHERE user_id = %s AND experiment_id = %s ORDER BY match_order ASC, created_at ASC""",
                (uid, experiment_id),
            )
            clean_links = [
                {
                    **dict(l),
                    "link_id": str(l["link_id"]),
                    "user_id": str(l["user_id"]),
                    "created_at": l["created_at"].isoformat() if hasattr(l.get("created_at"), "isoformat") else str(l.get("created_at") or ""),
                }
                for l in links
            ]
            assigns = self.list_experiment_assignments(uid, experiment_id)
            return self._row_to_experiment(row, clean_links, assigns)
        with self._lock:
            exp = self._experiments.get(uid, {}).get(experiment_id)
            if not exp:
                raise ExperimentNotFoundError(f"Experiment {experiment_id!r} not found.")
            copy_exp = exp.model_copy(deep=True)
            copy_exp.linked_matches = list(self._links.get(uid, {}).get(experiment_id, []))
            assigns = list(self._assignments.get(uid, {}).get(experiment_id, []))
            copy_exp.assignments = assigns
            scored = [a for a in assigns if a.get("adherent") is not None]
            copy_exp.adherence_rate = round(sum(1 for a in scored if a.get("adherent")) / len(scored), 4) if scored else None
            return copy_exp

    def list_experiments(self, user_id: str, *, game_version: Optional[str] = None, limit: int = 30) -> List[TacticalExperimentRecord]:
        uid = str(user_id)
        if self._use_pg(uid):
            sql = "SELECT * FROM public.phase43_experiment WHERE user_id = %s"
            params: List[Any] = [uid]
            if game_version:
                sql += " AND game_version = %s"
                params.append(game_version.upper())
            sql += " ORDER BY updated_at DESC LIMIT %s"
            params.append(limit)
            rows = db.query(sql, tuple(params))
            return [self.get_experiment(uid, str(r["experiment_id"])) for r in rows]
        with self._lock:
            items = list(self._experiments.get(uid, {}).values())
            if game_version:
                items = [e for e in items if e.game_version == game_version.upper()]
            items.sort(key=lambda e: e.updated_at, reverse=True)
            return [self.get_experiment(uid, e.experiment_id) for e in items[:limit]]

    def save_experiment_analysis(
        self,
        user_id: str,
        experiment_id: str,
        analysis: ExperimentStatisticalAnalysis,
        new_status: ExperimentStatus,
    ) -> TacticalExperimentRecord:
        uid = str(user_id)
        if self._use_pg(uid):
            db.execute(
                """UPDATE public.phase43_experiment SET
                     analysis_cache = %s,
                     status = %s,
                     completed_at = CASE WHEN %s IN ('COMPLETED','INCONCLUSIVE','INSUFFICIENT_EVIDENCE') THEN COALESCE(completed_at, now()) ELSE completed_at END,
                     updated_at = now()
                   WHERE user_id = %s AND experiment_id = %s""",
                (Jsonb(analysis.model_dump(mode="json")), new_status.value, new_status.value, uid, experiment_id),
            )
            if _pg_phase43_v2_ready():
                db.execute(
                    """INSERT INTO public.phase43_experiment_analysis
                       (analysis_id, experiment_id, user_id, protocol_version, verdict,
                        estimated_effect, relative_improvement, ci_low, ci_high, p_value,
                        posterior_prob_meaningful, confidence_score, adherence_rate,
                        sample_counts_json, confounder_warnings_json, full_payload, model_version)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        str(uuid4()),
                        experiment_id,
                        uid,
                        analysis.protocol_version,
                        analysis.verdict.value,
                        analysis.raw_delta_b_minus_a,
                        analysis.relative_improvement,
                        analysis.bootstrap_ci_95[0] if analysis.bootstrap_ci_95 and len(analysis.bootstrap_ci_95) == 2 else None,
                        analysis.bootstrap_ci_95[1] if analysis.bootstrap_ci_95 and len(analysis.bootstrap_ci_95) == 2 else None,
                        analysis.p_value,
                        analysis.posterior_prob_meaningful,
                        analysis.bayesian_posterior_prob_b_better,
                        analysis.adherence_rate,
                        Jsonb({"arm_a": analysis.arm_a.eligible_match_count, "arm_b": analysis.arm_b.eligible_match_count}),
                        Jsonb(analysis.confounders.match_quality_warnings),
                        Jsonb(analysis.model_dump(mode="json")),
                        analysis.model_version,
                    ),
                )
            return self.get_experiment(uid, experiment_id)
        with self._lock:
            exp = self._experiments.get(uid, {}).get(experiment_id)
            if not exp:
                raise ExperimentNotFoundError(f"Experiment {experiment_id!r} not found.")
            exp.analysis = analysis
            exp.status = new_status
            exp.updated_at = datetime.now(timezone.utc).isoformat()
            return self.get_experiment(uid, experiment_id)

    @staticmethod
    def _row_to_experiment(
        row: Dict[str, Any],
        links: List[Dict[str, Any]],
        assignments: Optional[List[Dict[str, Any]]] = None,
    ) -> TacticalExperimentRecord:
        cache = row.get("analysis_cache")
        assigns = assignments or []
        scored = [a for a in assigns if a.get("adherent") is not None]
        adh_rate = round(sum(1 for a in scored if a.get("adherent")) / len(scored), 4) if scored else None
        return TacticalExperimentRecord(
            experiment_id=str(row["experiment_id"]),
            user_id=str(row["user_id"]),
            title=str(row["title"]),
            hypothesis=str(row["hypothesis"]),
            experiment_type=ExperimentType(row["experiment_type"]),
            game_version=row["game_version"],
            baseline_patch=str(row.get("baseline_patch") or "PATCH_1.04"),
            gameplay_mode=str(row.get("gameplay_mode") or "COMPETITIVE_RIVALS"),
            baseline_snapshot_id=str(row["baseline_snapshot_id"]),
            variant_snapshot_id=str(row["variant_snapshot_id"]),
            primary_metric=str(row.get("primary_metric") or "conceded_transition_rate"),
            secondary_metrics=list(row.get("secondary_metrics") or []),
            target_min_matches_per_arm=int(row.get("target_min_matches_per_arm") or 3),
            assignment_design=str(row.get("assignment_design") or "MATCH_PAIRED_OR_RANDOMIZED_ABBA"),
            protocol_version=int(row.get("protocol_version") or 1),
            design_type=str(row.get("design_type") or "CROSSOVER_ABBA"),
            minimum_meaningful_improvement=float(row.get("minimum_meaningful_improvement") if row.get("minimum_meaningful_improvement") is not None else 0.05),
            planned_observations=int(row.get("planned_observations") or 6),
            required_coverage_pct=float(row.get("required_coverage_pct") if row.get("required_coverage_pct") is not None else 35.0),
            stopping_criteria=dict(row.get("stopping_criteria_json") or {}),
            confounder_controls=dict(row.get("confounders_json") or {}),
            random_seed=int(row.get("random_seed") or 43),
            status=ExperimentStatus(row.get("status") or "DRAFT"),
            linked_matches=links,
            assignments=assigns,
            adherence_rate=adh_rate,
            analysis=ExperimentStatisticalAnalysis(**cache) if cache else None,
            created_at=row["created_at"].isoformat() if hasattr(row.get("created_at"), "isoformat") else str(row.get("created_at") or ""),
            updated_at=row["updated_at"].isoformat() if hasattr(row.get("updated_at"), "isoformat") else str(row.get("updated_at") or ""),
        )

    # ------------------------------------------------------------------ Personal Meta
    def save_personal_meta(self, profile: PersonalMetaProfile) -> PersonalMetaProfile:
        uid = str(profile.user_id)
        if self._use_pg(uid):
            db.execute(
                """INSERT INTO public.phase43_personal_meta
                   (meta_id, user_id, game_version, game_patch, profile_payload, eligible_match_count, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,now())
                   ON CONFLICT (user_id, game_version, game_patch) DO UPDATE SET
                     profile_payload = EXCLUDED.profile_payload,
                     eligible_match_count = EXCLUDED.eligible_match_count,
                     updated_at = now()""",
                (
                    profile.meta_id,
                    uid,
                    profile.game_version,
                    profile.game_patch,
                    Jsonb(profile.model_dump(mode="json")),
                    profile.eligible_match_count,
                ),
            )
            return profile
        with self._lock:
            self._meta.setdefault(uid, {})[profile.meta_id] = profile
        return profile

    def list_personal_meta(self, user_id: str) -> List[PersonalMetaProfile]:
        uid = str(user_id)
        if self._use_pg(uid):
            rows = db.query(
                "SELECT profile_payload FROM public.phase43_personal_meta WHERE user_id = %s ORDER BY updated_at DESC",
                (uid,),
            )
            return [PersonalMetaProfile(**r["profile_payload"]) for r in rows]
        with self._lock:
            return list(self._meta.get(uid, {}).values())

    def save_formation_fit_observation(
        self,
        user_id: str,
        *,
        game_version: str,
        game_patch: str,
        formation: str,
        theoretical_fit: float,
        observed_performance: Optional[float],
        controlled_experiment_evidence: Optional[float],
        overall_suitability: float,
        confidence: float,
        sample_matches: int,
        payload: Dict[str, Any],
    ) -> None:
        uid = str(user_id)
        if self._use_pg(uid) and _pg_phase43_v2_ready():
            db.execute(
                """INSERT INTO public.phase43_formation_fit_observation
                   (fit_obs_id, user_id, game_version, game_patch, formation,
                    theoretical_fit, observed_performance, controlled_experiment_evidence,
                    overall_suitability, confidence, sample_matches, payload)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    str(uuid4()),
                    uid,
                    game_version,
                    game_patch,
                    formation,
                    theoretical_fit,
                    observed_performance,
                    controlled_experiment_evidence,
                    overall_suitability,
                    confidence,
                    sample_matches,
                    Jsonb(payload),
                ),
            )

    def save_replacement_experiment(
        self,
        user_id: str,
        *,
        game_version: str,
        position: str,
        outgoing_card_id: Optional[str],
        candidate_card_id: Optional[str],
        verdict: str,
        no_coin_viable: bool,
        payload: Dict[str, Any],
        snapshot_id: Optional[str] = None,
    ) -> str:
        uid = str(user_id)
        rid = str(uuid4())
        if self._use_pg(uid) and _pg_phase43_v2_ready():
            db.execute(
                """INSERT INTO public.phase43_replacement_experiment
                   (replacement_id, user_id, snapshot_id, game_version, position,
                    outgoing_card_id, candidate_card_id, verdict,
                    no_coin_tactical_alternative_viable, market_price_status, payload)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    rid,
                    uid,
                    snapshot_id,
                    game_version,
                    position,
                    outgoing_card_id,
                    candidate_card_id,
                    verdict,
                    no_coin_viable,
                    "MARKET_PRICE_UNAVAILABLE",
                    Jsonb(payload),
                ),
            )
        return rid

    def save_recommendation_feedback(self, rec: RecommendationFeedbackRecord) -> RecommendationFeedbackRecord:
        uid = str(rec.user_id)
        if self._use_pg(uid) and _pg_phase43_v2_ready():
            db.execute(
                """INSERT INTO public.phase43_recommendation_feedback
                   (feedback_id, user_id, recommendation_id, recommendation_type, game_version,
                    game_patch, user_action, snapshot_id, experiment_id, observation_id,
                    estimated_effect, uncertainty_summary, model_version, notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    rec.feedback_id,
                    uid,
                    rec.recommendation_id,
                    rec.recommendation_type,
                    rec.game_version,
                    rec.game_patch,
                    rec.user_action,
                    rec.snapshot_id,
                    rec.experiment_id,
                    rec.observation_id,
                    rec.estimated_effect,
                    Jsonb(rec.uncertainty_summary),
                    rec.model_version,
                    rec.notes,
                ),
            )
            return rec
        with self._lock:
            self._feedback.setdefault(uid, []).insert(0, rec)
        return rec

    def list_recommendation_feedback(
        self,
        user_id: str,
        *,
        game_version: Optional[str] = None,
        limit: int = 50,
    ) -> List[RecommendationFeedbackRecord]:
        uid = str(user_id)
        if self._use_pg(uid) and _pg_phase43_v2_ready():
            sql = "SELECT * FROM public.phase43_recommendation_feedback WHERE user_id = %s"
            params: List[Any] = [uid]
            if game_version:
                sql += " AND game_version = %s"
                params.append(game_version.upper())
            sql += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            rows = db.query(sql, tuple(params))
            return [
                RecommendationFeedbackRecord(
                    feedback_id=str(r["feedback_id"]),
                    user_id=str(r["user_id"]),
                    recommendation_id=str(r["recommendation_id"]),
                    recommendation_type=str(r["recommendation_type"]),
                    game_version=r["game_version"],
                    game_patch=str(r["game_patch"]),
                    user_action=r["user_action"],
                    snapshot_id=r.get("snapshot_id"),
                    experiment_id=r.get("experiment_id"),
                    observation_id=str(r["observation_id"]) if r.get("observation_id") else None,
                    estimated_effect=r.get("estimated_effect"),
                    uncertainty_summary=dict(r.get("uncertainty_summary") or {}),
                    model_version=str(r.get("model_version") or "phase43.v1"),
                    notes=str(r.get("notes") or ""),
                    created_at=r["created_at"].isoformat() if hasattr(r.get("created_at"), "isoformat") else str(r.get("created_at") or ""),
                )
                for r in rows
            ]
        with self._lock:
            items = list(self._feedback.get(uid, []))
            if game_version:
                items = [f for f in items if f.game_version == game_version.upper()]
            return items[:limit]

    def reset_user_phase43_data(self, user_id: str) -> Dict[str, int]:
        uid = str(user_id)
        if self._use_pg(uid):
            with db.get_conn() as conn:
                c_fb = 0
                if _pg_phase43_v2_ready():
                    c_fb = conn.execute("DELETE FROM public.phase43_recommendation_feedback WHERE user_id = %s", (uid,)).rowcount
                    conn.execute("DELETE FROM public.phase43_replacement_experiment WHERE user_id = %s", (uid,))
                    conn.execute("DELETE FROM public.phase43_formation_fit_observation WHERE user_id = %s", (uid,))
                c_exp = conn.execute("DELETE FROM public.phase43_experiment WHERE user_id = %s", (uid,)).rowcount
                c_fp = conn.execute("DELETE FROM public.phase43_tactical_fingerprint WHERE user_id = %s", (uid,)).rowcount
                c_sn = conn.execute("DELETE FROM public.phase43_tactical_snapshot WHERE user_id = %s", (uid,)).rowcount
                c_me = conn.execute("DELETE FROM public.phase43_personal_meta WHERE user_id = %s", (uid,)).rowcount
                conn.commit()
            return {"experiments_deleted": c_exp, "fingerprints_deleted": c_fp, "snapshots_deleted": c_sn, "meta_deleted": c_me, "feedback_deleted": c_fb}
        with self._lock:
            self._assignments.pop(uid, None)
            self._links.pop(uid, None)
            return {
                "experiments_deleted": len(self._experiments.pop(uid, {})),
                "fingerprints_deleted": len(self._fingerprints.pop(uid, {})),
                "snapshots_deleted": len(self._snapshots.pop(uid, {})),
                "meta_deleted": len(self._meta.pop(uid, {})),
                "feedback_deleted": len(self._feedback.pop(uid, [])),
            }


_SHARED_PHASE43_REPO: Optional[Phase43Repository] = None


def get_phase43_repository() -> Phase43Repository:
    global _SHARED_PHASE43_REPO
    if _SHARED_PHASE43_REPO is None:
        _SHARED_PHASE43_REPO = Phase43Repository()
    return _SHARED_PHASE43_REPO
