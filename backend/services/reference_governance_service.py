"""Phase 44B: Governed Professional Esports Reference Registry & Fail-Closed Rights Validator.

Enforces strict separation between public tournament metadata (EA SPORTS FC Pro) and
authorized gameplay/feature-extraction rights. Never fabricates professional styles or
claims endorsement; defaults strictly fail-closed (`METADATA_ONLY` / `AWAITING_PERMISSION` / `UNKNOWN`).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.domain.phase44_models import (
    ProStyleProfileVersion,
    ProfessionalGamerReference,
    ReferenceMatchRecord,
    ReferenceRightsRecord,
    ReferenceSourceRecord,
    RightsStatus,
    UsagePurpose,
)
from backend.repositories.phase44_repository import Phase44Repository, get_phase44_repository


_SEEDED_SOURCES: List[ReferenceSourceRecord] = [
    ReferenceSourceRecord(
        source_id="SRC-EA-FCPRO-RULES",
        title="EA SPORTS FC Pro Official Portal & FC Pro 26/27 Rules",
        source_type="OFFICIAL_RULES",
        source_url="https://www.ea.com/games/ea-sports-fc/fc-pro",
        license_or_terms="EA Official Competition Rules (Metadata & Nomenclature Only)",
        attribution_required=True,
    ),
    ReferenceSourceRecord(
        source_id="SRC-EA-FCPRO-YOUTUBE",
        title="EA SPORTS FC Pro Official Media Channel (@EASPORTSFCPro)",
        source_type="PUBLIC_COMPETITION_METADATA",
        source_url="https://www.youtube.com/@EASPORTSFCPro",
        license_or_terms="YouTube Developer Policies — Stream visibility does NOT authorize extraction/training",
        attribution_required=True,
    ),
]

# Strictly candidate metadata ONLY — ZERO playing style values, zero unauthorized extraction
_SEEDED_CANDIDATE_PROS: List[Dict[str, Any]] = [
    {"reference_id": "PRO-CAND-VEJRGANG", "public_alias": "Anders Vejrgang", "affiliations": ["EA SPORTS FC Pro"], "notes": "Research candidate metadata; awaiting explicit feature-extraction rights."},
    {"reference_id": "PRO-CAND-TEKKZ", "public_alias": "Tekkz", "affiliations": ["EA SPORTS FC Pro"], "notes": "Research candidate metadata; awaiting explicit feature-extraction rights."},
    {"reference_id": "PRO-CAND-NICOLAS99FC", "public_alias": "Nicolas99fc", "affiliations": ["EA SPORTS FC Pro"], "notes": "Research candidate metadata; awaiting explicit feature-extraction rights."},
    {"reference_id": "PRO-CAND-LEVI", "public_alias": "Levi de Weerd", "affiliations": ["EA SPORTS FC Pro"], "notes": "Research candidate metadata; awaiting explicit feature-extraction rights."},
    {"reference_id": "PRO-CAND-EMRE", "public_alias": "Emre Yilmaz", "affiliations": ["EA SPORTS FC Pro"], "notes": "Research candidate metadata; awaiting explicit feature-extraction rights."},
    {"reference_id": "PRO-CAND-UGUR", "public_alias": "Uğur Mersin", "affiliations": ["EA SPORTS FC Pro"], "notes": "Research candidate metadata; awaiting explicit feature-extraction rights."},
    {"reference_id": "PRO-CAND-PAULO", "public_alias": "Paulo Neto", "affiliations": ["EA SPORTS FC Pro"], "notes": "Research candidate metadata; awaiting explicit feature-extraction rights."},
    {"reference_id": "PRO-CAND-UMUT", "public_alias": "Umut", "affiliations": ["EA SPORTS FC Pro"], "notes": "Research candidate metadata; awaiting explicit feature-extraction rights."},
]


class ReferenceRightsValidator:
    """Fail-closed rights gate verifying every intended purpose independently."""

    @staticmethod
    def is_permitted(
        rights: Optional[ReferenceRightsRecord],
        purpose: UsagePurpose,
        *,
        allow_research_only: bool = True,
    ) -> tuple[bool, str]:
        if rights is None:
            return False, "BLOCKED_MISSING_RIGHTS_RECORD"
        status = rights.rights_status
        if status in (
            RightsStatus.UNKNOWN,
            RightsStatus.AWAITING_PERMISSION,
            RightsStatus.METADATA_ONLY,
            RightsStatus.RESTRICTED,
            RightsStatus.REVOKED,
        ):
            return False, f"BLOCKED_RIGHTS_STATUS:{status.value}"
        if status == RightsStatus.RESEARCH_ONLY and not allow_research_only:
            return False, "BLOCKED_RESEARCH_ONLY_NOT_PERMITTED_FOR_COMMERCIAL"

        flag_map = {
            UsagePurpose.LOCAL_RESEARCH: rights.allow_local_research,
            UsagePurpose.FEATURE_EXTRACTION: rights.allow_feature_extraction,
            UsagePurpose.MODEL_TRAINING: rights.allow_model_training,
            UsagePurpose.COMMERCIAL_INFERENCE: rights.allow_commercial_inference,
            UsagePurpose.PUBLIC_PROFILE_DISPLAY: rights.allow_public_profile_display,
            UsagePurpose.VIDEO_REDISTRIBUTION: rights.allow_video_redistribution,
            UsagePurpose.DERIVED_DATASET_REDISTRIBUTION: rights.allow_derived_dataset_redistribution,
        }
        if not flag_map.get(purpose, False):
            return False, f"BLOCKED_PURPOSE_NOT_AUTHORIZED:{purpose.value}"
        return True, "AUTHORIZED"


class ReferenceSourceRegistry:
    def __init__(self, repo: Optional[Phase44Repository] = None) -> None:
        self.repo = repo or get_phase44_repository()

    def seed_official_sources(self) -> List[ReferenceSourceRecord]:
        return [self.repo.upsert_source(s) for s in _SEEDED_SOURCES]


class ReferenceDatasetManifestService:
    def __init__(self, repo: Optional[Phase44Repository] = None) -> None:
        self.repo = repo or get_phase44_repository()

    def build_manifest(self) -> Dict[str, Any]:
        refs = self.repo.list_references()
        authorized = [r for r in refs if r.rights_status in (RightsStatus.RIGHTS_VERIFIED, RightsStatus.RESEARCH_ONLY)]
        metadata_only = [r for r in refs if r.rights_status in (RightsStatus.METADATA_ONLY, RightsStatus.AWAITING_PERMISSION, RightsStatus.UNKNOWN)]
        revoked = [r for r in refs if r.rights_status in (RightsStatus.REVOKED, RightsStatus.RESTRICTED)]
        return {
            "manifest_version": "phase44.ref_manifest.v1",
            "total_candidates": len(refs),
            "authorized_profile_count": len(authorized),
            "metadata_only_count": len(metadata_only),
            "revoked_or_restricted_count": len(revoked),
            "total_authorized_reference_matches": sum(r.reference_match_count for r in authorized),
            "governance_policy": "Fail-closed rights enforcement; public YouTube/tournament metadata never permits extraction without explicit rights.",
        }


class ProfessionalMatchMetadataRepository:
    def __init__(self, repo: Optional[Phase44Repository] = None) -> None:
        self.repo = repo or get_phase44_repository()

    def ingest_match(self, match: ReferenceMatchRecord) -> ReferenceMatchRecord:
        ref = self.repo.get_reference(match.reference_id)
        ok, reason = ReferenceRightsValidator.is_permitted(
            ref.rights if ref else None, UsagePurpose.FEATURE_EXTRACTION
        )
        if not ok:
            # Store strictly as metadata-only without style features when rights are absent
            sanitized = match.model_copy(
                update={
                    "feature_payload": {},
                    "provenance": reason,
                    "coverage_pct": 0.0,
                }
            )
            return self.repo.add_reference_match(sanitized)
        return self.repo.add_reference_match(match)


class ProfessionalGamerRegistry:
    def __init__(self, repo: Optional[Phase44Repository] = None) -> None:
        self.repo = repo or get_phase44_repository()

    def seed_default_candidates(self) -> List[ProfessionalGamerReference]:
        ReferenceSourceRegistry(self.repo).seed_official_sources()
        existing = {r.reference_id: r for r in self.repo.list_references()}
        out: List[ProfessionalGamerReference] = []
        for cand in _SEEDED_CANDIDATE_PROS:
            rid = cand["reference_id"]
            if rid in existing:
                out.append(existing[rid])
                continue
            ref = ProfessionalGamerReference(
                reference_id=rid,
                public_alias=cand["public_alias"],
                display_name=cand["public_alias"],
                competition_affiliations=cand["affiliations"],
                applicable_editions=["FC26", "FC27"],
                dataset_version="NONE",
                reference_match_count=0,
                evidence_quality="NONE",
                profile_coverage=0.0,
                rights_status=RightsStatus.METADATA_ONLY,
                is_independent_unendorsed=True,
                metadata_notes=cand["notes"],
            )
            rights = ReferenceRightsRecord(
                reference_id=rid,
                source_id="SRC-EA-FCPRO-RULES",
                rights_status=RightsStatus.METADATA_ONLY,
                allow_local_research=False,
                allow_feature_extraction=False,
                allow_model_training=False,
                allow_commercial_inference=False,
                allow_public_profile_display=False,
                allow_video_redistribution=False,
                allow_derived_dataset_redistribution=False,
            )
            out.append(self.repo.upsert_reference(ref, rights))
        return out


class ReferenceProfileBuilder:
    def __init__(self, repo: Optional[Phase44Repository] = None) -> None:
        self.repo = repo or get_phase44_repository()

    def build_profile(
        self,
        reference_id: str,
        *,
        game_version: str = "FC27",
        game_patch: str = "PATCH_1.04",
    ) -> Optional[ProStyleProfileVersion]:
        ref = self.repo.get_reference(reference_id)
        if not ref:
            return None
        ok, _ = ReferenceRightsValidator.is_permitted(ref.rights, UsagePurpose.FEATURE_EXTRACTION)
        if not ok:
            return None
        gv = "FC26" if game_version.upper() == "FC26" else "FC27"
        matches = [
            m for m in self.repo.list_reference_matches(reference_id, game_version=gv)
            if not m.is_invalidated and m.coverage_pct >= 35.0 and m.feature_payload
        ]
        if not matches:
            return None

        acc_style: Dict[str, List[float]] = {}
        acc_prof: Dict[str, List[float]] = {}
        dist_acc: Dict[str, Dict[str, List[float]]] = {}
        for m in matches:
            st_map = m.feature_payload.get("style_features") or m.feature_payload
            pr_map = m.feature_payload.get("proficiency_features") or {}
            for k, v in st_map.items():
                if isinstance(v, (int, float)):
                    acc_style.setdefault(k, []).append(float(v))
            for k, v in pr_map.items():
                if isinstance(v, (int, float)):
                    acc_prof.setdefault(k, []).append(float(v))
            for d_name, d_map in (m.feature_payload.get("distributions") or {}).items():
                if isinstance(d_map, dict):
                    bucket = dist_acc.setdefault(d_name, {})
                    for dk, dv in d_map.items():
                        if isinstance(dv, (int, float)):
                            bucket.setdefault(dk, []).append(float(dv))

        style_vals = {k: round(sum(vs) / len(vs), 4) for k, vs in acc_style.items() if vs}
        prof_vals = {k: round(sum(vs) / len(vs), 4) for k, vs in acc_prof.items() if vs}
        dists = {
            dn: {dk: round(sum(vs) / len(vs), 4) for dk, vs in dm.items()}
            for dn, dm in dist_acc.items()
        }
        mean_cov = round(sum(m.coverage_pct for m in matches) / (len(matches) * 100.0), 4)
        prof = ProStyleProfileVersion(
            reference_id=reference_id,
            public_alias=ref.public_alias,
            rights_status=ref.rights_status,
            game_version=gv,  # type: ignore[arg-type]
            game_patch=game_patch,
            dataset_version=ref.dataset_version,
            eligible_ref_matches=len(matches),
            coverage=mean_cov,
            style_values=style_vals,
            proficiency_values=prof_vals,
            distributions=dists,
        )
        return self.repo.save_pro_profile(prof)


class ProfessionalReferenceRepository:
    """High-level facade coordinating candidate seeding, rights revocation & profile lookup."""

    def __init__(self, repo: Optional[Phase44Repository] = None) -> None:
        self.repo = repo or get_phase44_repository()
        self.registry = ProfessionalGamerRegistry(self.repo)
        self.manifest_svc = ReferenceDatasetManifestService(self.repo)
        self.match_repo = ProfessionalMatchMetadataRepository(self.repo)
        self.profile_builder = ReferenceProfileBuilder(self.repo)

    def ensure_seeded(self) -> None:
        if not self.repo.list_references():
            self.registry.seed_default_candidates()

    def list_candidates(self) -> List[ProfessionalGamerReference]:
        self.ensure_seeded()
        return self.repo.list_references()

    def get_manifest(self) -> Dict[str, Any]:
        self.ensure_seeded()
        return self.manifest_svc.build_manifest()

    def list_eligible_pro_profiles(
        self,
        *,
        game_version: str = "FC27",
        purpose: UsagePurpose = UsagePurpose.LOCAL_RESEARCH,
    ) -> List[ProStyleProfileVersion]:
        self.ensure_seeded()
        profiles = self.repo.list_valid_pro_profiles(game_version=game_version)
        eligible: List[ProStyleProfileVersion] = []
        for p in profiles:
            ref = self.repo.get_reference(p.reference_id)
            ok, _ = ReferenceRightsValidator.is_permitted(ref.rights if ref else None, purpose)
            if ok and not p.is_invalidated:
                eligible.append(p)
        return eligible

    def revoke_rights(self, reference_id: str, reason: str = "Authorization withdrawn") -> Optional[ProfessionalGamerReference]:
        return self.repo.revoke_reference_rights(reference_id, reason=reason)
