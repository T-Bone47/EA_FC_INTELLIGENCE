"""Data license release gate (V3_1_CALIBRATION_REPORT.md Phase 19, extended
in Phase 20/21 for card-scope release evaluation).

Per FC26_DATA_GAPS.md G-10 / FC26_LEGAL_SOURCE_MATRIX.md / Phase 20 source
review: the production player foundation remains UNVERIFIED (unresolved
licence chain), and NO legitimate FC26 UT card-level source was found in
either the original data-forensics session or the refreshed Phase 20
review (see PHASE_20_CARD_DATA_STATUS.md). This module does not resolve
either question -- it is a release-control mechanism that fails closed,
not a legal conclusion and not a workaround.

Phase 20 addition: `evaluate_dataset_release()` gives a full, machine-
readable release evaluation for a candidate dataset (used here to
demonstrate the mechanism against the hypothetical card scope that
currently has zero real rows to evaluate), and `gate_or_raise()` is
hardened so that `allow_unverified=True` can structurally never reach a
production call site -- not merely by convention/comment as in the
original v3.1 version, but by an explicit, required `environment`
argument that the function itself checks.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DataLicenseStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    UNVERIFIED = "UNVERIFIED"
    BLOCKED = "BLOCKED"
    # Phase 22: the licence text IS known and permits non-commercial
    # research/education only (e.g. the FC27 Kaggle snapshot). Never
    # release_permitted; `allow_unverified` does not waive it; only an
    # explicit `allow_research_only=True` outside PRODUCTION does.
    RESEARCH_ONLY = "RESEARCH_ONLY"


class Environment(str, Enum):
    LOCAL = "local"
    RESEARCH = "research"
    PRODUCTION = "production"


def environment_from_settings(name: str | None) -> Environment:
    """Map deployment settings to the licence-gate environment. Anything
    production-like (or unknown) fails closed to PRODUCTION."""
    n = (name or "").strip().lower()
    if n in ("development", "dev", "local", "test"):
        return Environment.LOCAL
    if n == "research":
        return Environment.RESEARCH
    return Environment.PRODUCTION


@dataclass(frozen=True)
class LicenseGateResult:
    status: DataLicenseStatus
    dataset_version: str
    reason: str
    release_permitted: bool


@dataclass(frozen=True)
class DatasetReleaseEvaluation:
    """Full machine-readable release evaluation (Phase 20 S16)."""
    status: DataLicenseStatus
    dataset_id: str
    game_version: str
    entity_scope: str
    card_count: int
    legally_usable_card_count: int
    provenance_coverage: Optional[float]      # fraction [0,1], None if not applicable
    legal_coverage: Optional[float]           # fraction of fields classified GREEN, None if n/a
    unresolved_conflicts: int
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    evaluated_at: str


@dataclass(frozen=True)
class DatasetLicenseEntry:
    status: DataLicenseStatus
    game_version: str
    entity_scope: str
    reason: Optional[str] = None


# Per-dataset-version registration, scoped to (game_version, entity_scope).
# Single source of truth for release gating. Updated by a human, with
# evidence, when a chain is actually verified -- never inferred or assumed.
# FC26 and FC27, player and card scopes, are independent entries: a status
# for one never implies anything for another.
_DATASET_LICENSE_REGISTRY: dict[str, DatasetLicenseEntry] = {
    "fc26-players-2026-09-r1": DatasetLicenseEntry(
        DataLicenseStatus.UNVERIFIED, "FC26", "game_player"),
    # Phase 22: FC27 Kaggle snapshot (mikedpad, v4, snapshot 2026-09-12).
    # Its own licence text: "unofficial, non-commercial snapshot for
    # analysis and education". Known restriction, not an unverified chain.
    "fc27-players-2026-09-r1": DatasetLicenseEntry(
        DataLicenseStatus.RESEARCH_ONLY, "FC27", "game_player",
        "FC27 player ratings snapshot whose licence text permits non-commercial "
        "analysis and education only (Kaggle mikedpad/ea-sports-fc27-player-ratings "
        "v4). Research/validation use outside production only; never releasable "
        "without a separately obtained licence."),
    # No UT card dataset (FC26 or FC27) is registered. There are zero real
    # rows to register a status for -- see PHASE_20_CARD_DATA_STATUS.md. Any
    # dataset_version not listed here evaluates as BLOCKED (see
    # check_license_gate below), which correctly covers the card case
    # without a placeholder entry that could be mistaken for one.
}

# Backward-compatible read-only view (dataset_version -> status).
_DATASET_LICENSE_STATUS: dict[str, DataLicenseStatus] = {
    k: v.status for k, v in _DATASET_LICENSE_REGISTRY.items()}

_REASONS = {
    DataLicenseStatus.VERIFIED: "raw source files hash-verified against the recorded manifest",
    DataLicenseStatus.PARTIAL: (
        "some legitimate fields are usable but the full contract for this "
        "entity scope cannot be supported -- see blocking_reasons for what "
        "is withheld"
    ),
    DataLicenseStatus.UNVERIFIED: (
        "production foundation is an exact 16,228/16,228 ID-set match to a GPL-3, "
        "RESEARCH_ONLY-classified dataset (flynn28/eafc26-player-database); the "
        "three raw CC0 files named in the original ingestion manifest are not "
        "present in the repository, so the claimed independent chain is unverified. "
        "See FC26_DATA_GAPS.md G-10."
    ),
    DataLicenseStatus.BLOCKED: "explicitly blocked by legal review; do not ingest or release",
    DataLicenseStatus.RESEARCH_ONLY: (
        "licence permits non-commercial research/education only; never releasable "
        "to production"
    ),
}


def check_license_gate(dataset_version: str, *, game_version: Optional[str] = None,
                       entity_scope: Optional[str] = None) -> LicenseGateResult:
    """The release-control check. A CI/deploy step calls this and fails
    closed (does not ship) on anything other than VERIFIED, unless an
    explicit, logged override is supplied -- see gate_or_raise below.

    When `game_version` / `entity_scope` are given they must match the
    registration exactly; a dataset registered for (FC26, game_player) is
    BLOCKED when asked about as FC27 or as ut_card."""
    entry = _DATASET_LICENSE_REGISTRY.get(dataset_version)
    if entry is None:
        return LicenseGateResult(
            status=DataLicenseStatus.BLOCKED, dataset_version=dataset_version,
            reason=f"no license status recorded for dataset_version={dataset_version!r} "
                   f"-- unregistered datasets are treated as BLOCKED, not VERIFIED",
            release_permitted=False,
        )
    mismatch = []
    if game_version is not None and str(game_version).strip().upper() != entry.game_version:
        mismatch.append(f"game_version {game_version!r} != registered {entry.game_version}")
    if entity_scope is not None and entity_scope != entry.entity_scope:
        mismatch.append(f"entity_scope {entity_scope!r} != registered {entry.entity_scope}")
    if mismatch:
        return LicenseGateResult(
            status=DataLicenseStatus.BLOCKED, dataset_version=dataset_version,
            reason="; ".join(mismatch) + " -- a registration never covers another "
                   "version or scope",
            release_permitted=False,
        )
    return LicenseGateResult(
        status=entry.status, dataset_version=dataset_version,
        reason=entry.reason or _REASONS[entry.status],
        release_permitted=(entry.status == DataLicenseStatus.VERIFIED),
    )


def catalogue_releases(environment: Environment) -> dict[str, dict[str, str]]:
    """Select unambiguous serving releases from the reviewed registry."""
    available: dict[tuple[str, str], list[str]] = {}
    for version, entry in _DATASET_LICENSE_REGISTRY.items():
        if entry.status == DataLicenseStatus.VERIFIED or (
            environment == Environment.RESEARCH and entry.status == DataLicenseStatus.RESEARCH_ONLY
        ):
            available.setdefault((entry.game_version, entry.entity_scope), []).append(version)
    result: dict[str, dict[str, str]] = {}
    for (game_version, scope), versions in available.items():
        if len(versions) == 1:
            result.setdefault(game_version, {})[scope] = versions[0]
    return result


def catalogue_release_permitted(game_version: str, entity_scope: str) -> bool:
    return entity_scope in catalogue_releases(Environment.PRODUCTION).get(game_version, {})


class DataLicenseGateFailure(Exception):
    pass


class ProductionOverrideForbidden(Exception):
    """Raised if any call site attempts allow_unverified=True together with
    environment=PRODUCTION. This is a hard, structural refusal, not a
    documentation convention -- Phase 20 S15 requires that an override
    "may remain available only for explicitly local/research workflows"
    and this is what makes that a guarantee rather than a comment."""


def gate_or_raise(dataset_version: str, *, environment: Environment,
                   allow_unverified: bool = False, allow_research_only: bool = False,
                   game_version: Optional[str] = None,
                   entity_scope: Optional[str] = None) -> LicenseGateResult:
    """Raises unless the gate passes. `environment` is REQUIRED (no
    default) so every call site must state which environment it is
    running in. `allow_unverified=True` or `allow_research_only=True`
    combined with `environment=PRODUCTION` is refused unconditionally,
    before the license status is even consulted -- there is no code path by
    which a production caller can waive this gate.

    Each override waives exactly one status: allow_unverified waives
    UNVERIFIED only, allow_research_only waives RESEARCH_ONLY only. BLOCKED
    (including unregistered and version/scope-mismatched datasets) is never
    waivable."""
    if (allow_unverified or allow_research_only) and environment == Environment.PRODUCTION:
        raise ProductionOverrideForbidden(
            "allow_unverified/allow_research_only=True is not permitted with "
            "environment=PRODUCTION. These overrides exist only for local/research "
            "workflows; production releases must clear the gate on VERIFIED status alone."
        )
    result = check_license_gate(dataset_version, game_version=game_version,
                                entity_scope=entity_scope)
    waived = ((allow_unverified and result.status == DataLicenseStatus.UNVERIFIED)
              or (allow_research_only and result.status == DataLicenseStatus.RESEARCH_ONLY))
    if not result.release_permitted and not waived:
        raise DataLicenseGateFailure(
            f"data license gate failed for {dataset_version!r}: {result.status.value} -- {result.reason}"
        )
    return result


def evaluate_dataset_release(
    *,
    dataset_id: str,
    game_version: str,
    entity_scope: str,
    card_count: int = 0,
    legally_usable_card_count: int = 0,
    provenance_coverage: Optional[float] = None,
    legal_coverage: Optional[float] = None,
    unresolved_conflicts: int = 0,
    required_fields_with_red_or_unknown_status: tuple[str, ...] = (),
    evidence_refs: tuple[str, ...] = (),
) -> DatasetReleaseEvaluation:
    """Phase 20 S16: full machine-readable release evaluation.

    Decision rule (Phase 20 S15):
      VERIFIED only if: card_count > 0, every required field clears GREEN
        (required_fields_with_red_or_unknown_status is empty), no
        unresolved conflicts block serving, and legal+provenance coverage
        are both 100%.
      PARTIAL if: some legitimate fields are usable (legally_usable_card_count
        > 0) but the full contract cannot be met (some required fields are
        RED/UNKNOWN, or coverage is incomplete).
      UNVERIFIED if: cards exist but legal/provenance evidence is
        incomplete in a way that isn't yet a hard block.
      BLOCKED if: card_count == 0 (nothing to evaluate -- this is the
        current, actual state of the repository) or a required field is
        explicitly RED/prohibited rather than merely unverified.
    """
    blocking: list[str] = []
    warnings: list[str] = []

    if card_count == 0:
        blocking.append(
            "card_count is 0: no FC26 UT card data has been legitimately "
            "acquired. There is nothing to release. See PHASE_20_CARD_DATA_STATUS.md."
        )
        status = DataLicenseStatus.BLOCKED
    elif required_fields_with_red_or_unknown_status:
        blocking.append(
            f"required field(s) classified RED/UNKNOWN and cannot be published: "
            f"{', '.join(required_fields_with_red_or_unknown_status)}"
        )
        if legally_usable_card_count > 0:
            status = DataLicenseStatus.PARTIAL
            warnings.append(
                f"{legally_usable_card_count}/{card_count} cards have a legally "
                f"usable field subset; the full card-intelligence contract cannot "
                f"be met until the blocked fields are cleared"
            )
        else:
            status = DataLicenseStatus.BLOCKED
    elif unresolved_conflicts > 0:
        blocking.append(f"{unresolved_conflicts} unresolved field conflict(s) block serving")
        status = DataLicenseStatus.UNVERIFIED
    elif provenance_coverage is None or legal_coverage is None:
        # FAIL CLOSED: unmeasured evidence is not the same as complete
        # evidence. A caller that never measured coverage must not reach
        # VERIFIED merely by omitting the measurement -- that would make
        # "don't check" the path of least resistance to a release.
        missing = [n for n, v in (("provenance_coverage", provenance_coverage),
                                   ("legal_coverage", legal_coverage)) if v is None]
        blocking.append(f"required evidence not measured: {', '.join(missing)}")
        status = DataLicenseStatus.UNVERIFIED
    elif provenance_coverage < 1.0:
        blocking.append(f"provenance coverage {provenance_coverage:.1%} < 100%")
        status = DataLicenseStatus.UNVERIFIED
    elif legal_coverage < 1.0:
        blocking.append(f"legal coverage {legal_coverage:.1%} < 100%")
        status = DataLicenseStatus.UNVERIFIED
    else:
        status = DataLicenseStatus.VERIFIED

    return DatasetReleaseEvaluation(
        status=status, dataset_id=dataset_id, game_version=game_version,
        entity_scope=entity_scope, card_count=card_count,
        legally_usable_card_count=legally_usable_card_count,
        provenance_coverage=provenance_coverage, legal_coverage=legal_coverage,
        unresolved_conflicts=unresolved_conflicts,
        blocking_reasons=tuple(blocking), warnings=tuple(warnings),
        evidence_refs=evidence_refs,
        evaluated_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
    )
