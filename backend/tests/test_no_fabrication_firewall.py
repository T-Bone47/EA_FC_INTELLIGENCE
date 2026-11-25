"""Phase 20 S23 test categories: LICENSE, CARD, PLAYER/CARD, REFERENCE,
PROVENANCE, LEGAL, RELEASE. Named tests from S11/S12 are included verbatim
where the mandate specified an exact test name.
"""
from __future__ import annotations

import pytest

from backend.services.card_publication_gate import (
    CardCandidate,
    PublicationDecision,
    evaluate_publication,
    player_cannot_become_card,
)
from backend.services.data_license_gate import (
    DataLicenseGateFailure,
    DataLicenseStatus,
    Environment,
    ProductionOverrideForbidden,
    evaluate_dataset_release,
    gate_or_raise,
)
from backend.services.reference_distribution import (
    ReferenceDistributionUnavailable,
    Universe,
    load_reference_distribution,
)


# ---------------------------------------------------------------------
# PLAYER/CARD -- no-fabrication firewall (exact names from S11)
# ---------------------------------------------------------------------
class TestNoFabricationFirewall:
    def test_player_cannot_become_card_implicitly(self):
        """A fully-populated player attribute dict must not automatically
        produce a populated card. This is the direct, literal test of the
        mandate's own example (player_id=X, overall=84, pace=91 must not
        produce card_id/card_type/card_version/PlayStyles/Roles/price)."""
        rich_player_attrs = {
            "player_id": "X", "overall_rating": 84, "pace": 91,
            "short_passing": 88, "position_primary": "CM",
        }
        card = player_cannot_become_card(rich_player_attrs)
        assert card.card_id is None
        assert card.card_version_id is None
        assert card.game_version is None
        assert card.legal_field_status == {}
        result = evaluate_publication(card)
        assert result.decision == PublicationDecision.NOT_PUBLISHABLE

    def test_missing_card_id_blocks_publication(self):
        card = CardCandidate(card_version_id="v1", game_version="FC26",
                             source_id="s", source_observation_id="o")
        result = evaluate_publication(card)
        assert result.decision == PublicationDecision.NOT_PUBLISHABLE
        assert any("card_id" in r for r in result.reasons)

    def test_missing_card_version_blocks_publication(self):
        card = CardCandidate(card_id="c1", game_version="FC26",
                             source_id="s", source_observation_id="o")
        result = evaluate_publication(card)
        assert result.decision == PublicationDecision.NOT_PUBLISHABLE
        assert any("card_version_id" in r for r in result.reasons)

    def test_unverified_card_field_is_not_served(self):
        card = CardCandidate(card_id="c1", card_version_id="v1", game_version="FC26",
                             source_id="s", source_observation_id="o",
                             legal_field_status={"price_coins": "UNKNOWN"})
        result = evaluate_publication(card)
        assert result.decision == PublicationDecision.NOT_PUBLISHABLE
        assert any("UNKNOWN" in r for r in result.reasons)

    def test_synthetic_card_never_enters_production(self):
        card = CardCandidate(card_id="c1", card_version_id="v1", game_version="FC26",
                             source_id="s", source_observation_id="o", is_synthetic=True)
        result = evaluate_publication(card)
        assert result.decision == PublicationDecision.NOT_PUBLISHABLE
        assert any("synthetic" in r for r in result.reasons)

    def test_fc25_card_cannot_enter_fc26_scope(self):
        card = CardCandidate(card_id="c1", card_version_id="v1", game_version="FC25",
                             source_id="s", source_observation_id="o")
        result = evaluate_publication(card, target_game_version="FC26")
        assert result.decision == PublicationDecision.NOT_PUBLISHABLE
        assert any("FC25" in r or "does not match" in r for r in result.reasons)

    def test_fully_valid_card_is_publishable(self):
        """Sanity check: the gate is not vacuously always-false -- a card
        with every required field present, provenance attached, correct
        version, not synthetic, and no RED/UNKNOWN fields IS publishable."""
        card = CardCandidate(card_id="c1", card_version_id="v1", game_version="FC26",
                             source_id="s", source_observation_id="o",
                             legal_field_status={"position": "GREEN"})
        result = evaluate_publication(card)
        assert result.decision == PublicationDecision.PUBLISHABLE


# ---------------------------------------------------------------------
# CARD -- version wall, identity, conflicts, provenance
# ---------------------------------------------------------------------
class TestCardCategory:
    def test_fc26_accepted(self):
        card = CardCandidate(card_id="c1", card_version_id="v1", game_version="FC26",
                             source_id="s", source_observation_id="o")
        assert evaluate_publication(card).decision == PublicationDecision.PUBLISHABLE

    def test_fc25_rejected(self):
        card = CardCandidate(card_id="c1", card_version_id="v1", game_version="FC25",
                             source_id="s", source_observation_id="o")
        assert evaluate_publication(card).decision == PublicationDecision.NOT_PUBLISHABLE

    def test_fc27_rejected(self):
        card = CardCandidate(card_id="c1", card_version_id="v1", game_version="FC27",
                             source_id="s", source_observation_id="o")
        assert evaluate_publication(card).decision == PublicationDecision.NOT_PUBLISHABLE

    def test_missing_provenance_rejected(self):
        card = CardCandidate(card_id="c1", card_version_id="v1", game_version="FC26")
        result = evaluate_publication(card)
        assert result.decision == PublicationDecision.NOT_PUBLISHABLE
        assert any("provenance" in r for r in result.reasons)

    def test_unresolved_conflict_is_review_required_not_publishable_outright(self):
        """An unresolved conflict on a non-identity field is recoverable
        (REVIEW_REQUIRED) once resolved -- distinct from a hard,
        unrecoverable block (NOT_PUBLISHABLE). Both withhold publication;
        the mandate requires the distinction be preserved, not collapsed."""
        card = CardCandidate(card_id="c1", card_version_id="v1", game_version="FC26",
                             source_id="s", source_observation_id="o",
                             unresolved_conflict_fields=("short_passing",))
        result = evaluate_publication(card)
        assert result.decision == PublicationDecision.REVIEW_REQUIRED


