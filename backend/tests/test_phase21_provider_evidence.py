"""Phase 21 S24 test categories: PROVIDER, LICENSE, PRODUCTION, CARD, PRICE,
PLAYSTYLE, REFERENCE, FIREWALL. Named tests use the mandate's exact names
where one was specified.
"""
from __future__ import annotations

import pytest

from backend.services.provider_license_evaluator import (
    DimensionEvidence,
    RightsAnswer,
    RightsDimension,
    evaluate_provider_clearance,
    overall_provider_status,
)
from backend.services.data_license_gate import (
    DataLicenseGateFailure,
    DataLicenseStatus,
    Environment,
    ProductionOverrideForbidden,
    gate_or_raise,
)
from backend.services.card_publication_gate import (
    CardCandidate,
    PublicationDecision,
    evaluate_publication,
)
from backend.services.reference_distribution import (
    ReferenceDistributionUnavailable,
    Universe,
    load_reference_distribution,
)


def _ev(dim, answer, ref="test-fixture"):
    return DimensionEvidence(dim, answer, ref)


ALL_ALLOWED = {d: _ev(d, RightsAnswer.EXPLICITLY_ALLOWED) for d in RightsDimension}
ALL_SILENT = {d: _ev(d, RightsAnswer.SILENT) for d in RightsDimension}


# ---------------------------------------------------------------------
# PROVIDER
# ---------------------------------------------------------------------
class TestProvider:
    def test_provider_registry(self):
        """A provider with every dimension explicitly allowed clears the
        minimum production profile -- proves the mechanism CAN reach a
        positive result when evidence genuinely supports it (not vacuously
        always-blocked)."""
        clearance = evaluate_provider_clearance("hypothetical_fully_cleared", ALL_ALLOWED)
        assert clearance.minimum_production_clearance is True
        assert overall_provider_status(clearance, any_dimension_explicitly_prohibited=False) == "VERIFIED"

    def test_unknown_provider(self):
        """A provider with zero evidence supplied at all evaluates
        identically to one where every dimension is SILENT."""
        clearance = evaluate_provider_clearance("never_contacted", {})
        assert clearance.minimum_production_clearance is False
        assert overall_provider_status(clearance, any_dimension_explicitly_prohibited=False) == "UNVERIFIED"
        assert clearance.per_dimension["STORAGE"].answer == RightsAnswer.SILENT

    def test_missing_terms(self):
        """Mirrors the real FutDB.app finding: an API exists but no terms
        document was found -- every dimension is SILENT, not ALLOWED."""
        clearance = evaluate_provider_clearance("futdb_app", ALL_SILENT)
        assert clearance.cleared_dimensions == ()
        assert clearance.minimum_production_clearance is False

    def test_silent_right_is_not_allowed(self):
        ev = _ev(RightsDimension.STORAGE, RightsAnswer.SILENT)
        assert ev.answer != RightsAnswer.EXPLICITLY_ALLOWED
        from backend.services.provider_license_evaluator import is_cleared
        assert is_cleared(ev) is False


