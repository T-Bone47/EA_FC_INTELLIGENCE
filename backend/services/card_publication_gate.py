"""No-fabrication firewall and card publication gate (Phase 20 S11, S12, S18).

There is currently zero legitimate FC26 UT card data (see
PHASE_20_CARD_DATA_STATUS.md). This module's job is to guarantee that fact
stays true structurally -- a game_player record must never automatically
become a UT card, at any layer, regardless of how much attribute data the
player record carries.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

REQUIRED_CARD_FIELDS_FOR_PUBLICATION = (
    "card_id",           # VERIFIED_EXTERNAL_ID or a withheld DERIVED_CANONICAL_ID -- never guessed
    "card_version_id",
    "game_version",
)


class PublicationDecision(str, Enum):
    PUBLISHABLE = "PUBLISHABLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NOT_PUBLISHABLE = "NOT_PUBLISHABLE"


@dataclass(frozen=True)
class CardCandidate:
    """A prospective UT card record -- deliberately NOT constructible from
    a GamePlayer/Candidate object by any automatic conversion. Every field
    must be independently supplied, and the ones that matter for
    publication default to None (absent), never inherited from a player."""
    card_id: Optional[str] = None
    card_version_id: Optional[str] = None
    game_version: Optional[str] = None
    is_synthetic: bool = False
    source_id: Optional[str] = None
    source_observation_id: Optional[str] = None
    legal_field_status: dict[str, str] = None  # field_name -> GREEN/YELLOW/RED/UNKNOWN
    unresolved_conflict_fields: tuple[str, ...] = ()

    def __post_init__(self):
        if self.legal_field_status is None:
            object.__setattr__(self, "legal_field_status", {})


@dataclass(frozen=True)
class PublicationResult:
    decision: PublicationDecision
    reasons: tuple[str, ...]


def evaluate_publication(card: CardCandidate, *, target_game_version: str = "FC26") -> PublicationResult:
    """Phase 20 S18. A card is PUBLISHABLE only if every required identity
    field is present, provenance exists, the game version matches exactly,
    it is not synthetic, no required field is RED/UNKNOWN, and there is no
    unresolved conflict on a required field. Anything else is
    REVIEW_REQUIRED (recoverable with more evidence) or NOT_PUBLISHABLE
    (a hard block)."""
    hard_blocks: list[str] = []
    review_reasons: list[str] = []

    if card.is_synthetic:
        hard_blocks.append("card is_synthetic=True -- synthetic data is never publishable")

    if card.game_version != target_game_version:
        hard_blocks.append(
            f"game_version={card.game_version!r} does not match target "
            f"{target_game_version!r} -- no FC25/FC27/ambiguous-version card is ever published "
            f"into another version's scope"
        )

    for field_name in REQUIRED_CARD_FIELDS_FOR_PUBLICATION:
        value = getattr(card, field_name, None)
        if value is None:
            hard_blocks.append(f"required field {field_name!r} is missing -- cannot be inferred")

    if card.source_id is None or card.source_observation_id is None:
        hard_blocks.append("no source_observation_id -- a card field with no provenance is never served")

    for field_name, status in (card.legal_field_status or {}).items():
        if status == "RED":
            hard_blocks.append(f"field {field_name!r} is legally RED -- explicitly prohibited from publication")
        elif status == "UNKNOWN":
            hard_blocks.append(f"field {field_name!r} is legally UNKNOWN -- treated as RED, not publishable")

    if card.unresolved_conflict_fields:
        review_reasons.append(
            f"unresolved conflict on field(s): {', '.join(card.unresolved_conflict_fields)} "
            f"-- value is UNKNOWN until resolved, not silently chosen"
        )

    if hard_blocks:
        return PublicationResult(PublicationDecision.NOT_PUBLISHABLE, tuple(hard_blocks))
    if review_reasons:
        return PublicationResult(PublicationDecision.REVIEW_REQUIRED, tuple(review_reasons))
    return PublicationResult(PublicationDecision.PUBLISHABLE, ())


def player_cannot_become_card(player_attributes: dict) -> CardCandidate:
    """Demonstrates the firewall directly: given an arbitrary game_player's
    full attribute dict, there is no function in this codebase that maps it
    to a populated CardCandidate. This constructs the ONLY thing a player
    record can legitimately produce -- an empty-identity CardCandidate that
    evaluate_publication will always reject."""
    return CardCandidate()  # every identity field defaults to None regardless of `player_attributes`
