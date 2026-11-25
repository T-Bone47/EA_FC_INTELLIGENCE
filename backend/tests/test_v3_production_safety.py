"""DB-gated regression tests for the four defects proven live against the
real PostgreSQL instance during this implementation session
(IMPLEMENTATION_BASELINE.md / IMPLEMENTATION_REPORT.md). Each test
reconstructs the exact adversarial scenario used for the live proof.
"""
from __future__ import annotations

import uuid

import pytest

from backend.tests.conftest import requires_db

pytestmark = requires_db


class TestSyntheticFirewall:
    def test_mismatched_synthetic_row_is_never_served(self):
        """The measured defect: is_synthetic=TRUE with data_status='CANONICAL'
        was served by production load_cards() (1 leaked row, proven live).
        Two independent layers now block it: the corrected query predicate,
        and the DB-level CHECK constraint added in migration 006."""
        from backend.core.db import get_conn
        from backend.data_access.candidate_repository import CandidateRepository

        with get_conn() as conn:
            gv_id = conn.execute("SELECT id FROM game_version WHERE code='FC26'").fetchone()["id"]

            # Layer 1: the CHECK constraint must reject the mismatch outright.
            with pytest.raises(Exception, match="synthetic_status_consistent"):
                conn.execute("""
                    INSERT INTO ut_card (game_version_id, source_id, source_card_id,
                                          card_name, position, overall_rating,
                                          is_synthetic, data_status)
                    VALUES (%s, 'synthetic_fixtures', %s, 'Adversarial', 'ST', 99, TRUE, 'CANONICAL')
                """, (gv_id, f"ADV-{uuid.uuid4()}"))
            conn.rollback()

        # Layer 2: the repository query must never serve a synthetic row.
        # Verified against the real synthetic fixtures already ingested by
        # scripts/ingest_synthetic_cards.py.
        repo = CandidateRepository()
        cards = repo.load_cards("FC26")
        assert all(not c.is_synthetic for c in cards), (
            "a synthetic card reached the production read path")


class TestConflictResolverUnresolvedPath:
    def test_equal_authority_material_disagreement_is_unresolved(self):
        """The exact worked example from FC26_CONFLICT_RESOLUTION_SPEC.md:
        two equal-tier sources disagree by one point on an attribute with
        zero tolerance. The old resolver always returned SOURCE_A_WINS here
        (alphabetical), never UNRESOLVED."""
        from datetime import datetime, timezone
        from backend.services.conflict_resolver import ConflictResolver, Claim_
        from backend.domain.evidence_model import SourceRecord, UsageStatus

        def src(sid):
            return SourceRecord(source_id=sid, name=sid, source_type="dataset",
                                 authority_tier=2, canonical_fields=["short_passing"],
                                 usage_status=UsageStatus.LICENSED)

        resolver = ConflictResolver([src("source_a"), src("source_b")])
        t = datetime(2026, 9, 1, tzinfo=timezone.utc)
        res = resolver.resolve("game_player", "p1", "short_passing",
                                [Claim_(src("source_a"), 91, t), Claim_(src("source_b"), 92, t)])
        assert res.winner is None
        assert res.conflict.resolution == "UNRESOLVED"

    def test_genuine_authority_difference_still_resolves(self):
        from datetime import datetime, timezone
        from backend.services.conflict_resolver import ConflictResolver, Claim_
        from backend.domain.evidence_model import SourceRecord, UsageStatus

        def src(sid, tier):
            return SourceRecord(source_id=sid, name=sid, source_type="dataset",
                                 authority_tier=tier, canonical_fields=["short_passing"],
                                 usage_status=UsageStatus.LICENSED)

        resolver = ConflictResolver([src("source_a", 1), src("source_b", 3)])
        t = datetime(2026, 9, 1, tzinfo=timezone.utc)
        res = resolver.resolve("game_player", "p1", "short_passing",
                                [Claim_(src("source_a", 1), 91, t), Claim_(src("source_b", 3), 92, t)])
        assert res.winner is not None and res.winner.value == 91
        assert res.conflict.resolution == "SOURCE_A_WINS"


class TestCardIdentityCollision:
    def test_both_discriminators_absent_withholds_identity(self):
        """Two genuinely different promo items for the same player, position
        and release group, both with card_type and rarity unpublished, must
        NOT silently collide into one canonical card."""
        from backend.domain.card_model import UTCard

        id_a = UTCard.compute_canonical_id("FC26", "sp:111", None, None, "ST", "wave1")
        id_b = UTCard.compute_canonical_id("FC26", "sp:111", None, None, "ST", "wave1")
        assert id_a is None and id_b is None

    def test_one_discriminator_present_still_resolves(self):
        from backend.domain.card_model import UTCard

        gold = UTCard.compute_canonical_id("FC26", "sp:111", None, "gold", "ST", None)
        totw = UTCard.compute_canonical_id("FC26", "sp:111", "TOTW", None, "ST", None)
        assert gold is not None and totw is not None and gold != totw


class TestFieldProvenanceTrace:
    def test_attribute_traces_to_source_observation(self):
        """The literal question the mission statement poses: 'why do we
        believe this card has 92 short passing?' must be answerable with a
        trace, not an assurance."""
        from backend.core.db import get_conn

        with get_conn() as conn:
            row = conn.execute("""
                SELECT fp.observed_value, fp.source_id, so.observed_at, sr.license
                FROM field_provenance fp
                JOIN source_observation so ON so.id = fp.source_observation_id
                JOIN source_registry sr ON sr.source_id = fp.source_id
                WHERE fp.canonical_field = 'short_passing'
                LIMIT 1
            """).fetchone()
        assert row is not None, "no field_provenance rows found -- run scripts/build_field_provenance_v3.py"
        assert row["observed_value"] is not None
        assert row["source_id"] is not None
        assert row["observed_at"] is not None
        assert row["license"] is not None


class TestTeamFitLeagueFix:
    def test_league_link_counts_the_candidate_not_itself(self):
        from backend.services.fit_components import team_fit
        from backend.services.scoring_config import ScoringConfig
        from backend.tests.helpers import make_candidate, make_attrs, make_req

        candidate = make_candidate(name="Foreign", position="CM", ovr=84,
                                    attrs=make_attrs(short_passing=80))
        candidate.league = "Serie A"

        class FakeSlot:
            def __init__(self, league):
                self.league, self.club, self.nation = league, None, None

        class FakeSquadCtx:
            def __init__(self, slots):
                self._slots = slots

            def filled_slots(self):
                return self._slots

        ctx = FakeSquadCtx([FakeSlot(league="Premier League"), FakeSlot(league="La Liga")])
        result = team_fit(candidate, make_req(position="CM"), ctx, ScoringConfig())
        assert "league: 0" in str(result.evidence)
