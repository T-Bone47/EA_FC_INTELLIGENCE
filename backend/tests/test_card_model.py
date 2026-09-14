"""Phase 3 §4/§5/§7 — card domain semantics: identity, attribute separation,
rarity UNKNOWN. Pure domain tests; no DB required."""
from __future__ import annotations

import uuid

from backend.domain.card_model import (
    Candidate, DataStatus, GamePlayer, GameVersionCode, PlayerAttributes,
    UTCard,
)


def _base_player(pace=84, finishing=85, ps_base=("Rapid",), published=True):
    return GamePlayer(
        id=uuid.uuid4(), game_version=GameVersionCode.FC26, source_id="src_a",
        source_player_id=4242, display_name="Base Player",
        position_primary="ST", overall_rating=84,
        attributes=PlayerAttributes(values={"pace": pace, "finishing": finishing}),
        playstyles_base=list(ps_base), playstyles_plus=[],
        playstyle_data_published=published,
        nation="France", club="Paris SG", league="Ligue 1",
        secondary_positions=["LW"])


def _card(**kw):
    kw.setdefault("id", uuid.uuid4())
    kw.setdefault("game_version", GameVersionCode.FC26)
    kw.setdefault("source_id", "src_a")
    kw.setdefault("source_card_id", "card-1")
    kw.setdefault("card_name", "TOTW Base Player")
    kw.setdefault("position", "ST")
    kw.setdefault("overall_rating", 91)
    kw.setdefault("data_status", DataStatus.CANONICAL)
    return UTCard(**kw)


# --------------------------------------------------------------------- §5
class TestCardAttributeSeparation:
    def test_card_attribute_beats_base_player(self):
        """PAC95 card over PAC84 base player: the candidate MUST carry 95."""
        gp = _base_player(pace=84)
        card = _card(attribute_overrides={"pace": 95})
        c = Candidate.from_ut_card(card, gp)
        assert c.attributes.get("pace") == 95

    def test_unpublished_card_attribute_is_unknown_never_base_value(self):
        """An attribute the card does not publish is UNKNOWN — never 85 from
        the base player. This is the exact silent-fallback bug §5 forbids."""
        gp = _base_player(finishing=85)
        card = _card(attribute_overrides={"pace": 95})   # finishing NOT published
        c = Candidate.from_ut_card(card, gp)
        assert c.attributes.get("finishing") is None
        assert "finishing" not in c.attributes.known()

    def test_card_overall_is_card_level(self):
        gp = _base_player()
        c = Candidate.from_ut_card(_card(overall_rating=91), gp)
        assert c.overall_rating == 91
        assert c.overall_rating != gp.overall_rating

    def test_playstyles_never_inherited_from_base_player(self):
        gp = _base_player(ps_base=("Rapid", "Finesse Shot"))
        card = _card(playstyles_base=[], playstyles_plus=[],
                     playstyle_data_published=False)
        c = Candidate.from_ut_card(card, gp)
        assert c.playstyles_base == []
        assert c.playstyles_plus == []
        assert c.playstyle_data_published is False

    def test_published_card_playstyles_are_used(self):
        gp = _base_player(ps_base=("Rapid",))
        card = _card(playstyles_base=["Quick Step"], playstyles_plus=["Quick Step"],
                     playstyle_data_published=True)
        c = Candidate.from_ut_card(card, gp)
        assert c.playstyles_base == ["Quick Step"]
        assert c.playstyles_plus == ["Quick Step"]
        assert "Rapid" not in c.playstyles_base   # base PS not merged in

    def test_playstyle_plus_never_silently_created(self):
        card = _card(playstyles_base=["Rapid"], playstyles_plus=[],
                     playstyle_data_published=True)
        c = Candidate.from_ut_card(card, None)
        assert c.playstyles_plus == []

    def test_price_is_card_level_and_never_zero_default(self):
        c = Candidate.from_ut_card(_card(price_coins=None), None)
        assert c.price_coins is None
        c2 = Candidate.from_ut_card(_card(price_coins=125000), None)
        assert c2.price_coins == 125000

    def test_link_facts_come_from_base_player_and_are_labelled(self):
        gp = _base_player()
        c = Candidate.from_ut_card(_card(), gp)
        assert (c.nation, c.club, c.league) == ("France", "Paris SG", "Ligue 1")
        assert c.secondary_positions == ["LW"]
        assert c.extra["attribute_source"] == "ut_card"
        assert c.extra["secondary_positions_source"] == "game_player"
        assert c.entity_type == "ut_card"

    def test_card_without_base_player_is_self_standing(self):
        c = Candidate.from_ut_card(_card(attribute_overrides={"pace": 90}), None)
        assert c.attributes.get("pace") == 90
        assert c.nation is None and c.club is None and c.league is None
        assert c.extra["game_player_id"] is None


