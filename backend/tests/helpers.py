"""Test helpers — tests depend on production code, never the reverse (§14)."""
from __future__ import annotations

import uuid
from typing import Optional

from backend.domain.card_model import (
    Candidate, DataStatus, GamePlayer, GameVersionCode, PlayerAttributes,
)
from backend.domain.user_model import AttributePreference, UserRequirements


def make_attrs(**kw) -> PlayerAttributes:
    a = PlayerAttributes()
    for k, v in kw.items():
        a.set(k, v)
    return a


def make_candidate(name: str = "Test Player",
                   position: str = "CM",
                   ovr: Optional[int] = 85,
                   version: str = "FC26",
                   attrs: Optional[PlayerAttributes] = None,
                   playstyles_base: Optional[list[str]] = None,
                   playstyles_plus: Optional[list[str]] = None,
                   playstyle_published: bool = True,
                   secondary: Optional[list[str]] = None,
                   nation: Optional[str] = "Testland",
                   club: Optional[str] = "Test FC",
                   league: Optional[str] = "Test League",
                   price: Optional[int] = None,
                   synthetic: bool = False,
                   entity_id: Optional[uuid.UUID] = None) -> Candidate:
    return Candidate(
        entity_type="game_player",
        entity_id=entity_id or uuid.uuid4(),
        game_version=GameVersionCode(version),
        name=name, position_primary=position,
        secondary_positions=secondary or [],
        overall_rating=ovr,
        attributes=attrs if attrs is not None else make_attrs(
            short_passing=80, vision=80, long_passing=78, stamina=85,
            ball_control=82, composure=80, defensive_awareness=70,
            interceptions=65, positioning=72, dribbling_detail=78,
            acceleration=70, sprint_speed=68, strength=72, aggression=60,
        ),
        playstyles_base=playstyles_base if playstyles_base is not None else ["Tiki Taka", "First Touch"],
        playstyles_plus=playstyles_plus or [],
        playstyle_data_published=playstyle_published,
        nation=nation, club=club, league=league,
        price_coins=price,
        data_status=DataStatus.SYNTHETIC_TEST if synthetic else DataStatus.CANONICAL,
        is_synthetic=synthetic,
    )


def make_req(**kw) -> UserRequirements:
    kw.setdefault("game_version", "FC26")
    return UserRequirements(**kw)


CM_ATTRS = dict(short_passing=80, vision=80, long_passing=78, stamina=85,
                ball_control=82, composure=80, defensive_awareness=70,
                interceptions=65, positioning=72, dribbling_detail=78)
