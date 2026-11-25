"""Shared, cached loaders for the V3.2 tests (real FC26 foundation / FC27 DB)."""
from __future__ import annotations
from functools import lru_cache

from backend.data_access.foundation_loader import load_foundation_candidates
from backend.services.reference_distribution import load_reference_distribution

FC26_REF = "fc26-players-2026-09-r1"
FC27_REF = "fc27-players-2026-09-r1"


@lru_cache(maxsize=1)
def fc26_pool():
    return load_foundation_candidates("FC26")


@lru_cache(maxsize=1)
def fc26_reference():
    return load_reference_distribution(FC26_REF)


@lru_cache(maxsize=1)
def fc27_reference():
    # FC27 is RESEARCH_ONLY: its frozen distribution is outside the production artifact dir,
    # reachable only through the explicit research gate (same call the lab runner uses).
    from backend.services.reference_distribution import load_reference_for
    ref = load_reference_for("FC27", allow_research_only=True)
    assert ref.version == FC27_REF
    return ref


@lru_cache(maxsize=1)
def fc27_midfield_pool():
    from backend.data_access.candidate_repository import CandidateRepository
    return CandidateRepository().load_candidates(
        "FC27", positions={"CM", "CDM", "CAM"}, include_research_only=True)