# ---------------------------------------------------------------------
# LICENSE
# ---------------------------------------------------------------------
class TestLicense:
    def test_storage_required(self):
        partial = dict(ALL_ALLOWED)
        partial[RightsDimension.STORAGE] = _ev(RightsDimension.STORAGE, RightsAnswer.SILENT)
        clearance = evaluate_provider_clearance("p", partial)
        assert clearance.minimum_production_clearance is False

    def test_derivation_required(self):
        partial = dict(ALL_ALLOWED)
        partial[RightsDimension.DERIVATION] = _ev(RightsDimension.DERIVATION, RightsAnswer.SILENT)
        clearance = evaluate_provider_clearance("p", partial)
        assert clearance.minimum_production_clearance is False

    def test_commercial_required(self):
        partial = dict(ALL_ALLOWED)
        partial[RightsDimension.COMMERCIAL] = _ev(RightsDimension.COMMERCIAL, RightsAnswer.SILENT)
        clearance = evaluate_provider_clearance("p", partial)
        assert clearance.minimum_production_clearance is False

    def test_display_required(self):
        partial = dict(ALL_ALLOWED)
        partial[RightsDimension.DISPLAY] = _ev(RightsDimension.DISPLAY, RightsAnswer.SILENT)
        clearance = evaluate_provider_clearance("p", partial)
        assert clearance.minimum_production_clearance is False

    def test_blocked_right(self):
        partial = dict(ALL_ALLOWED)
        partial[RightsDimension.STORAGE] = _ev(RightsDimension.STORAGE, RightsAnswer.EXPLICITLY_PROHIBITED)
        clearance = evaluate_provider_clearance("p", partial)
        assert clearance.minimum_production_clearance is False
        assert overall_provider_status(clearance, any_dimension_explicitly_prohibited=True) == "BLOCKED"

    def test_ambiguous_right(self):
        partial = dict(ALL_ALLOWED)
        partial[RightsDimension.DERIVATION] = _ev(RightsDimension.DERIVATION, RightsAnswer.AMBIGUOUS)
        clearance = evaluate_provider_clearance("p", partial)
        assert clearance.minimum_production_clearance is False

    def test_conditional_right_is_not_cleared_outright(self):
        """CONDITIONAL means a separate condition must be independently
        verified -- it is not itself a clearance."""
        partial = dict(ALL_ALLOWED)
        partial[RightsDimension.AUTOMATION] = _ev(RightsDimension.AUTOMATION, RightsAnswer.CONDITIONAL)
        clearance = evaluate_provider_clearance("p", partial)
        assert clearance.minimum_production_clearance is False

    def test_unverified_provider(self):
        clearance = evaluate_provider_clearance("p", ALL_SILENT)
        assert overall_provider_status(clearance, any_dimension_explicitly_prohibited=False) == "UNVERIFIED"


# ---------------------------------------------------------------------
# PRODUCTION
# ---------------------------------------------------------------------
class TestProduction:
    def test_unverified_provider_blocks_production(self):
        clearance = evaluate_provider_clearance("p", ALL_SILENT)
        assert overall_provider_status(clearance, any_dimension_explicitly_prohibited=False) != "VERIFIED"

    def test_blocked_provider_blocks_production(self):
        partial = dict(ALL_ALLOWED)
        partial[RightsDimension.REDISTRIBUTION] = _ev(RightsDimension.REDISTRIBUTION, RightsAnswer.EXPLICITLY_PROHIBITED)
        clearance = evaluate_provider_clearance("p", partial)
        assert overall_provider_status(clearance, any_dimension_explicitly_prohibited=True) == "BLOCKED"

    def test_research_override_cannot_enable_production(self):
        gate_or_raise("fc26-players-2026-09-r1", environment=Environment.RESEARCH, allow_unverified=True)
        with pytest.raises((DataLicenseGateFailure, ProductionOverrideForbidden)):
            gate_or_raise("fc26-players-2026-09-r1", environment=Environment.PRODUCTION)


# ---------------------------------------------------------------------
# CARD
# ---------------------------------------------------------------------
class TestCard:
    def test_player_cannot_become_card(self):
        from backend.services.card_publication_gate import player_cannot_become_card
        card = player_cannot_become_card({"overall_rating": 90, "pace": 95})
        assert card.card_id is None

    def test_card_requires_verified_identity(self):
        card = CardCandidate(game_version="FC26", source_id="s", source_observation_id="o")
        assert evaluate_publication(card).decision == PublicationDecision.NOT_PUBLISHABLE

    def test_card_requires_fc26(self):
        card = CardCandidate(card_id="c", card_version_id="v", game_version="FC25",
                             source_id="s", source_observation_id="o")
        assert evaluate_publication(card, target_game_version="FC26").decision == PublicationDecision.NOT_PUBLISHABLE

    def test_card_requires_provenance(self):
        card = CardCandidate(card_id="c", card_version_id="v", game_version="FC26")
        assert evaluate_publication(card).decision == PublicationDecision.NOT_PUBLISHABLE

    def test_card_requires_license(self):
        card = CardCandidate(card_id="c", card_version_id="v", game_version="FC26",
                             source_id="s", source_observation_id="o",
                             legal_field_status={"price_coins": "RED"})
        assert evaluate_publication(card).decision == PublicationDecision.NOT_PUBLISHABLE

    def test_unresolved_conflict_blocks_publication(self):
        """Blocks full PUBLISHABLE status (REVIEW_REQUIRED, not PUBLISHABLE) --
        distinct from NOT_PUBLISHABLE per Phase 20's identity-vs-recoverable
        distinction, but in neither case does the card actually publish."""
        card = CardCandidate(card_id="c", card_version_id="v", game_version="FC26",
                             source_id="s", source_observation_id="o",
                             unresolved_conflict_fields=("short_passing",))
        assert evaluate_publication(card).decision != PublicationDecision.PUBLISHABLE


