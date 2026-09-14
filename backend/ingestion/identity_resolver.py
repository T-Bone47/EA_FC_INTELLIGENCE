"""Conservative identity resolution (§38).

Matches incoming GamePlayers to RealPlayers using normalized name +
nationality + DOB + position hints. NEVER merges on name similarity alone.
Ambiguity routes to REVIEW_REQUIRED — guessing is prohibited.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

from backend.domain.card_model import GamePlayer, IdentityStatus, RealPlayer
from backend.ingestion.normalizer import normalize_name


@dataclass
class IdentityIndex:
    """In-memory index over known RealPlayers (loaded from DB or fixtures)."""
    by_normalized_name: dict[str, list[RealPlayer]] = field(default_factory=dict)

    def add(self, rp: RealPlayer) -> None:
        self.by_normalized_name.setdefault(rp.normalized_name, []).append(rp)
        for v in rp.name_variants:
            nv = normalize_name(v)
            if nv:
                self.by_normalized_name.setdefault(nv, []).append(rp)

    @classmethod
    def build(cls, players: list[RealPlayer]) -> "IdentityIndex":
        idx = cls()
        for p in players:
            idx.add(p)
        return idx


@dataclass
class ResolutionResult:
    status: IdentityStatus
    real_player: Optional[RealPlayer]
    reason: str
    candidates_considered: int = 0
    matched_game_player: Optional[GamePlayer] = None   # RP-side resolution winner


def game_player_name_forms(gp: GamePlayer) -> set[str]:
    """All normalized name forms of a GamePlayer (display, common, first+last).

    EA data carries both registered names ('C. Ronaldo dos Santos Aveiro') and
    common names ('Cristiano Ronaldo'); identity facts may use either. Exact
    matching across forms is safe; anything looser goes to review.
    """
    forms = set()
    for raw in (gp.display_name, gp.common_name):
        n = normalize_name(raw or "")
        if n:
            forms.add(n)
    first = normalize_name(gp.first_name or "")
    last = normalize_name(gp.last_name or "")
    if first and last:
        forms.add(f"{first} {last}")
        forms.add(f"{last} {first}")
    return forms


class IdentityResolver:
    def __init__(self, index: IdentityIndex):
        self.index = index

    def resolve(self, gp: GamePlayer) -> ResolutionResult:
        forms = game_player_name_forms(gp)
        norm = normalize_name(gp.display_name)
        if not forms:
            return ResolutionResult(IdentityStatus.UNRESOLVED, None,
                                    "no usable name")
        exact = []
        seen = set()
        for f in sorted(forms):
            for rp in self.index.by_normalized_name.get(f, []):
                if rp.id not in seen:
                    seen.add(rp.id)
                    exact.append(rp)

        if len(exact) == 1:
            rp = exact[0]
            if self._corroborates(gp, rp):
                return ResolutionResult(IdentityStatus.RESOLVED, rp,
                                        "unique exact normalized-name match, corroborated",
                                        len(exact))
            return ResolutionResult(IdentityStatus.REVIEW_REQUIRED, rp,
                                    "unique name match but identity facts conflict "
                                    "(nationality/DOB/position) — routed to review, not merged",
                                    len(exact))
        if len(exact) > 1:
            # disambiguate with hard facts; if still ambiguous -> REVIEW_REQUIRED
            confirmed = [rp for rp in exact if self._corroborates(gp, rp, strict=True)]
            if len(confirmed) == 1:
                return ResolutionResult(IdentityStatus.RESOLVED, confirmed[0],
                                        "name ambiguous but identity facts confirm exactly one",
                                        len(exact))
            return ResolutionResult(
                IdentityStatus.REVIEW_REQUIRED, None,
                f"ambiguous: {len(exact)} real players share normalized name "
                f"{norm!r} and facts do not isolate one — REVIEW_REQUIRED (§38, never guess)",
                len(exact))

        # No exact match. §38: never merge on name similarity. Only a SURNAME
        # collision across multiple RealPlayers is escalated (to review);
        # everything else stays honestly UNRESOLVED (the GamePlayer exists
        # without a RealPlayer link — no guessing, no review-queue flooding).
        last_token = norm.split()[-1] if norm.split() else ""
        near: dict[uuid.UUID, RealPlayer] = {}
        if last_token and len(last_token) >= 4:
            for key, players in self.index.by_normalized_name.items():
                if last_token in key.split():
                    for p in players:
                        near[p.id] = p
        if len(near) > 1:
            return ResolutionResult(
                IdentityStatus.REVIEW_REQUIRED, None,
                f"surname-level match is ambiguous across {len(near)} real players "
                f"(e.g. {sorted(p.full_name for p in near.values())[:4]}) — "
                "REVIEW_REQUIRED, never auto-merged",
                len(near))
        return ResolutionResult(IdentityStatus.UNRESOLVED, None,
                                "no exact normalized-name match; left unresolved "
                                "(conservative: no similarity merge)")

    # ------------------------------------------------------------------ RP side
    def resolve_identity_record(self, rp: RealPlayer,
                                game_players: list[GamePlayer]) -> ResolutionResult:
        """Resolve a RealPlayer identity record against known GamePlayers.

        Policy (conservative, reproduces the documented 'ambiguous Ronaldo'
        behavior): exact normalized-name match + corroborated facts -> RESOLVED.
        Anything looser (token overlap), even when facts isolate a single
        candidate, routes to REVIEW_REQUIRED — similarity alone never merges.
        """
        norm = rp.normalized_name
        exact = [gp for gp in game_players if norm in game_player_name_forms(gp)]
        if len(exact) == 1 and self._corroborates(exact[0], rp):
            return ResolutionResult(IdentityStatus.RESOLVED, rp,
                                    "unique exact normalized-name match, corroborated",
                                    len(exact), matched_game_player=exact[0])
        if len(exact) > 1:
            confirmed = [gp for gp in exact if self._corroborates(gp, rp, strict=True)]
            if len(confirmed) == 1:
                return ResolutionResult(IdentityStatus.RESOLVED, rp,
                                        "name ambiguous but identity facts confirm exactly one",
                                        len(exact), matched_game_player=confirmed[0])
            return ResolutionResult(
                IdentityStatus.REVIEW_REQUIRED, None,
                f"{len(exact)} GamePlayers share the exact normalized name — "
                "REVIEW_REQUIRED", len(exact))

        rp_tokens = {t for t in norm.split() if len(t) >= 5}
        overlap = []
        if rp_tokens:
            for gp in game_players:
                gp_tokens = {t for form in game_player_name_forms(gp)
                             for t in form.split() if len(t) >= 5}
                if rp_tokens & gp_tokens:
                    overlap.append(gp)
        if not overlap:
            return ResolutionResult(IdentityStatus.UNRESOLVED, None,
                                    "no exact or token-overlap candidate found")
        corroborated = [gp for gp in overlap if self._corroborates(gp, rp, strict=True)]
        names = sorted({gp.display_name for gp in overlap})
        if len(overlap) == 1 and len(corroborated) == 1:
            return ResolutionResult(
                IdentityStatus.REVIEW_REQUIRED, None,
                f"single corroborated candidate {corroborated[0].display_name!r} but "
                "name is not an exact match — REVIEW_REQUIRED (never auto-merged, §38)",
                len(overlap))
        return ResolutionResult(
            IdentityStatus.REVIEW_REQUIRED, None,
            f"AMBIGUOUS: {len(overlap)} GamePlayers overlap identity tokens "
            f"({names[:6]}); {len(corroborated)} corroborated by hard facts — "
            "routed to REVIEW_REQUIRED, never guessed (§38)",
            len(overlap))

    @staticmethod
    def _corroborates(gp: GamePlayer, rp: RealPlayer, strict: bool = False) -> bool:
        """Hard-fact corroboration. Any CONTRADICTING fact fails; missing facts
        are UNKNOWN and only fail in strict mode when nothing corroborates."""
        checks = []
        if rp.nationality and gp.nation:
            checks.append(normalize_name(rp.nationality) == normalize_name(gp.nation))
        if rp.date_of_birth and gp.date_of_birth:
            checks.append(str(rp.date_of_birth)[:10] == str(gp.date_of_birth)[:10])
        if rp.position_hint and gp.position_primary:
            checks.append(rp.position_hint.upper() == gp.position_primary.upper())
        if not checks:
            return not strict
        if any(c is False for c in checks):
            return False
        return True if any(c is True for c in checks) else not strict
