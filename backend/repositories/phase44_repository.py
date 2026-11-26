"""Phase 44 Repository: Governed Pro Reference Registry, Gamer DNA V2, Similarity, Evolution & Feedback.

Dual-mode PostgreSQL (`021_phase44_gamer_dna_v2.sql`) + thread-safe in-memory storage.
Strictly scopes user records to `user_id` and invalidates derived reference data upon rights revocation.
"""
from __future__ import annotations

import threading
import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from psycopg.types.json import Jsonb

from backend.core import db
from backend.domain.phase44_models import (
    EliteSkillGapReport,
    GamerStyleVectorV2,
    ProStyleProfileVersion,
    ProStyleSimilarityReport,
    ProfessionalGamerReference,
    ReferenceMatchRecord,
    ReferenceRightsRecord,
    ReferenceSourceRecord,
    RightsStatus,
    StyleEvolutionReport,
    StyleRecommendationFeedbackRecord,
)


def _pg_phase44_ready() -> bool:
    try:
        row = db.query_one("SELECT to_regclass('public.phase44_professional_gamer_reference') AS tbl")
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


class Phase44Repository:
    def __init__(self, *, force_memory: bool = False) -> None:
        self._force_memory = force_memory
        self._lock = threading.RLock()
        self._sources: Dict[str, ReferenceSourceRecord] = {}
        self._references: Dict[str, ProfessionalGamerReference] = {}
        self._rights: Dict[str, ReferenceRightsRecord] = {}
        self._ref_matches: Dict[str, List[ReferenceMatchRecord]] = {}
        self._pro_profiles: Dict[str, List[ProStyleProfileVersion]] = {}
        self._gamer_profiles: Dict[str, List[GamerStyleVectorV2]] = {}
        self._similarity_runs: Dict[str, List[ProStyleSimilarityReport]] = {}
        self._skill_gaps: Dict[str, List[EliteSkillGapReport]] = {}
        self._evolutions: Dict[str, List[StyleEvolutionReport]] = {}
        self._feedback: Dict[str, List[StyleRecommendationFeedbackRecord]] = {}

    def _use_pg_global(self) -> bool:
        return (not self._force_memory) and _pg_phase44_ready()

    def _use_pg_user(self, user_id: str) -> bool:
        return (not self._force_memory) and _pg_phase44_ready() and _user_in_pg(user_id)

    # ------------------------------------------------------------------ Reference Governance
    def upsert_source(self, src: ReferenceSourceRecord) -> ReferenceSourceRecord:
        if self._use_pg_global():
            db.execute(
                """INSERT INTO public.phase44_professional_reference_source
                   (source_id, title, source_type, source_url, license_or_terms, attribution_required)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (source_id) DO UPDATE SET
                     title = EXCLUDED.title,
                     source_type = EXCLUDED.source_type,
                     source_url = EXCLUDED.source_url,
                     license_or_terms = EXCLUDED.license_or_terms,
                     attribution_required = EXCLUDED.attribution_required""",
                (src.source_id, src.title, src.source_type, src.source_url, src.license_or_terms, src.attribution_required),
            )
            return src
        with self._lock:
            self._sources[src.source_id] = src
        return src

    def upsert_reference(self, ref: ProfessionalGamerReference, rights: ReferenceRightsRecord) -> ProfessionalGamerReference:
        if self._use_pg_global():
            db.execute(
                """INSERT INTO public.phase44_professional_gamer_reference
                   (reference_id, public_alias, display_name, competition_affiliations,
                    applicable_editions, dataset_version, reference_match_count,
                    evidence_quality, profile_coverage, is_independent_unendorsed, metadata_notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (reference_id) DO UPDATE SET
                     public_alias = EXCLUDED.public_alias,
                     display_name = EXCLUDED.display_name,
                     competition_affiliations = EXCLUDED.competition_affiliations,
                     applicable_editions = EXCLUDED.applicable_editions,
                     dataset_version = EXCLUDED.dataset_version,
                     reference_match_count = EXCLUDED.reference_match_count,
                     evidence_quality = EXCLUDED.evidence_quality,
                     profile_coverage = EXCLUDED.profile_coverage,
                     metadata_notes = EXCLUDED.metadata_notes,
                     updated_at = now()""",
                (
                    ref.reference_id,
                    ref.public_alias,
                    ref.display_name,
                    Jsonb(ref.competition_affiliations),
                    Jsonb(ref.applicable_editions),
                    ref.dataset_version,
                    ref.reference_match_count,
                    ref.evidence_quality,
                    ref.profile_coverage,
                    ref.is_independent_unendorsed,
                    ref.metadata_notes,
                ),
            )
            db.execute(
                """INSERT INTO public.phase44_professional_reference_rights
                   (rights_id, reference_id, source_id, rights_status,
                    allow_local_research, allow_feature_extraction, allow_model_training,
                    allow_commercial_inference, allow_public_profile_display,
                    allow_video_redistribution, allow_derived_dataset_redistribution,
                    verified_by, revocation_reason)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (reference_id) DO UPDATE SET
                     source_id = EXCLUDED.source_id,
                     rights_status = EXCLUDED.rights_status,
                     allow_local_research = EXCLUDED.allow_local_research,
                     allow_feature_extraction = EXCLUDED.allow_feature_extraction,
                     allow_model_training = EXCLUDED.allow_model_training,
                     allow_commercial_inference = EXCLUDED.allow_commercial_inference,
                     allow_public_profile_display = EXCLUDED.allow_public_profile_display,
                     allow_video_redistribution = EXCLUDED.allow_video_redistribution,
                     allow_derived_dataset_redistribution = EXCLUDED.allow_derived_dataset_redistribution,
                     verified_by = EXCLUDED.verified_by,
                     revocation_reason = EXCLUDED.revocation_reason,
                     updated_at = now()""",
                (
                    rights.rights_id,
                    rights.reference_id,
                    rights.source_id,
                    rights.rights_status.value,
                    rights.allow_local_research,
                    rights.allow_feature_extraction,
                    rights.allow_model_training,
                    rights.allow_commercial_inference,
                    rights.allow_public_profile_display,
                    rights.allow_video_redistribution,
                    rights.allow_derived_dataset_redistribution,
                    rights.verified_by,
                    rights.revocation_reason,
                ),
            )
            return self.get_reference(ref.reference_id) or ref
        with self._lock:
            stored_ref = ref.model_copy(update={"rights_status": rights.rights_status, "rights": rights})
            self._references[ref.reference_id] = stored_ref
            self._rights[ref.reference_id] = rights
            return stored_ref

    def get_reference(self, reference_id: str) -> Optional[ProfessionalGamerReference]:
        if self._use_pg_global():
            row = db.query_one(
                """SELECT g.*, r.rights_id, r.source_id, r.rights_status,
                          r.allow_local_research, r.allow_feature_extraction, r.allow_model_training,
                          r.allow_commercial_inference, r.allow_public_profile_display,
                          r.allow_video_redistribution, r.allow_derived_dataset_redistribution,
                          r.verified_by, r.revocation_reason
                   FROM public.phase44_professional_gamer_reference g
                   LEFT JOIN public.phase44_professional_reference_rights r ON r.reference_id = g.reference_id
                   WHERE g.reference_id = %s""",
                (reference_id,),
            )
            return self._row_to_reference(row) if row else None
        with self._lock:
            ref = self._references.get(reference_id)
            if not ref:
                return None
            rt = self._rights.get(reference_id)
            return ref.model_copy(update={"rights": rt, "rights_status": rt.rights_status if rt else RightsStatus.UNKNOWN})

    def list_references(self) -> List[ProfessionalGamerReference]:
        if self._use_pg_global():
            rows = db.query(
                """SELECT g.*, r.rights_id, r.source_id, r.rights_status,
                          r.allow_local_research, r.allow_feature_extraction, r.allow_model_training,
                          r.allow_commercial_inference, r.allow_public_profile_display,
                          r.allow_video_redistribution, r.allow_derived_dataset_redistribution,
                          r.verified_by, r.revocation_reason
                   FROM public.phase44_professional_gamer_reference g
                   LEFT JOIN public.phase44_professional_reference_rights r ON r.reference_id = g.reference_id
                   ORDER BY g.public_alias ASC"""
            )
            return [self._row_to_reference(r) for r in rows]
        with self._lock:
            return sorted(self._references.values(), key=lambda x: x.public_alias)

    @staticmethod
    def _row_to_reference(row: Dict[str, Any]) -> ProfessionalGamerReference:
        rs_raw = row.get("rights_status") or "UNKNOWN"
        rights = ReferenceRightsRecord(
            rights_id=str(row.get("rights_id") or uuid4()),
            reference_id=str(row["reference_id"]),
            source_id=row.get("source_id"),
            rights_status=RightsStatus(rs_raw),
            allow_local_research=bool(row.get("allow_local_research", False)),
            allow_feature_extraction=bool(row.get("allow_feature_extraction", False)),
            allow_model_training=bool(row.get("allow_model_training", False)),
            allow_commercial_inference=bool(row.get("allow_commercial_inference", False)),
            allow_public_profile_display=bool(row.get("allow_public_profile_display", False)),
            allow_video_redistribution=bool(row.get("allow_video_redistribution", False)),
            allow_derived_dataset_redistribution=bool(row.get("allow_derived_dataset_redistribution", False)),
            verified_by=row.get("verified_by"),
            revocation_reason=row.get("revocation_reason"),
        )
        return ProfessionalGamerReference(
            reference_id=str(row["reference_id"]),
            public_alias=str(row["public_alias"]),
            display_name=row.get("display_name"),
            competition_affiliations=list(row.get("competition_affiliations") or []),
            applicable_editions=list(row.get("applicable_editions") or ["FC26", "FC27"]),
            dataset_version=str(row.get("dataset_version") or "NONE"),
            reference_match_count=int(row.get("reference_match_count") or 0),
            evidence_quality=str(row.get("evidence_quality") or "NONE"),  # type: ignore[arg-type]
            profile_coverage=float(row.get("profile_coverage") or 0.0),
            rights_status=rights.rights_status,
            rights=rights,
            is_independent_unendorsed=bool(row.get("is_independent_unendorsed", True)),
            metadata_notes=str(row.get("metadata_notes") or ""),
        )

    def revoke_reference_rights(self, reference_id: str, *, reason: str = "Rights revoked by governance audit") -> Optional[ProfessionalGamerReference]:
        """Transitions rights to REVOKED and invalidates all downstream matches and pro style profiles."""
        if self._use_pg_global():
            db.execute(
                """UPDATE public.phase44_professional_reference_rights SET
                     rights_status = 'REVOKED',
                     allow_local_research = FALSE,
                     allow_feature_extraction = FALSE,
                     allow_model_training = FALSE,
                     allow_commercial_inference = FALSE,
                     allow_public_profile_display = FALSE,
                     allow_video_redistribution = FALSE,
                     allow_derived_dataset_redistribution = FALSE,
                     revocation_reason = %s,
                     revoked_at = now(),
                     updated_at = now()
                   WHERE reference_id = %s""",
                (reason, reference_id),
            )
            db.execute("UPDATE public.phase44_reference_match SET is_invalidated = TRUE WHERE reference_id = %s", (reference_id,))
            db.execute("UPDATE public.phase44_professional_style_profile_version SET is_invalidated = TRUE WHERE reference_id = %s", (reference_id,))
            return self.get_reference(reference_id)
        with self._lock:
            rt = self._rights.get(reference_id)
            if not rt:
                return None
            rev = rt.model_copy(
                update={
                    "rights_status": RightsStatus.REVOKED,
                    "allow_local_research": False,
                    "allow_feature_extraction": False,
                    "allow_model_training": False,
                    "allow_commercial_inference": False,
                    "allow_public_profile_display": False,
                    "allow_video_redistribution": False,
                    "allow_derived_dataset_redistribution": False,
                    "revocation_reason": reason,
                    "revoked_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            self._rights[reference_id] = rev
            if reference_id in self._references:
                self._references[reference_id] = self._references[reference_id].model_copy(update={"rights_status": RightsStatus.REVOKED, "rights": rev})
            for m in self._ref_matches.get(reference_id, []):
                m.is_invalidated = True
            for p in self._pro_profiles.get(reference_id, []):
                p.is_invalidated = True
            return self.get_reference(reference_id)

    def add_reference_match(self, m: ReferenceMatchRecord) -> ReferenceMatchRecord:
        if self._use_pg_global():
            db.execute(
                """INSERT INTO public.phase44_reference_match
                   (ref_match_id, reference_id, source_id, game_version, game_patch,
                    competition_name, gameplay_mode, formation, coverage_pct,
                    feature_payload, provenance, is_invalidated)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (ref_match_id) DO UPDATE SET
                     feature_payload = EXCLUDED.feature_payload,
                     coverage_pct = EXCLUDED.coverage_pct,
                     is_invalidated = EXCLUDED.is_invalidated""",
                (
                    m.ref_match_id, m.reference_id, m.source_id, m.game_version, m.game_patch,
                    m.competition_name, m.gameplay_mode, m.formation, m.coverage_pct,
                    Jsonb(m.feature_payload), m.provenance, m.is_invalidated,
                ),
            )
            return m
        with self._lock:
            lst = [x for x in self._ref_matches.setdefault(m.reference_id, []) if x.ref_match_id != m.ref_match_id]
            lst.append(m)
            self._ref_matches[m.reference_id] = lst
        return m

    def list_reference_matches(self, reference_id: str, *, game_version: Optional[str] = None, include_invalidated: bool = False) -> List[ReferenceMatchRecord]:
        if self._use_pg_global():
            sql = "SELECT * FROM public.phase44_reference_match WHERE reference_id = %s"
            params: List[Any] = [reference_id]
            if not include_invalidated:
                sql += " AND is_invalidated = FALSE"
            if game_version:
                sql += " AND game_version = %s"
                params.append(game_version.upper())
            sql += " ORDER BY created_at DESC"
            return [
                ReferenceMatchRecord(
                    ref_match_id=str(r["ref_match_id"]),
                    reference_id=str(r["reference_id"]),
                    source_id=r.get("source_id"),
                    game_version=r["game_version"],
                    game_patch=str(r["game_patch"]),
                    competition_name=str(r["competition_name"]),
                    gameplay_mode=str(r["gameplay_mode"]),
                    formation=r.get("formation"),
                    coverage_pct=float(r["coverage_pct"]),
                    feature_payload=dict(r.get("feature_payload") or {}),
                    provenance=str(r["provenance"]),
                    is_invalidated=bool(r["is_invalidated"]),
                )
                for r in db.query(sql, tuple(params))
            ]
        with self._lock:
            items = list(self._ref_matches.get(reference_id, []))
            if not include_invalidated:
                items = [x for x in items if not x.is_invalidated]
            if game_version:
                items = [x for x in items if x.game_version == game_version.upper()]
            return items

    def save_pro_profile(self, prof: ProStyleProfileVersion) -> ProStyleProfileVersion:
        if self._use_pg_global():
            db.execute(
                """INSERT INTO public.phase44_professional_style_profile_version
                   (pro_profile_id, reference_id, game_version, game_patch, dataset_version,
                    eligible_ref_matches, coverage, feature_vectors_json, distributions_json,
                    model_version, is_invalidated)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    prof.pro_profile_id, prof.reference_id, prof.game_version, prof.game_patch,
                    prof.dataset_version, prof.eligible_ref_matches, prof.coverage,
                    Jsonb({"style": prof.style_values, "proficiency": prof.proficiency_values, "public_alias": prof.public_alias, "rights_status": prof.rights_status.value}),
                    Jsonb(prof.distributions), prof.model_version, prof.is_invalidated,
                ),
            )
            return prof
        with self._lock:
            self._pro_profiles.setdefault(prof.reference_id, []).insert(0, prof)
        return prof

    def list_valid_pro_profiles(self, *, game_version: str = "FC27") -> List[ProStyleProfileVersion]:
        gv = "FC26" if game_version.upper() == "FC26" else "FC27"
        if self._use_pg_global():
            rows = db.query(
                """SELECT p.*, r.rights_status
                   FROM public.phase44_professional_style_profile_version p
                   JOIN public.phase44_professional_reference_rights r ON r.reference_id = p.reference_id
                   WHERE p.game_version = %s AND p.is_invalidated = FALSE
                     AND r.rights_status IN ('RIGHTS_VERIFIED', 'RESEARCH_ONLY')
                   ORDER BY p.created_at DESC""",
                (gv,),
            )
            out: List[ProStyleProfileVersion] = []
            seen: set[str] = set()
            for row in rows:
                rid = str(row["reference_id"])
                if rid in seen:
                    continue
                seen.add(rid)
                fv = dict(row.get("feature_vectors_json") or {})
                out.append(
                    ProStyleProfileVersion(
                        pro_profile_id=str(row["pro_profile_id"]),
                        reference_id=rid,
                        public_alias=str(fv.get("public_alias") or rid),
                        rights_status=RightsStatus(row["rights_status"]),
                        game_version=row["game_version"],
                        game_patch=str(row["game_patch"]),
                        dataset_version=str(row["dataset_version"]),
                        eligible_ref_matches=int(row["eligible_ref_matches"]),
                        coverage=float(row["coverage"]),
                        style_values=dict(fv.get("style") or {}),
                        proficiency_values=dict(fv.get("proficiency") or {}),
                        distributions=dict(row.get("distributions_json") or {}),
                        is_invalidated=False,
                    )
                )
            return out
        with self._lock:
            out = []
            for rid, lst in self._pro_profiles.items():
                rt = self._rights.get(rid)
                if not rt or rt.rights_status not in (RightsStatus.RIGHTS_VERIFIED, RightsStatus.RESEARCH_ONLY):
                    continue
                valid = next((p for p in lst if not p.is_invalidated and p.game_version == gv), None)
                if valid:
                    out.append(valid)
            return out

    # ------------------------------------------------------------------ User-Scoped Profiles, Similarity, Evolution & Feedback
    def save_gamer_profile(self, prof: GamerStyleVectorV2) -> GamerStyleVectorV2:
        uid = str(prof.user_id)
        if self._use_pg_user(uid):
            db.execute(
                """INSERT INTO public.phase44_gamer_style_profile_version
                   (profile_version_id, user_id, game_version, game_patch, gameplay_mode,
                    eligible_match_count, synthetic_excluded_count, profile_maturity,
                    overall_coverage, primary_archetype, secondary_archetype,
                    scaler_fit_split, feature_vectors_json, context_summary_json, model_version)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (profile_version_id) DO NOTHING""",
                (
                    prof.profile_version_id, uid, prof.game_version, prof.game_patch, prof.gameplay_mode,
                    prof.eligible_match_count, prof.synthetic_excluded_count, prof.profile_maturity,
                    prof.overall_coverage, prof.archetype.primary_archetype, prof.archetype.secondary_archetype,
                    prof.scaler_fit_split, Jsonb(prof.model_dump(mode="json")), Jsonb(prof.context_summary), prof.model_version,
                ),
            )
            return prof
        with self._lock:
            self._gamer_profiles.setdefault(uid, []).insert(0, prof)
        return prof

    def list_gamer_profiles(self, user_id: str, *, game_version: Optional[str] = None, limit: int = 20) -> List[GamerStyleVectorV2]:
        uid = str(user_id)
        if self._use_pg_user(uid):
            sql = "SELECT feature_vectors_json FROM public.phase44_gamer_style_profile_version WHERE user_id = %s AND is_invalidated = FALSE"
            params: List[Any] = [uid]
            if game_version:
                sql += " AND game_version = %s"
                params.append(game_version.upper())
            sql += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            return [GamerStyleVectorV2(**r["feature_vectors_json"]) for r in db.query(sql, tuple(params))]
        with self._lock:
            items = list(self._gamer_profiles.get(uid, []))
            if game_version:
                items = [x for x in items if x.game_version == game_version.upper()]
            return items[:limit]

    def save_similarity_run(self, rep: ProStyleSimilarityReport) -> ProStyleSimilarityReport:
        uid = str(rep.user_id)
        if self._use_pg_user(uid):
            db.execute(
                """INSERT INTO public.phase44_style_similarity_run
                   (similarity_run_id, user_id, profile_version_id, game_version, game_patch,
                    distance_metric, abstained, abstention_reason, eligible_references_count,
                    uncertainty_notes_json, model_version)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    rep.similarity_run_id, uid, rep.profile_version_id, rep.game_version, rep.game_patch,
                    rep.distance_metric, rep.abstained, rep.abstention_reason, rep.eligible_references_count,
                    Jsonb(rep.uncertainty_summary), "phase44.sim.v1",
                ),
            )
            for m in rep.matches:
                db.execute(
                    """INSERT INTO public.phase44_style_similarity_result
                       (result_id, similarity_run_id, reference_id, rank_position,
                        raw_distance, interpretable_similarity_index, feature_overlap_ratio,
                        confidence_band_json, group_similarities_json,
                        top_similar_features_json, top_divergent_features_json, indistinguishable_note)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        str(uuid4()), rep.similarity_run_id, m.reference_id, m.rank_position,
                        m.raw_distance, m.interpretable_similarity_index, m.feature_overlap_ratio,
                        Jsonb(m.confidence_band), Jsonb(m.group_similarities),
                        Jsonb(m.top_similar_behaviors), Jsonb(m.top_divergent_behaviors), m.indistinguishable_note,
                    ),
                )
            return rep
        with self._lock:
            self._similarity_runs.setdefault(uid, []).insert(0, rep)
        return rep

    def save_feedback(self, rec: StyleRecommendationFeedbackRecord) -> StyleRecommendationFeedbackRecord:
        uid = str(rec.user_id)
        if self._use_pg_user(uid):
            db.execute(
                """INSERT INTO public.phase44_style_recommendation_feedback
                   (feedback_id, user_id, recommendation_id, recommendation_type, game_version,
                    game_patch, user_action, profile_version_id, similarity_run_id, notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    rec.feedback_id, uid, rec.recommendation_id, rec.recommendation_type,
                    rec.game_version, rec.game_patch, rec.user_action,
                    rec.profile_version_id, rec.similarity_run_id, rec.notes,
                ),
            )
            return rec
        with self._lock:
            self._feedback.setdefault(uid, []).insert(0, rec)
        return rec

    def list_feedback(self, user_id: str, *, game_version: Optional[str] = None, limit: int = 50) -> List[StyleRecommendationFeedbackRecord]:
        uid = str(user_id)
        if self._use_pg_user(uid):
            sql = "SELECT * FROM public.phase44_style_recommendation_feedback WHERE user_id = %s"
            params: List[Any] = [uid]
            if game_version:
                sql += " AND game_version = %s"
                params.append(game_version.upper())
            sql += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            return [
                StyleRecommendationFeedbackRecord(
                    feedback_id=str(r["feedback_id"]),
                    user_id=str(r["user_id"]),
                    recommendation_id=str(r["recommendation_id"]),
                    recommendation_type=str(r["recommendation_type"]),
                    game_version=r["game_version"],
                    game_patch=str(r["game_patch"]),
                    user_action=r["user_action"],
                    profile_version_id=r.get("profile_version_id"),
                    similarity_run_id=r.get("similarity_run_id"),
                    notes=str(r.get("notes") or ""),
                    created_at=r["created_at"].isoformat() if hasattr(r.get("created_at"), "isoformat") else str(r.get("created_at") or ""),
                )
                for r in db.query(sql, tuple(params))
            ]
        with self._lock:
            items = list(self._feedback.get(uid, []))
            if game_version:
                items = [f for f in items if f.game_version == game_version.upper()]
            return items[:limit]

    def reset_user_phase44_data(self, user_id: str) -> Dict[str, int]:
        uid = str(user_id)
        if self._use_pg_user(uid):
            with db.get_conn() as conn:
                c_prof = conn.execute("DELETE FROM public.phase44_gamer_style_profile_version WHERE user_id = %s", (uid,)).rowcount
                c_sim = conn.execute("DELETE FROM public.phase44_style_similarity_run WHERE user_id = %s", (uid,)).rowcount
                c_fb = conn.execute("DELETE FROM public.phase44_style_recommendation_feedback WHERE user_id = %s", (uid,)).rowcount
                conn.commit()
            return {"profiles_deleted": c_prof, "similarity_runs_deleted": c_sim, "feedback_deleted": c_fb}
        with self._lock:
            return {
                "profiles_deleted": len(self._gamer_profiles.pop(uid, [])),
                "similarity_runs_deleted": len(self._similarity_runs.pop(uid, [])),
                "feedback_deleted": len(self._feedback.pop(uid, [])),
            }


_SHARED_PHASE44_REPO: Optional[Phase44Repository] = None


def get_phase44_repository() -> Phase44Repository:
    global _SHARED_PHASE44_REPO
    if _SHARED_PHASE44_REPO is None:
        _SHARED_PHASE44_REPO = Phase44Repository()
    return _SHARED_PHASE44_REPO