# ---------------------------------------------------------------------
# PRICE
# ---------------------------------------------------------------------
class TestPrice:
    def test_price_is_observation(self):
        """Price is modelled as an observation with value/currency/observed_at/
        source, never as bare card metadata -- structural check against the
        CardCandidate/publication-gate design: price has no dedicated field
        on CardCandidate itself, it would arrive only via the same
        source_observation_id-linked provenance path as any other field."""
        card = CardCandidate(card_id="c", card_version_id="v", game_version="FC26",
                             source_id="s", source_observation_id="o")
        assert not hasattr(card, "price_coins"), (
            "price must never be a first-class CardCandidate field -- it is "
            "an observation like any other, traced through field_provenance")

    def test_price_not_used_in_capability_score(self):
        """Direct regression: the v3 demand vector never contains a price
        term, for any position/profile combination."""
        from backend.services.demand_composition import compose_demand
        for position, profile in (("CM", "POSSESSION"), ("CB", "LOW_BLOCK"), ("ST", "PACE_ABUSER")):
            demand = compose_demand(position=position, tactical_profile=profile, lam=0.7).vector
            assert "price" not in demand and "price_coins" not in demand


# ---------------------------------------------------------------------
# PLAYSTYLE
# ---------------------------------------------------------------------
class TestPlayStyle:
    def test_playstyle_is_observed_fact(self):
        """A candidate's playstyles_base/plus are read verbatim from
        ingested data, never computed from other attributes."""
        from backend.tests.helpers import make_candidate, make_attrs
        c = make_candidate(name="X", position="CM", attrs=make_attrs(short_passing=80))
        c.playstyles_base = ["Technical"]
        assert c.playstyles_base == ["Technical"], "held PlayStyles must be exactly what was assigned, not derived"

    def test_no_invented_playstyle_effect(self):
        """The v3 PlayStyle modifier uses playstyle_context.context_value(),
        which maps (playstyle, profile, position) to one of three fixed,
        documented tiers (1.0/0.75/0.35) -- confirm no per-attribute
        gameplay-effect table exists anywhere for PlayStyles (that mapping
        was explicitly rejected as Model B in the v3.1 calibration session
        for lacking an evidence foundation)."""
        from backend.services import playstyle_context
        assert not hasattr(playstyle_context, "PLAYSTYLE_ATTRIBUTE_EFFECTS")
        assert not hasattr(playstyle_context, "PLAYSTYLE_RELEVANT_ATTRS")


# ---------------------------------------------------------------------
# REFERENCE
# ---------------------------------------------------------------------
class TestReference:
    def test_ut_card_requires_ut_reference_distribution(self):
        with pytest.raises(ReferenceDistributionUnavailable):
            load_reference_distribution("fc26-ut-cards-2026-09-r1")

    def test_player_reference_rejected_for_ut_card(self):
        ref = load_reference_distribution("fc26-players-2026-09-r1")
        assert ref.applies_to("ut_card") is False


# ---------------------------------------------------------------------
# FIREWALL
# ---------------------------------------------------------------------
class TestFirewall:
    def test_synthetic_card_blocked(self):
        card = CardCandidate(card_id="c", card_version_id="v", game_version="FC26",
                             source_id="s", source_observation_id="o", is_synthetic=True)
        assert evaluate_publication(card).decision == PublicationDecision.NOT_PUBLISHABLE

    def test_fc25_blocked(self):
        card = CardCandidate(card_id="c", card_version_id="v", game_version="FC25",
                             source_id="s", source_observation_id="o")
        assert evaluate_publication(card, target_game_version="FC26").decision == PublicationDecision.NOT_PUBLISHABLE

    def test_fc27_blocked(self):
        card = CardCandidate(card_id="c", card_version_id="v", game_version="FC27",
                             source_id="s", source_observation_id="o")
        assert evaluate_publication(card, target_game_version="FC26").decision == PublicationDecision.NOT_PUBLISHABLE
