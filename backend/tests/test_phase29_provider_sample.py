"""Synthetic validation of the offline evaluation only."""
import pytest

from scripts.compare_fc27_provider_sample import (
    demanded, fut_paths, identity_checks, observed_stat, quote_checks, sample_index, timestamp,
)


def test_observation_counts_respect_engine_demand_and_namespaces():
    assert set(demanded("GK")) == {"gk_diving", "gk_handling", "gk_kicking", "gk_positioning", "gk_reflexes"}
    paths = fut_paths()
    for position in ("GK", "ST", "RW"):
        assert set(demanded(position)) <= paths.keys()
    assert observed_stat({"positioning": 91}, paths["gk_positioning"]) is None
    assert observed_stat({"goalkeeperAttributes": {"positioning": 57}}, paths["gk_positioning"]) == 57
    assert observed_stat({"pace": True}, paths["pace"]) is None
    assert observed_stat({"pace": 100}, paths["pace"]) is None


CARD = dict(player_name="Test Player", full_name="Test Player", club="Test FC", league="League",
            nation="Nation", positions="RW, RM", overall="85", eaId="42", rarity="Star Performer")


def test_matching_ids_ratings_and_names_do_not_override_conflicting_version():
    details = dict(resourceId=42, resourceBaseId=11, futBinId=42, name="Test Player", rating=85,
                   version="27", position="RW")
    entry = dict(ea_id=42, player_id=11, futbin_id=42, name="Test Player", club="Test FC", league="League",
                 nation="Nation", rating=85, position="RW", rarity_name="Star Performer")
    assert identity_checks(CARD, 11, details, entry, False) == []
    assert "RARITY_UNVERIFIED" in identity_checks(CARD, 11, details, dict(entry, rarity_name="Rare"), False)
    assert "FUTDB_ID_CONFLICT" in identity_checks(CARD, 11, dict(details, resourceBaseId=42), entry, False)
    assert "ILLUSTRATIVE_CATALOGUE" in identity_checks(CARD, 11, details, entry, True)
    with pytest.raises(ValueError, match="Duplicate"):
        sample_index([entry, entry], "ea_id")


@pytest.mark.parametrize(("changes", "issue"), [
    ({"game": "fc26"}, "GAME_OR_ITEM_MISMATCH"),
    ({"ea_id": 11}, "GAME_OR_ITEM_MISMATCH"),
    ({"market": "console"}, "PLATFORM_MISMATCH"),
    ({"observed_at": "2026-11-24T10:00:00Z"}, "INVALID_TIME"),
    ({"observed_at": "2026-11-23T10:00:00"}, "INVALID_TIME"),
    ({"observed_at": "2026-09-01T10:00:00Z"}, "OUTSIDE_FRESHNESS_WINDOW"),
    ({"futbin_updated_at": "2026-09-01T10:00:00Z"}, "SOURCE_TIMESTAMP_UNUSABLE"),
    ({"price": 0}, "NO_LISTED_PRICE"), ({"exact": False}, "PENDING_OR_INEXACT"),
    ({"club": "Other FC"}, "CLUB_MISMATCH"),
])
def test_price_checks(changes, issue):
    at = "2026-11-23T10:00:00Z"
    quote = dict(name="Test Player", club="Test FC", game="fc27", ea_id=42, rating=85, position="RW",
                 market="pc", platform="pc", price=100, availability="listed", observed_at=at,
                 checked_at=at, stale=False, pending=False, exact=True)
    assert quote_checks(quote, CARD, timestamp(at), False) == []
    assert quote_checks(quote, CARD, timestamp(at), True) == ["ILLUSTRATIVE_SANDBOX"]
    assert issue in quote_checks(dict(quote, **changes), CARD, timestamp(at), False)
