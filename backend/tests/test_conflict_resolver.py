"""Source conflict resolution: record, never silently overwrite; field-level
authority beats raw tier order."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.domain.evidence_model import SourceRecord, UsageStatus
from backend.services.conflict_resolver import Claim_, ConflictResolver


def src(sid, tier, usage=UsageStatus.LICENSED, canonical=()):
    return SourceRecord(source_id=sid, name=sid, source_type="CARRIER_DATASET",
                        authority_tier=tier, usage_status=usage,
                        canonical_fields=list(canonical))


@pytest.fixture()
def resolver():
    ea = src("ea_official", 1, UsageStatus.OFFICIAL,
             canonical=["overall_rating", "position_primary"])
    carrier = src("carrier", 3, UsageStatus.LICENSED, canonical=["dribbling_detail"])
    community = src("community", 4, UsageStatus.PUBLIC_REFERENCE)
    research = src("research_only", 3, UsageStatus.RESEARCH_ONLY)
    return ConflictResolver([ea, carrier, community, research])


def test_agreeing_sources_no_conflict(resolver):
    now = datetime.now(timezone.utc)
    r = resolver.resolve("game_player", "x", "overall_rating", [
        Claim_(resolver.sources["ea_official"], 91, now),
        Claim_(resolver.sources["carrier"], 91, now)])
    assert r.conflict is None
    assert r.winner.value == 91


def test_disagreement_prefers_canonical_authority(resolver):
    now = datetime.now(timezone.utc)
    r = resolver.resolve("game_player", "x", "overall_rating", [
        Claim_(resolver.sources["carrier"], 90, now),
        Claim_(resolver.sources["ea_official"], 91, now)])
    assert r.winner.value == 91
    assert r.conflict is not None
    assert r.conflict.resolution == "SOURCE_A_WINS"
    assert r.conflict.value_b == 90 and r.conflict.source_b == "carrier"


def test_field_level_authority_beats_tier(resolver):
    # carrier is canonical for dribbling_detail; EA (tier 1) is not listed for it
    now = datetime.now(timezone.utc)
    r = resolver.resolve("game_player", "x", "dribbling_detail", [
        Claim_(resolver.sources["ea_official"], 88, now),
        Claim_(resolver.sources["carrier"], 90, now)])
    assert r.winner.value == 90
    assert r.conflict is not None


def test_recency_breaks_same_tier(resolver):
    older = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newer = datetime(2026, 6, 1, tzinfo=timezone.utc)
    c1 = src("c_a", 3, UsageStatus.LICENSED)
    c2 = src("c_b", 3, UsageStatus.LICENSED)
    res = ConflictResolver([c1, c2])
    r = res.resolve("game_player", "x", "some_field", [
        Claim_(c1, "old", older), Claim_(c2, "new", newer)])
    assert r.winner.value == "new"


def test_research_only_claims_not_production_winners(resolver):
    now = datetime.now(timezone.utc)
    r = resolver.resolve("game_player", "x", "overall_rating", [
        Claim_(resolver.sources["research_only"], 99, now)])
    assert r.winner is None      # RESEARCH_ONLY cannot win production fields
    assert "no production-permitted claims" in r.reason
