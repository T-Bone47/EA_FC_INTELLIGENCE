"""Canonical domain model.

Hierarchy (fundamental, must never be collapsed):

    RealPlayer -> GamePlayer -> UTCard -> CardVersion

One real footballer may have multiple game versions (FC26, FC27, ...) and each
game version may have multiple UT cards. A card is NOT the real player.

UNKNOWN policy: every factual field is Optional. None means UNKNOWN — it must
never be coerced to 0 / False / empty-list by any layer.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

# Deterministic namespace for source-derived canonical IDs (idempotent ingestion).
ID_NAMESPACE = uuid.UUID("6f1e2d3c-4b5a-4968-8776-655443322110")


class GameVersionCode(str, Enum):
    FC26 = "FC26"
    FC27 = "FC27"

    @classmethod
    def parse(cls, raw: str) -> "GameVersionCode":
        try:
            return cls(str(raw).strip().upper())
        except ValueError:
            raise ValueError(
                f"Unsupported game_version {raw!r}. Supported: "
                f"{[v.value for v in cls]}. Versions are never mixed or defaulted silently.")


class DataStatus(str, Enum):
    CANONICAL = "CANONICAL"
    PENDING_REVIEW = "PENDING_REVIEW"
    SYNTHETIC_TEST = "SYNTHETIC_TEST"
    REJECTED = "REJECTED"


class IdentityStatus(str, Enum):
    RESOLVED = "RESOLVED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNRESOLVED = "UNRESOLVED"


FACADE_ATTRS = ("pace", "shooting", "passing", "dribbling", "defending", "physicality")
DETAIL_ATTRS = (
    "acceleration", "sprint_speed", "finishing", "shot_power", "long_shots",
    "volleys", "penalties", "positioning", "vision", "crossing",
    "short_passing", "long_passing", "curve", "free_kick_accuracy",
    "dribbling_detail", "ball_control", "agility", "balance", "reactions",
    "composure", "defensive_awareness", "interceptions", "standing_tackle",
    "sliding_tackle", "heading_accuracy", "strength", "stamina", "aggression",
    "jumping",
)
GK_ATTRS = ("gk_diving", "gk_handling", "gk_kicking", "gk_positioning", "gk_reflexes")
ALL_ATTRS = FACADE_ATTRS + DETAIL_ATTRS + GK_ATTRS


@dataclass
class PlayerAttributes:
    """Attribute bag. None = UNKNOWN for that attribute (never 0)."""
    values: dict[str, Optional[int]] = field(default_factory=dict)

    def get(self, name: str) -> Optional[int]:
        return self.values.get(name)

    def set(self, name: str, value: Optional[int]) -> None:
        if name not in ALL_ATTRS:
            raise KeyError(f"unknown attribute {name!r}")
        self.values[name] = value

    def known(self) -> dict[str, int]:
        return {k: v for k, v in self.values.items() if v is not None}

    def content_hash(self) -> str:
        payload = json.dumps(self.known(), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class RealPlayer:
    """The real-world human being. Identity facts only — no game ratings."""
    id: uuid.UUID
    full_name: str
    normalized_name: str
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None
    position_hint: Optional[str] = None
    identity_status: IdentityStatus = IdentityStatus.RESOLVED
    name_variants: list[str] = field(default_factory=list)


@dataclass
class GamePlayer:
    """A player as represented in one specific game version."""
    id: uuid.UUID
    game_version: GameVersionCode
    source_id: str
    source_player_id: int
    display_name: str
    position_primary: str
    overall_rating: Optional[int]
    attributes: PlayerAttributes = field(default_factory=PlayerAttributes)
    real_player_id: Optional[uuid.UUID] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    common_name: Optional[str] = None
    nation: Optional[str] = None
    club: Optional[str] = None
    league: Optional[str] = None
    position_type: Optional[str] = None
    secondary_positions: list[str] = field(default_factory=list)
    playstyles_base: list[str] = field(default_factory=list)
    playstyles_plus: list[str] = field(default_factory=list)
    playstyle_data_published: bool = False   # False => PlayStyles UNKNOWN (not "none")
    date_of_birth: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    preferred_foot: Optional[str] = None
    weak_foot_stars: Optional[int] = None
    skill_moves_stars: Optional[int] = None
    gender: Optional[str] = None
    source_rank: Optional[int] = None
    identity_status: IdentityStatus = IdentityStatus.RESOLVED
    data_status: DataStatus = DataStatus.CANONICAL

    @property
    def all_playstyles(self) -> set[str]:
        return set(self.playstyles_base) | set(self.playstyles_plus)


@dataclass
class UTCard:
    """An Ultimate Team card. Belongs to a game version; may reference a GamePlayer.

    Identity (§4): `id` is the per-source deterministic row id
    (source|version|source_card_id). `canonical_card_id` is the cross-source
    identity computed from football facts, NOT name+OVR — see
    `compute_canonical_id`. Both are stable and idempotent.
    """
    id: uuid.UUID
    game_version: GameVersionCode
    source_id: str
    source_card_id: str
    card_name: str
    position: str
    overall_rating: Optional[int]
    rarity: Optional[str] = None
    game_player_id: Optional[uuid.UUID] = None
    # card-published attributes. These are the ONLY attributes a card candidate
    # may use (§5). Missing keys are UNKNOWN — never backfilled from the base
    # player.
    attribute_overrides: dict[str, Optional[int]] = field(default_factory=dict)
    playstyles_base: list[str] = field(default_factory=list)
    playstyles_plus: list[str] = field(default_factory=list)
    # True only when the source publishes this card's PlayStyle list. False =>
    # card PlayStyles are UNKNOWN — base-player PlayStyles are never inherited.
    playstyle_data_published: bool = False
    price_coins: Optional[int] = None        # None = UNKNOWN, never 0
    price_platform: Optional[str] = None
    price_observed_at: Optional[str] = None
    price_source_id: Optional[str] = None
    price_confidence: Optional[float] = None
    is_synthetic: bool = False
    data_status: DataStatus = DataStatus.CANONICAL
    validation_hints: dict[str, Any] = field(default_factory=dict)
    # ---- Phase 3 (§3/§4/§7/§9) ----
    canonical_card_id: Optional[uuid.UUID] = None
    card_type: Optional[str] = None          # version-aware; never assumed
    rarity_raw: Optional[str] = None         # source wording before mapping
    release_date: Optional[Any] = None
    release_group: Optional[str] = None
    identity_status: IdentityStatus = IdentityStatus.UNRESOLVED
    identity_rule: Optional[str] = None
    roles: list[dict[str, Any]] = field(default_factory=list)   # card-level roles

    @staticmethod
    def deterministic_id(source_id: str, game_version: str, source_card_id: str) -> uuid.UUID:
        """card_id derived from source identity + source row identity (idempotency)."""
        return uuid.uuid5(ID_NAMESPACE, f"ut_card|{source_id}|{game_version}|{source_card_id}")

    @staticmethod
    def compute_canonical_id(game_version: str, player_key: str,
                             card_type: Optional[str], rarity_code: Optional[str],
                             position: str, release_group: Optional[str]) -> uuid.UUID:
        """§4 canonical identity rule (documented in docs/CARD_IDENTITY.md).

        Deliberately NOT name+OVR. Inputs are football facts that distinguish
        one release of a player's card from another:
        version | player identity | card type (falling back to rarity, then
        BASE) | position | release group (promo wave).
        Deterministic: the same card from two sources gets the same id, while
        a Gold base and a TOTW of the same player stay distinct. FC26 and FC27
        can never collide because game_version is part of the preimage.
        """
        kind = (card_type or rarity_code or "BASE").strip().upper()
        return uuid.uuid5(
            ID_NAMESPACE,
            "canonical_card|{v}|{p}|{k}|{pos}|{rg}".format(
                v=str(game_version).strip().upper(),
                p=str(player_key).strip(),
                k=kind,
                pos=str(position or "").strip().upper(),
                rg=str(release_group or "").strip()))


@dataclass
class CardVersion:
    """A timestamped stat snapshot of a UTCard. Content-hash identified."""
    id: uuid.UUID
    ut_card_id: uuid.UUID
    version_number: int
    content_hash: str
    overall_rating: Optional[int]
    attributes: dict[str, Any] = field(default_factory=dict)
    playstyles: dict[str, Any] = field(default_factory=dict)
    valid_from: Optional[str] = None
    is_current: bool = True

    @staticmethod
    def compute_content_hash(overall: Optional[int], attributes: dict, playstyles: dict) -> str:
        payload = json.dumps(
            {"ovr": overall, "attrs": attributes, "ps": playstyles},
            sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def deterministic_id(ut_card_id: uuid.UUID, content_hash: str) -> uuid.UUID:
        return uuid.uuid5(ID_NAMESPACE, f"card_version|{ut_card_id}|{content_hash}")


@dataclass
class Candidate:
    """Unified scoring target for the recommendation engine.

    Wraps either a GamePlayer (player-level request) or a UTCard (card-level
    request). The engine never conflates them: entity_type is always explicit.
    """
    entity_type: str                       # 'game_player' | 'ut_card'
    entity_id: uuid.UUID
    game_version: GameVersionCode
    name: str
    position_primary: str
    secondary_positions: list[str]
    overall_rating: Optional[int]
    attributes: PlayerAttributes
    playstyles_base: list[str]
    playstyles_plus: list[str]
    playstyle_data_published: bool
    nation: Optional[str] = None
    club: Optional[str] = None
    league: Optional[str] = None
    rarity: Optional[str] = None
    price_coins: Optional[int] = None      # None = UNKNOWN
    data_status: DataStatus = DataStatus.CANONICAL
    is_synthetic: bool = False
    extra: dict[str, Any] = field(default_factory=dict)
    # §29 precomputed non-user-specific features (archetype vectors, gameplay
    # profile, versatility, position-weighted attribute bases). Lazily filled;
    # lives and dies with the cached candidate pool (watermark-invalidated).
    feature_cache: dict[str, Any] = field(default_factory=dict, compare=False,
                                          repr=False)

    @classmethod
    def from_game_player(cls, gp: GamePlayer) -> "Candidate":
        return cls(
            entity_type="game_player", entity_id=gp.id, game_version=gp.game_version,
            name=gp.display_name, position_primary=gp.position_primary,
            secondary_positions=list(gp.secondary_positions),
            overall_rating=gp.overall_rating, attributes=gp.attributes,
            playstyles_base=list(gp.playstyles_base),
            playstyles_plus=list(gp.playstyles_plus),
            playstyle_data_published=gp.playstyle_data_published,
            nation=gp.nation, club=gp.club, league=gp.league,
            data_status=gp.data_status, is_synthetic=(gp.data_status == DataStatus.SYNTHETIC_TEST),
            extra={"position_type": gp.position_type, "preferred_foot": gp.preferred_foot,
                   "weak_foot_stars": gp.weak_foot_stars, "skill_moves_stars": gp.skill_moves_stars,
                   "source_player_id": gp.source_player_id},
        )

    @classmethod
    def from_ut_card(cls, card: UTCard, gp: Optional[GamePlayer] = None) -> "Candidate":
        """Build a card candidate. §5 CARD ATTRIBUTE SEPARATION:

        * attributes come ONLY from card-published values; anything the card
          does not publish is UNKNOWN (None) — never silently inherited from
          the base player;
        * PlayStyles come ONLY from the card, and only when the card's
          PlayStyle data is published;
        * overall rating is the card's;
        * price is the card's.

        The base GamePlayer contributes ONLY identity/link facts (nation,
        club, league, secondary positions) which are player-level facts, and
        every such contribution is labelled in `extra` so the evidence trail
        shows where each value came from.
        """
        attrs = PlayerAttributes()
        for k, v in card.attribute_overrides.items():
            attrs.set(k, v)               # card values only; no base fallback
        ps_published = bool(card.playstyle_data_published)
        return cls(
            entity_type="ut_card", entity_id=card.id, game_version=card.game_version,
            name=card.card_name, position_primary=card.position,
            secondary_positions=list(gp.secondary_positions) if gp else [],
            overall_rating=card.overall_rating, attributes=attrs,
            playstyles_base=list(card.playstyles_base) if ps_published else [],
            playstyles_plus=list(card.playstyles_plus) if ps_published else [],
            playstyle_data_published=ps_published,
            nation=gp.nation if gp else None, club=gp.club if gp else None,
            league=gp.league if gp else None, rarity=card.rarity,
            price_coins=card.price_coins, data_status=card.data_status,
            is_synthetic=card.is_synthetic,
            extra={
                "card_type": card.card_type,
                "rarity_raw": card.rarity_raw,
                "release_date": card.release_date,
                "release_group": card.release_group,
                "source_card_id": card.source_card_id,
                "source_id": card.source_id,
                "canonical_card_id": (str(card.canonical_card_id)
                                      if card.canonical_card_id else None),
                "card_identity_status": card.identity_status.value,
                "game_player_id": str(card.game_player_id) if card.game_player_id else None,
                "roles": list(card.roles),
                "attribute_source": "ut_card",
                "attribute_separation": ("card-published attributes only; "
                                         "unpublished = UNKNOWN, never base-player"),
                "secondary_positions_source": ("game_player" if gp and gp.secondary_positions
                                               else None),
                "playstyle_source": "ut_card" if ps_published else None,
                "price_platform": card.price_platform,
                "price_observed_at": card.price_observed_at,
                "price_source_id": card.price_source_id,
                "price_confidence": card.price_confidence,
            },
        )
