"""Phase 19/20 -- data license release gate tests."""
from __future__ import annotations

import pytest

from backend.services.data_license_gate import (
    DataLicenseGateFailure,
    DataLicenseStatus,
    Environment,
    ProductionOverrideForbidden,
    check_license_gate,
    evaluate_dataset_release,
    gate_or_raise,
)


class TestDataLicenseGate:
    def test_current_foundation_is_unverified_not_verified(self):
        """Do not pretend the licence issue is solved. This must stay
        UNVERIFIED until a human re-retrieves and hashes the raw CC0 files
        (FC26_DATA_GAPS.md G-10)."""
        result = check_license_gate("fc26-players-2026-09-r1")
        assert result.status == DataLicenseStatus.UNVERIFIED
        assert result.release_permitted is False

    def test_unknown_dataset_is_blocked_not_verified(self):
        """Fail closed: a dataset never registered is BLOCKED, not silently
        treated as fine. This also covers the current card scope: zero
        FC26 UT card datasets are registered, so any attempt to gate one
        by name evaluates as BLOCKED, correctly."""
        result = check_license_gate("some-dataset-nobody-registered")
        assert result.status == DataLicenseStatus.BLOCKED
        assert result.release_permitted is False

    def test_gate_or_raise_blocks_by_default_in_production(self):
        with pytest.raises(DataLicenseGateFailure):
            gate_or_raise("fc26-players-2026-09-r1", environment=Environment.PRODUCTION)

    def test_gate_or_raise_requires_explicit_override_in_research(self):
        # succeeds only because allow_unverified=True was passed explicitly,
        # and only because environment is RESEARCH, not PRODUCTION.
        result = gate_or_raise("fc26-players-2026-09-r1", environment=Environment.RESEARCH,
                                allow_unverified=True)
        assert result.status == DataLicenseStatus.UNVERIFIED

    def test_blocked_dataset_cannot_be_overridden_by_allow_unverified(self):
        """allow_unverified must only ever waive UNVERIFIED, never BLOCKED."""
        with pytest.raises(DataLicenseGateFailure):
            gate_or_raise("some-dataset-nobody-registered", environment=Environment.LOCAL,
                          allow_unverified=True)

    def test_production_override_is_structurally_forbidden(self):
        """The Phase 20 hardening: allow_unverified=True combined with
        environment=PRODUCTION must be refused unconditionally, before the
        license status is even consulted -- not merely documented as a
        convention. This is what makes 'may remain available only for
        explicitly local/research workflows' a guarantee."""
        with pytest.raises(ProductionOverrideForbidden):
            gate_or_raise("fc26-players-2026-09-r1", environment=Environment.PRODUCTION,
                          allow_unverified=True)

    def test_production_override_forbidden_even_for_a_dataset_that_would_otherwise_pass(self):
        """The refusal is unconditional on the (environment, override) pair
        alone -- it must not be possible to construct a dataset_version
        whose status happens to make the combination acceptable."""
        with pytest.raises(ProductionOverrideForbidden):
            gate_or_raise("nonexistent-dataset", environment=Environment.PRODUCTION,
                          allow_unverified=True)


class TestEvaluateDatasetRelease:
    """Phase 20 S16. Exercised here against the actual, current state (zero
    card rows) and against constructed hypothetical scenarios to prove the
    decision rule -- not against any real card dataset, because none exists."""

    def test_zero_cards_is_blocked(self):
        """The real, current state of the repository: no FC26 UT card data
        has been legitimately acquired."""
        result = evaluate_dataset_release(
            dataset_id="fc26-ut-cards-hypothetical", game_version="FC26",
            entity_scope="ut_card", card_count=0,
        )
        assert result.status == DataLicenseStatus.BLOCKED
        assert "card_count is 0" in result.blocking_reasons[0]

    def test_red_required_field_with_some_usable_cards_is_partial(self):
        result = evaluate_dataset_release(
            dataset_id="fc26-ut-cards-hypothetical", game_version="FC26",
            entity_scope="ut_card", card_count=1000, legally_usable_card_count=1000,
            provenance_coverage=1.0, legal_coverage=1.0,
            required_fields_with_red_or_unknown_status=("price_coins",),
        )
        assert result.status == DataLicenseStatus.PARTIAL
        assert result.warnings

    def test_red_required_field_with_no_usable_cards_is_blocked(self):
        result = evaluate_dataset_release(
            dataset_id="fc26-ut-cards-hypothetical", game_version="FC26",
            entity_scope="ut_card", card_count=1000, legally_usable_card_count=0,
            required_fields_with_red_or_unknown_status=("card_id",),
        )
        assert result.status == DataLicenseStatus.BLOCKED

    def test_unresolved_conflicts_block_verified_status(self):
        result = evaluate_dataset_release(
            dataset_id="fc26-ut-cards-hypothetical", game_version="FC26",
            entity_scope="ut_card", card_count=1000, legally_usable_card_count=1000,
            unresolved_conflicts=5, provenance_coverage=1.0, legal_coverage=1.0,
        )
        assert result.status == DataLicenseStatus.UNVERIFIED

    def test_incomplete_provenance_blocks_verified_status(self):
        result = evaluate_dataset_release(
            dataset_id="fc26-ut-cards-hypothetical", game_version="FC26",
            entity_scope="ut_card", card_count=1000, legally_usable_card_count=1000,
            provenance_coverage=0.95, legal_coverage=1.0,
        )
        assert result.status == DataLicenseStatus.UNVERIFIED

    def test_full_coverage_no_conflicts_no_red_fields_is_verified(self):
        """The only path to VERIFIED. Constructed here to prove the rule is
        reachable in principle -- not because this describes any real
        dataset in the repository today."""
        result = evaluate_dataset_release(
            dataset_id="fc26-ut-cards-hypothetical", game_version="FC26",
            entity_scope="ut_card", card_count=1000, legally_usable_card_count=1000,
            provenance_coverage=1.0, legal_coverage=1.0, unresolved_conflicts=0,
        )
        assert result.status == DataLicenseStatus.VERIFIED
        assert not result.blocking_reasons
