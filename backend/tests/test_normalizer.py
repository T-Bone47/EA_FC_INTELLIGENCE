"""Normalizer: deterministic IDs, UNKNOWN preservation, version guards."""
from __future__ import annotations

import uuid

import pytest

from backend.domain.card_model import DataStatus
from backend.ingestion.adapter import RawCardRecord, RawPlayerRecord
from backend.ingestion.normalizer import Normalizer, normalize_name, parse_playstyle_list


@pytest.fixture()
def norm():
    return Normalizer("test_source", "FC26")


def test_normalize_name_conservative():
    assert normalize_name("Kylian Mbappé") == "kylian mbappe"
    assert normalize_name("  C.   Ronaldo-dos Santos Aveiro ") == "c ronaldo dos santos aveiro"
    assert normalize_name("") == ""


def test_player_id_deterministic(norm):
    a = norm.game_player_id(209331)
    b = norm.game_player_id(209331)
    c = norm.game_player_id(209332)
    assert a == b and a != c
    n27 = Normalizer("test_source", "FC27")
    assert n27.game_player_id(209331) != a     # version-scoped identity


def test_missing_values_stay_none(norm):
    raw = RawPlayerRecord(
        source_player_id=1, names={"first": "Empty", "last": "Fields"},
        position_raw="cm", overall_rating=None,
        attributes={"pace": "", "stamina": None, "vision": "88"})
    gp = norm.normalize_player(raw)
    assert gp.overall_rating is None                 # UNKNOWN, not 0
    assert gp.attributes.get("pace") is None
    assert gp.attributes.get("stamina") is None
    assert gp.attributes.get("vision") == 88
    assert gp.position_primary == "CM"


def test_version_contamination_rejected(norm):
    raw = RawPlayerRecord(source_player_id=1, names={"first": "A", "last": "B"},
                          position_raw="CM", overall_rating=80,
                          extras={"game_version": "FC27"})
    with pytest.raises(ValueError, match="contamination"):
        norm.normalize_player(raw)


def test_card_deterministic_id_and_version_hash(norm):
    raw = RawCardRecord(source_card_id="C1", card_name="Test Card",
                        position_raw="ST", rarity_raw="GOLD", overall_rating=85,
                        attributes={"pace": "90"}, playstyles_raw="Rapid, Quick Step",
                        playstyles_plus_raw="Rapid+")
    card = norm.normalize_card(raw)
    again = norm.normalize_card(raw)
    assert card.id == again.id                       # idempotent card_id
    v1, v2 = norm.card_version(card), norm.card_version(again)
    assert v1.id == v2.id and v1.content_hash == v2.content_hash
    # genuine content change -> new version id
    raw2 = RawCardRecord(source_card_id="C1", card_name="Test Card",
                         position_raw="ST", rarity_raw="GOLD", overall_rating=86,
                         attributes={"pace": "90"})
    v3 = norm.card_version(norm.normalize_card(raw2))
    assert v3.id != v1.id
    assert card.playstyles_plus == ["Rapid"]         # '+' stripped
    assert card.rarity == "gold"
    assert card.price_coins is None                  # UNKNOWN, never 0


def test_synthetic_source_marks_firewall(norm):
    synth = Normalizer("synthetic_fixtures", "FC26")
    card = synth.normalize_card(RawCardRecord(
        source_card_id="X", card_name="Synth", position_raw="ST",
        overall_rating=80, extras={"data_status": "SYNTHETIC_TEST"}))
    assert card.is_synthetic and card.data_status == DataStatus.SYNTHETIC_TEST
    normal = norm.normalize_card(RawCardRecord(
        source_card_id="Y", card_name="Real", position_raw="ST", overall_rating=80))
    assert not normal.is_synthetic and normal.data_status == DataStatus.CANONICAL


def test_playstyle_list_parsing():
    assert parse_playstyle_list("Rapid, Quick Step+") == ["Rapid", "Quick Step"]
    assert parse_playstyle_list("") == []
    assert parse_playstyle_list(None) == []