# ---------------------------------------------------------------------
# REFERENCE -- player distribution cannot score UT cards
# ---------------------------------------------------------------------
class TestReferenceUniverseWall:
    def test_player_reference_cannot_score_ut_cards(self):
        ref = load_reference_distribution("fc26-players-2026-09-r1")
        assert ref.universe == Universe.RATINGS_SITE_PLAYERS
        assert ref.applies_to("ut_card") is False

    def test_ut_card_reference_requires_ut_cards_universe(self):
        """No UT_CARDS-universe reference distribution exists (correctly --
        there is no legitimate card data to build one from). Attempting to
        load one fails explicitly rather than silently substituting the
        player distribution."""
        with pytest.raises(ReferenceDistributionUnavailable):
            load_reference_distribution("fc26-ut-cards-2026-09-r1")


# ---------------------------------------------------------------------
# LEGAL -- field-level release classification
# ---------------------------------------------------------------------
class TestFieldLevelLegality:
    def test_red_field_cannot_be_published(self):
        card = CardCandidate(card_id="c1", card_version_id="v1", game_version="FC26",
                             source_id="s", source_observation_id="o",
                             legal_field_status={"price_coins": "RED"})
        assert evaluate_publication(card).decision == PublicationDecision.NOT_PUBLISHABLE

    def test_unknown_field_cannot_be_published(self):
        card = CardCandidate(card_id="c1", card_version_id="v1", game_version="FC26",
                             source_id="s", source_observation_id="o",
                             legal_field_status={"roles": "UNKNOWN"})
        assert evaluate_publication(card).decision == PublicationDecision.NOT_PUBLISHABLE

    def test_green_field_does_not_block(self):
        card = CardCandidate(card_id="c1", card_version_id="v1", game_version="FC26",
                             source_id="s", source_observation_id="o",
                             legal_field_status={"position": "GREEN"})
        assert evaluate_publication(card).decision == PublicationDecision.PUBLISHABLE

    def test_yellow_field_alone_is_not_modelled_as_a_hard_block(self):
        """YELLOW means 'requires review before use', not 'may be served
        as-is' and not 'automatically rejected' -- this codebase treats it
        as a research-only classification (never reaching this gate at
        all, per FC26_LEGAL_SOURCE_MATRIX.md), so a YELLOW field reaching
        evaluate_publication at all would itself be a pipeline defect
        upstream of this gate, not something this gate is asked to sort out."""
        card = CardCandidate(card_id="c1", card_version_id="v1", game_version="FC26",
                             source_id="s", source_observation_id="o",
                             legal_field_status={"club": "YELLOW"})
        # Documented behaviour: only RED/UNKNOWN are treated as hard blocks
        # here; YELLOW fields should never arrive at this gate in the first
        # place (enforced further upstream, at ingestion).
        assert evaluate_publication(card).decision == PublicationDecision.PUBLISHABLE


# ---------------------------------------------------------------------
# RELEASE -- production publication requires VERIFIED; research mode
# cannot leak into production
# ---------------------------------------------------------------------
class TestReleaseGate:
    def test_production_publication_requires_verified(self):
        with pytest.raises(DataLicenseGateFailure):
            gate_or_raise("fc26-players-2026-09-r1", environment=Environment.PRODUCTION)

    def test_research_mode_cannot_accidentally_enable_production(self):
        """Calling with RESEARCH + allow_unverified never sets any global
        state -- it is a pure function returning a result object. Proven
        here by calling it twice, once RESEARCH and once PRODUCTION, and
        confirming the PRODUCTION call still fails regardless of the
        preceding RESEARCH call."""
        gate_or_raise("fc26-players-2026-09-r1", environment=Environment.RESEARCH, allow_unverified=True)
        with pytest.raises((DataLicenseGateFailure, ProductionOverrideForbidden)):
            gate_or_raise("fc26-players-2026-09-r1", environment=Environment.PRODUCTION)

    def test_direct_lower_layer_injection_still_fails(self):
        """Simulates bypassing the service-level gate entirely and calling
        evaluate_dataset_release directly with the real, current (zero-card)
        state -- it still evaluates BLOCKED, because the decision is a pure
        function of the inputs, not a check that can be routed around by
        skipping a wrapper."""
        result = evaluate_dataset_release(
            dataset_id="fc26-ut-cards-hypothetical", game_version="FC26",
            entity_scope="ut_card", card_count=0,
        )
        assert result.status == DataLicenseStatus.BLOCKED

    def test_missing_license_evidence_blocks(self):
        """FIX verified here: unmeasured coverage (None) must not be treated
        as complete coverage. Before this fix, omitting the measurement was
        the path of least resistance to VERIFIED -- exactly backwards."""
        result = evaluate_dataset_release(
            dataset_id="totally-unregistered", game_version="FC26",
            entity_scope="ut_card", card_count=500, legally_usable_card_count=500,
            provenance_coverage=None, legal_coverage=None,
        )
        assert result.status == DataLicenseStatus.UNVERIFIED
        assert any("not measured" in r for r in result.blocking_reasons)
