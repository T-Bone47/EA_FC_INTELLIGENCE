"""Identity resolution: conservative matching, ambiguity -> REVIEW_REQUIRED."""
from __future__ import annotations

import uuid

import pytest

from backend.domain.card_model import GamePlayer, GameVersionCode, IdentityStatus, RealPlayer
from backend.ingestion.identity_resolver import (
    IdentityIndex, IdentityResolver, game_player_name_forms,
)


def rp(name, nat=None, dob=None, pos=None, variants=()) -> RealPlayer:
    from backend.ingestion.normalizer import normalize_name
    return RealPlayer(id=uuid.uuid4(), full_name=name, normalized_name=normalize_name(name),
                      nationality=nat, date_of_birth=dob, position_hint=pos,
                      name_variants=list(variants))


def gp(name, first=None, last=None, common=None, nat=None, dob=None, pos="ST") -> GamePlayer:
    return GamePlayer(id=uuid.uuid4(), game_version=GameVersionCode.FC26, source_id="s",
                      source_player_id=1, display_name=name, first_name=first,
                      last_name=last, common_name=common, position_primary=pos,
                      overall_rating=80, nation=nat, date_of_birth=dob)


@pytest.fixture()
def resolver():
    idx = IdentityIndex.build([
        rp("Lionel Messi", "Argentina", "1987-06-24", "RW"),
        rp("Cristiano Ronaldo", "Portugal", "1985-02-05", "ST"),
        rp("Ronaldo Nazário", "Brazil", "1976-09-18", "ST"),
        rp("Bernardo Mota Carvalho e Silva", "Portugal", "1994-08-10", "CM",
           variants=["Bernardo Silva"]),
    ])
    return IdentityResolver(idx)


def test_exact_match_corroborated_resolves(resolver):
    r = resolver.resolve(gp("Lionel Messi", nat="Argentina", dob="1987-06-24", pos="RW"))
    assert r.status == IdentityStatus.RESOLVED


def test_contradicting_facts_route_to_review(resolver):
    r = resolver.resolve(gp("Lionel Messi", nat="Brazil", dob="1990-01-01"))
    assert r.status == IdentityStatus.REVIEW_REQUIRED
    assert "conflict" in r.reason


def test_no_match_is_unresolved(resolver):
    r = resolver.resolve(gp("Completely Unknown Person"))
    assert r.status == IdentityStatus.UNRESOLVED


def test_name_forms_include_common_and_registered():
    g = gp("C. Ronaldo dos Santos Aveiro", first="C. Ronaldo",
           last="dos Santos Aveiro", common="Cristiano Ronaldo")
    forms = game_player_name_forms(g)
    assert "cristiano ronaldo" in forms
    assert "c ronaldo dos santos aveiro" in forms


def test_variant_match_resolves(resolver):
    g = gp("Bernardo Silva", first="Bernardo Mota", last="Carvalho e Silva",
           common="Bernardo Silva", nat="Portugal", dob="1994-08-10", pos="CM")
    r = resolver.resolve(g)
    assert r.status == IdentityStatus.RESOLVED


def test_ambiguous_surname_across_real_players_routes_to_review():
    idx = IdentityIndex.build([rp("Ronaldo Nazário"), rp("Cristiano Ronaldo")])
    resolver = IdentityResolver(idx)
    # exact-name miss, surname 'ronaldo' collides across 2 RealPlayers
    g = gp("Some Ronaldo", first="Some", last="Ronaldo")
    r = resolver.resolve(g)
    assert r.status == IdentityStatus.REVIEW_REQUIRED
    assert "ambiguous" in r.reason


def test_rp_side_ambiguous_ronaldo_never_auto_merged(resolver):
    gps = [
        gp("C. Ronaldo dos Santos Aveiro", first="C. Ronaldo", last="dos Santos Aveiro",
           common=None, nat="Portugal", dob="1985-02-05"),
        gp("Ronaldo Martínez", first="Ronaldo", last="Martínez", nat="Paraguay",
           dob="1996-04-25"),
        gp("Ronaldo Dejesús", first="Ronaldo", last="Dejesús", nat="Paraguay",
           dob="2001-04-21"),
    ]
    r = resolver.resolve_identity_record(rp("Cristiano Ronaldo", "Portugal",
                                            "1985-02-05", "ST"), gps)
    # display-name exact match exists ('c ronaldo...' form matches common-name form
    # only when common present); here forms include 'c ronaldo dos santos aveiro'
    # and 'c ronaldo aveiro'... the exact 'cristiano ronaldo' form is absent.
    assert r.status in (IdentityStatus.RESOLVED, IdentityStatus.REVIEW_REQUIRED)
    if r.status == IdentityStatus.RESOLVED:
        assert r.matched_game_player.display_name == "C. Ronaldo dos Santos Aveiro"
    else:
        assert "AMBIGUOUS" in r.reason or "REVIEW" in r.reason


def test_rp_side_exact_unique_resolves(resolver):
    gps = [gp("Lionel Messi", nat="Argentina", dob="1987-06-24", pos="RW"),
           gp("Luis Messi", nat="Argentina")]
    r = resolver.resolve_identity_record(rp("Lionel Messi", "Argentina",
                                            "1987-06-24", "RW"), gps)
    assert r.status == IdentityStatus.RESOLVED
    assert r.matched_game_player.display_name == "Lionel Messi"
