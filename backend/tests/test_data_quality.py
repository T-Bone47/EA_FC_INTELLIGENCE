"""Data-quality gate: invalid production data rejected; UNKNOWN not rejected;
version-aware caps."""
from __future__ import annotations

import uuid

import pytest

from backend.domain.card_model import (
    GamePlayer, GameVersionCode, PlayerAttributes, UTCard,
)
from backend.ingestion.data_quality import DataQualityValidator


@pytest.fixture()
def v():
    return DataQualityValidator()


def gp(**kw) -> GamePlayer:
    base = dict(id=uuid.uuid4(), game_version=GameVersionCode.FC26,
                source_id="s", source_player_id=1, display_name="Test Player",
                position_primary="CM", overall_rating=80,
                attributes=PlayerAttributes())
    base.update(kw)
    return GamePlayer(**base)


def card(**kw) -> UTCard:
    base = dict(id=uuid.uuid4(), game_version=GameVersionCode.FC26,
                source_id="s", source_card_id="c1", card_name="Test Card",
                position="ST", overall_rating=80)
    base.update(kw)
    return UTCard(**base)


class TestPlayerRules:
    def test_valid_player_passes(self, v):
        assert v.validate_player(gp()).ok

    def test_missing_rating_rejected(self, v):
        r = v.validate_player(gp(overall_rating=None))
        assert r.rejected and any(i.rule == "required_rating" for i in r.issues)

    def test_impossible_rating_rejected(self, v):
        assert v.validate_player(gp(overall_rating=999)).rejected
        assert v.validate_player(gp(overall_rating=0)).rejected

    def test_unknown_position_rejected(self, v):
        assert v.validate_player(gp(position_primary="ZZZ")).rejected

    def test_missing_name_rejected(self, v):
        assert v.validate_player(gp(display_name="  ")).rejected

    def test_impossible_attribute_rejected(self, v):
        a = PlayerAttributes()
        a.set("pace", 150)
        assert v.validate_player(gp(attributes=a)).rejected

    def test_unknown_attributes_not_rejected(self, v):
        # §19: missing attributes are UNKNOWN, perfectly legal
        r = v.validate_player(gp(attributes=PlayerAttributes()))
        assert r.ok

    def test_gk_without_gk_attrs_is_review_not_reject(self, v):
        r = v.validate_player(gp(position_primary="GK"))
        assert not r.rejected
        assert r.needs_review
        assert any(i.rule == "gk_attributes_missing" for i in r.issues)


class TestCardRules:
    def test_valid_card_passes(self, v):
        c = card(playstyles_base=["Rapid"], playstyles_plus=["Rapid"])
        assert v.validate_card(c).ok

    def test_broken_rating_rejected(self, v):
        # normalizer turns 'NOT_A_NUMBER' into None + hint
        c = card(overall_rating=None,
                 validation_hints={"rating_unparseable": "NOT_A_NUMBER"})
        r = v.validate_card(c)
        assert r.rejected and any(i.rule == "invalid_rating" for i in r.issues)

    def test_missing_rating_rejected(self, v):
        r = v.validate_card(card(overall_rating=None))
        assert r.rejected and any(i.rule == "required_rating" for i in r.issues)

    def test_too_many_plus_rejected_fc26_cap_1(self, v):
        c = card(playstyles_base=["Finesse Shot", "Power Shot"],
                 playstyles_plus=["Finesse Shot", "Power Shot"])
        r = v.validate_card(c)
        assert r.rejected and any(i.rule == "playstyle_plus_cap" for i in r.issues)

    def test_plus_not_subset_of_base_rejected(self, v):
        c = card(playstyles_base=["Rapid"], playstyles_plus=["Finesse Shot"])
        r = v.validate_card(c)
        assert r.rejected and any(i.rule == "playstyle_plus_subset" for i in r.issues)

    def test_unknown_rarity_is_review(self, v):
        r = v.validate_card(card(rarity="mystery_promo"))
        assert not r.rejected and r.needs_review

    def test_fc27_cap_unknown_is_review_not_reject(self, v):
        # FC27 has NO seeded cap: unknown cap must not guess (-> REVIEW)
        c = card(game_version=GameVersionCode.FC27, position="",
                 playstyles_base=["Rapid", "Technical"],
                 playstyles_plus=["Rapid", "Technical"])
        r = v.validate_card(c)
        assert any(i.rule == "playstyle_plus_cap_unknown" for i in r.issues)
        # (position '' will also reject — that's separate and correct)
