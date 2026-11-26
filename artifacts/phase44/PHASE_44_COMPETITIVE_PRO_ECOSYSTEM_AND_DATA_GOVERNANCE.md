# Phase 44 Competitive Pro Ecosystem & Data Governance

## 1. Fail-Closed Legal & Rights Policy
- **Primary Governance Rule:** EA SPORTS FC Pro public tournament broadcasts (`@EASPORTSFCPro`), competition portals (`ea.com/games/ea-sports-fc/fc-pro`), and Twitch/YouTube streams do **NOT** grant implied permission to scrape, ingest raw broadcast video, extract behavioral feature vectors, train ML models, or present public pro-player style comparisons (`YouTube Developer Policies`, verified offline-safe).
- **Seeded Baseline Registry (`backend/services/reference_governance_service.py`):**
  - Sources: `SRC-EA-FCPRO-RULES`, `SRC-EA-FCPRO-YOUTUBE`
  - 8 Candidate Entities: `PRO-CAND-VEJRGANG` (Anders Vejrgang), `PRO-CAND-TEKKZ` (Tekkz), `PRO-CAND-NICOLAS99FC` (Nicolas99fc), `PRO-CAND-LEVI` (Levi de Weerd), `PRO-CAND-EMRE` (Emre Yilmaz), `PRO-CAND-UGUR` (Ugur Mersin), `PRO-CAND-PAULO` (Paulo Neto), `PRO-CAND-UMUT` (Umut).
  - Default status: `RightsStatus.METADATA_ONLY` with **all 7 usage flags set to `False`** (`allow_local_research`, `allow_feature_extraction`, `allow_model_training`, `allow_commercial_inference`, `allow_public_profile_display`, `allow_video_redistribution`, `allow_derived_dataset_redistribution`).

## 2. Rights Gate & Revocation Cascade (`ReferenceRightsValidator` & `Phase44Repository`)
- `ReferenceRightsValidator.is_permitted(rights, purpose, allow_research_only=True)` returns `False` with explicit reason (`BLOCKED_MISSING_RIGHTS_RECORD`, `BLOCKED_RIGHTS_STATUS:*`, or `BLOCKED_PURPOSE_NOT_AUTHORIZED:*`) unless status is `RIGHTS_VERIFIED` or `RESEARCH_ONLY` and the specific `UsagePurpose` flag is explicitly `True`.
- `ProfessionalMatchMetadataRepository.ingest_match()` strips `feature_payload` to `{}` and `coverage_pct` to `0.0` automatically if `UsagePurpose.FEATURE_EXTRACTION` is blocked.
- `Phase44Repository.revoke_reference_rights(reference_id, reason)` atomically sets `rights_status = 'REVOKED'`, disables all 7 permission flags, and invalidates (`is_invalidated = TRUE`) downstream `phase44_reference_match` and `phase44_professional_style_profile_version` rows immediately.

## 3. Verified Runtime Manifest State
Observed live via `GET /api/phase44/health`:
- `total_candidates`: `8`
- `authorized_profile_count`: `0`
- `metadata_only_count`: `8`
- `pro_comparison_enabled`: `False`
- `frozen_v321_preserved`: `True`
