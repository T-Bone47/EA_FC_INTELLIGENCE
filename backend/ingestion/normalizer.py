"""Deterministic normalization: raw source records -> canonical domain objects.

Idempotency: canonical IDs are derived deterministically from (source, game
version, source row id) via uuid5, and CardVersion IDs incorporate a content
hash. Re-running the same dataset produces no duplicates; genuine content
changes create a new CardVersion.

UNKNOWN policy: empty strings/None stay None. No zero-coercion anywhere.
"""
from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Optional

from backend.domain.card_model import (
    IdentityStatus,
    ALL_ATTRS, CardVersion, DataStatus, GamePlayer, GameVersionCode,
    PlayerAttributes, UTCard,
)
from backend.ingestion.adapter import RawCardRecord, RawPlayerRecord

NAME_NAMESPACE = uuid.UUID("6f1e2d3c-4b5a-4968-8776-655443322110")


def normalize_name(name: str) -> str:
    """Conservative normalization: strip accents/case/punctuation; NEVER merges
    on similarity — that is the identity resolver's (conservative) job."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def _int_or_none(v) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _display_name(names: dict) -> str:
    common = (names.get("common") or "").strip()
    if common:
        return common
    first = (names.get("first") or "").strip()
    last = (names.get("last") or "").strip()
    return (f"{first} {last}".strip()) or "Unknown"


def parse_alternate_positions(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    return [p.strip().upper() for p in re.split(r"[;,|]", raw) if p.strip()]


def parse_playstyle_list(raw: Optional[str], strip_plus: bool = True) -> list[str]:
    if not raw:
        return []
    out = []
    for p in raw.split(","):
        p = p.strip()
        if strip_plus:
            p = p.rstrip("+").strip()
        if p:
            out.append(p)
    return out


class Normalizer:
    def __init__(self, source_id: str, game_version: str):
        self.source_id = source_id
        self.game_version = GameVersionCode.parse(game_version)

    # ------------------------------------------------------------ players
    def game_player_id(self, source_player_id) -> uuid.UUID:
        return uuid.uuid5(
            NAME_NAMESPACE,
            f"game_player|{self.source_id}|{self.game_version.value}|{source_player_id}")

    def normalize_player(self, raw: RawPlayerRecord) -> GamePlayer:
        gv = raw.extras.get("game_version") or self.game_version.value
        if str(gv).upper() != self.game_version.value:
            raise ValueError(f"version contamination: {gv} != {self.game_version.value}")

        attrs = PlayerAttributes()
        for code in ALL_ATTRS:
            v = _int_or_none(raw.attributes.get(code))
            attrs.set(code, v)

        display = _display_name(raw.names)
        gp = GamePlayer(
            id=self.game_player_id(raw.source_player_id),
            game_version=self.game_version,
            source_id=self.source_id,
            source_player_id=int(raw.source_player_id),
            display_name=display,
            position_primary=(raw.position_raw or "").upper(),
            overall_rating=_int_or_none(raw.overall_rating),
            attributes=attrs,
            first_name=(raw.names.get("first") or None),
            last_name=(raw.names.get("last") or None),
            common_name=(raw.names.get("common") or None),
            nation=raw.nation, club=raw.club, league=raw.league,
            position_type=raw.extras.get("position_type"),
            secondary_positions=parse_alternate_positions(raw.alternate_positions_raw),
            date_of_birth=raw.extras.get("date_of_birth") or None,
            height_cm=_int_or_none(raw.extras.get("height_cm")),
            weight_kg=_int_or_none(raw.extras.get("weight_kg")),
            preferred_foot=raw.extras.get("preferred_foot") or None,
            weak_foot_stars=_int_or_none(raw.extras.get("weak_foot_stars")),
            skill_moves_stars=_int_or_none(raw.extras.get("skill_moves_stars")),
            gender=raw.extras.get("gender") or None,
            source_rank=_int_or_none(raw.extras.get("source_rank")),
        )
        return gp

    # ------------------------------------------------------------ cards
    def normalize_card(self, raw: RawCardRecord) -> UTCard:
        if raw.source_card_id is None or str(raw.source_card_id).strip() == "":
            raise ValueError(
                "card has no source_card_id — identity cannot be established, "
                "so the row is rejected rather than given an invented id (§4)")
        gv = raw.extras.get("game_version") or self.game_version.value
        if str(gv).upper() != self.game_version.value:
            raise ValueError(f"version contamination: {gv} != {self.game_version.value}")
        data_status_raw = (raw.extras.get("data_status") or "").upper()
        is_synth = (data_status_raw == "SYNTHETIC_TEST"
                    or (raw.extras.get("source") or "").upper() == "SYNTHETIC_TEST"
                    or self.source_id == "synthetic_fixtures")
        status = DataStatus.SYNTHETIC_TEST if is_synth else DataStatus.CANONICAL

        overrides = {}
        for code, v in raw.attributes.items():
            iv = _int_or_none(v)
            if iv is not None:
                overrides[code] = iv

        hints: dict = {}
        raw_ovr = raw.overall_rating
        if raw_ovr is not None and str(raw_ovr).strip() != "" \
                and _int_or_none(raw_ovr) is None:
            hints["rating_unparseable"] = str(raw_ovr)

        # PlayStyle publication: the column being PRESENT (even empty) means the
        # source published this card's PlayStyle list; absent means UNKNOWN and
        # base-player PlayStyles are never inherited (§6).
        published_raw = raw.extras.get("playstyles_published")
        ps_published = (raw.playstyles_raw is not None
                        or raw.playstyles_plus_raw is not None
                        or str(published_raw or "").strip().lower()
                        in ("true", "1", "yes"))
        if published_raw is not None and str(published_raw).strip() != "":
            ps_published = str(published_raw).strip().lower() in ("true", "1", "yes")

        rarity_raw = (raw.rarity_raw or "").strip() or None
        card_type = (raw.extras.get("card_type") or "").strip() or None
        release_group = (raw.extras.get("release_group") or "").strip() or None
        release_date = (raw.extras.get("release_date") or "").strip() or None

        # §4 canonical identity: never name+OVR. Requires a stable player key
        # from the source; without one the card stays UNRESOLVED (honest) —
        # we do not guess identity from names.
        player_ref = raw.source_player_ref
        canonical_id = None
        identity_status = IdentityStatus.UNRESOLVED
        identity_rule = None
        if player_ref is not None and str(player_ref).strip() != "":
            canonical_id = UTCard.compute_canonical_id(
                self.game_version.value, f"sp:{str(player_ref).strip()}",
                card_type, (rarity_raw or "").lower() or None,
                (raw.position_raw or "").upper(), release_group)
            identity_status = IdentityStatus.RESOLVED
            identity_rule = ("canonical_card_id = uuid5(version|source_player_ref|"
                             "card_type|rarity|position|release_group)")

        card = UTCard(
            id=UTCard.deterministic_id(self.source_id, self.game_version.value,
                                       str(raw.source_card_id)),
            game_version=self.game_version,
            source_id=self.source_id,
            source_card_id=str(raw.source_card_id),
            card_name=raw.card_name or "Unknown Card",
            position=(raw.position_raw or "").upper(),
            overall_rating=_int_or_none(raw.overall_rating),
            rarity=(rarity_raw or "").lower() or None,
            attribute_overrides=overrides,
            playstyles_base=parse_playstyle_list(raw.playstyles_raw),
            playstyles_plus=parse_playstyle_list(raw.playstyles_plus_raw),
            playstyle_data_published=ps_published,
            price_coins=_int_or_none(raw.price_coins),   # None = UNKNOWN, never 0
            is_synthetic=is_synth,
            data_status=status,
            validation_hints=hints,
            canonical_card_id=canonical_id,
            card_type=card_type,
            rarity_raw=rarity_raw,
            release_date=release_date,
            release_group=release_group,
            identity_status=identity_status,
            identity_rule=identity_rule,
        )
        return card

    def card_version(self, card: UTCard) -> CardVersion:
        payload_attrs = dict(sorted(card.attribute_overrides.items()))
        payload_ps = {"base": sorted(card.playstyles_base),
                      "plus": sorted(card.playstyles_plus)}
        content_hash = CardVersion.compute_content_hash(
            card.overall_rating, payload_attrs, payload_ps)
        return CardVersion(
            id=CardVersion.deterministic_id(card.id, content_hash),
            ut_card_id=card.id,
            version_number=1,
            content_hash=content_hash,
            overall_rating=card.overall_rating,
            attributes=payload_attrs,
            playstyles=payload_ps,
            is_current=True,
        )
