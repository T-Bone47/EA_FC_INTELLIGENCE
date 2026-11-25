# PHASE 20 RELEASE GATE

## What was built

Extended `backend/services/data_license_gate.py` (previously `VERIFIED | UNVERIFIED | BLOCKED`, dataset-scoped only) with:

**`DataLicenseStatus.PARTIAL`** — some legitimate fields usable, full contract not supportable.

**`evaluate_dataset_release()`** — full machine-readable evaluation:
```python
DatasetReleaseEvaluation(
    status, dataset_id, game_version, entity_scope,
    card_count, legally_usable_card_count,
    provenance_coverage, legal_coverage, unresolved_conflicts,
    blocking_reasons, warnings, evidence_refs, evaluated_at,
)
```
Decision rule: `card_count == 0` → BLOCKED (the actual current state). A required field classified RED/UNKNOWN → PARTIAL if some cards remain usable, else BLOCKED. Unresolved conflicts → UNVERIFIED. **Unmeasured coverage (`None`) → UNVERIFIED, never treated as passing** — this was a real bug caught and fixed during this session's own testing (see below).

**`gate_or_raise(dataset_version, *, environment, allow_unverified=False)`** — `environment` is now a required keyword argument. `allow_unverified=True` combined with `environment=PRODUCTION` raises `ProductionOverrideForbidden` **unconditionally, before the dataset's status is even looked up** — this is a structural guarantee, not a comment asking callers to be careful. The mandate's requirement ("`allow_unverified=True` must never activate production serving... may remain available only for explicitly local/research workflows") is enforced in code, not in documentation.

## A bug this session found in its own new code, and fixed before shipping it

The first version of `evaluate_dataset_release()` skipped the coverage check entirely when `provenance_coverage` or `legal_coverage` was `None` (never measured) — which meant a caller could reach `VERIFIED` status simply by *not measuring* coverage, the exact opposite of fail-closed. Caught by a test written against the mandate's own "missing license evidence blocks" requirement, fixed so `None` now routes to `UNVERIFIED` with an explicit "required evidence not measured" reason. Documented here rather than silently corrected, per this project's standing practice of surfacing its own mistakes.

## Multi-layer enforcement, proven independently at each layer

| Layer | Mechanism | Proof |
|---|---|---|
| Repository | `CandidateRepository.load_cards()` returns only `is_synthetic=false` rows | Returns 0 rows against the live database (60 total, all synthetic) |
| License gate | `check_license_gate()` on any card dataset name | Returns `BLOCKED` — no card dataset is registered, and unregistered = BLOCKED by default, never VERIFIED |
| Engine | `RecommendationEngineV3.recommend()` | Raises `UnsupportedEntityScopeError` for `entity_scope="ut_card"` |
| Service | `RecommendationServiceV3.recommend` | Structurally never calls `load_cards` (confirmed by reading its source, not just its output) |
| API | `RecommendationRequestV3.entity_scope: Literal["game_player"]` | `ut_card` request is a 422 from Pydantic before any handler code runs |

Each layer reaches the same conclusion **independently** — confirmed by testing the repository and license-gate layers directly in this session, not merely inferring it from the API's behaviour. A single forgotten check at any one layer would not expose card data, because every other layer still blocks it on its own.

## Publication gate (`card_publication_gate.py`)

`PUBLISHABLE | REVIEW_REQUIRED | NOT_PUBLISHABLE`, per card, given required identity fields, provenance, exact version match, non-synthetic status, and per-field legal classification. A card with an unresolved conflict on a non-identity field is `REVIEW_REQUIRED` (recoverable); a card missing an identity field, synthetic, wrong-version, or carrying a RED/UNKNOWN required field is `NOT_PUBLISHABLE` (a hard block) — the two are kept distinct per the mandate, not collapsed into one refusal category.

## Current gate state

```
check_license_gate("fc26-players-2026-09-r1") = UNVERIFIED   (player scope, unchanged)
check_license_gate(<any card dataset name>)   = BLOCKED       (no card dataset registered)
evaluate_dataset_release(card_count=0, ...)   = BLOCKED       (the real, current evaluation)
```