# --------------------------------------------------------------------- §7
class TestRarity:
    def test_unknown_rarity_stays_unknown(self):
        c = Candidate.from_ut_card(_card(rarity=None), None)
        assert c.rarity is None     # never defaulted to 'gold'

    def test_rarity_is_data_driven_value(self):
        c = Candidate.from_ut_card(_card(rarity="totw", rarity_raw="Team of the Week"), None)
        assert c.rarity == "totw"
        assert c.extra["rarity_raw"] == "Team of the Week"


# --------------------------------------------------------------------- §4
class TestCardIdentity:
    def test_row_id_is_deterministic_and_idempotent(self):
        a = UTCard.deterministic_id("src_a", "FC26", "card-9")
        b = UTCard.deterministic_id("src_a", "FC26", "card-9")
        assert a == b

    def test_canonical_id_never_name_ovr(self):
        """Same name + same OVR but different underlying players => different
        canonical ids: identity must not collapse to name+OVR."""
        k1 = UTCard.compute_canonical_id("FC26", "sp:111", None, "gold", "ST", None)
        k2 = UTCard.compute_canonical_id("FC26", "sp:222", None, "gold", "ST", None)
        assert k1 != k2

    def test_canonical_id_distinguishes_card_types(self):
        base = UTCard.compute_canonical_id("FC26", "sp:111", None, "gold", "ST", None)
        totw = UTCard.compute_canonical_id("FC26", "sp:111", "TOTW", "gold", "ST", None)
        assert base != totw

    def test_canonical_id_distinguishes_release_groups(self):
        a = UTCard.compute_canonical_id("FC26", "sp:111", "PROMO", "gold", "ST", "wave1")
        b = UTCard.compute_canonical_id("FC26", "sp:111", "PROMO", "gold", "ST", "wave2")
        assert a != b

    def test_fc26_fc27_never_collide(self):
        a = UTCard.compute_canonical_id("FC26", "sp:111", None, "gold", "ST", None)
        b = UTCard.compute_canonical_id("FC27", "sp:111", None, "gold", "ST", None)
        ra = UTCard.deterministic_id("src", "FC26", "card-1")
        rb = UTCard.deterministic_id("src", "FC27", "card-1")
        assert a != b and ra != rb

    def test_canonical_id_stable_across_sources(self):
        """The same real card seen via two sources resolves to one canonical id
        while row ids stay source-specific (no duplicate merges, no collisions)."""
        row_a = UTCard.deterministic_id("source_a", "FC26", "xyz-1")
        row_b = UTCard.deterministic_id("source_b", "FC26", "abc-9")
        canon_a = UTCard.compute_canonical_id("FC26", "sp:111", "TOTW", None, "ST", None)
        canon_b = UTCard.compute_canonical_id("FC26", "sp:111", "TOTW", None, "ST", None)
        assert row_a != row_b
        assert canon_a == canon_b

    def test_identity_metadata_exposed_on_candidate(self):
        card = _card(canonical_card_id=uuid.uuid4(), card_type="TOTW",
                     release_group="TOTW-1")
        from backend.domain.card_model import IdentityStatus
        card.identity_status = IdentityStatus.RESOLVED
        c = Candidate.from_ut_card(card, None)
        assert c.extra["card_type"] == "TOTW"
        assert c.extra["card_identity_status"] == "RESOLVED"
        assert c.extra["canonical_card_id"] == str(card.canonical_card_id)
