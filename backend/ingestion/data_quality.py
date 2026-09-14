"""Data-quality validation gate (§12, §37).

Invalid PRODUCTION data is rejected, never silently repaired. Ambiguous
identities are routed to review. Version-aware rules come from VersionConfig
(positions, PlayStyle+ caps) rather than hardcoded constants.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.domain.card_model import GamePlayer, UTCard
from backend.services.scoring_config import ScoringConfig, VersionConfig

VALID_RATINGS = range(1, 100)


@dataclass
class ValidationIssue:
    rule: str
    severity: str          # 'REJECT' | 'REVIEW'
    message: str
    entity_id: Optional[str] = None


@dataclass
class ValidationResult:
    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def rejected(self) -> bool:
        return any(i.severity == "REJECT" for i in self.issues)

    @property
    def needs_review(self) -> bool:
        return any(i.severity == "REVIEW" for i in self.issues)


class DataQualityValidator:
    def __init__(self, scoring_config: Optional[ScoringConfig] = None):
        self.scoring_config = scoring_config or ScoringConfig()

    def version_config(self, code: str) -> VersionConfig:
        return self.scoring_config.version(code)

    # ------------------------------------------------------------------ players
    def validate_player(self, gp: GamePlayer) -> ValidationResult:
        issues: list[ValidationIssue] = []
        vc = self.version_config(gp.game_version.value)
        eid = str(gp.id)

        if not gp.display_name or not gp.display_name.strip():
            issues.append(ValidationIssue("required_name", "REJECT",
                                          "missing player name", eid))
        if gp.overall_rating is None:
            issues.append(ValidationIssue("required_rating", "REJECT",
                                          "missing overall rating", eid))
        elif gp.overall_rating not in VALID_RATINGS:
            issues.append(ValidationIssue("rating_range", "REJECT",
                                          f"overall rating {gp.overall_rating} outside 1-99", eid))

        if not gp.position_primary:
            issues.append(ValidationIssue("required_position", "REJECT",
                                          "missing primary position", eid))
        elif vc.positions and not vc.position_allowed(gp.position_primary):
            issues.append(ValidationIssue("known_position", "REJECT",
                                          f"position {gp.position_primary!r} not recognized "
                                          f"for {gp.game_version.value}", eid))
        elif not vc.positions:
            issues.append(ValidationIssue("version_position_reference", "REVIEW",
                                          f"{gp.game_version.value} has no position reference "
                                          "table; position cannot be validated", eid))

        for pos in gp.secondary_positions:
            if vc.positions and not vc.position_allowed(pos):
                issues.append(ValidationIssue("known_secondary_position", "REJECT",
                                              f"alternate position {pos!r} not recognized", eid))

        # attribute range check: impossible values rejected
        for code, val in gp.attributes.values.items():
            if val is None:
                continue          # UNKNOWN is legal (§19)
            if not isinstance(val, int) or val not in VALID_RATINGS:
                issues.append(ValidationIssue("attribute_range", "REJECT",
                                              f"attribute {code}={val!r} impossible", eid))

        # GK-specific: outfield facades must be UNKNOWN for GKs in canonical data
        # (source combined-file mirrors are a known artifact — see forensics F1)
        if gp.position_primary == "GK":
            leaked = [c for c in ("pace", "shooting", "passing", "dribbling",
                                 "defending", "physicality")
                      if gp.attributes.get(c) is not None]
            gk_known = [c for c in vc.gk_attributes if gp.attributes.get(c) is not None]
            if leaked and not gk_known:
                issues.append(ValidationIssue("gk_attribute_shape", "REVIEW",
                                              "GK row carries outfield facades but no GK "
                                              "attributes — possible facade-mirroring artifact", eid))
            if not gk_known:
                issues.append(ValidationIssue("gk_attributes_missing", "REVIEW",
                                              "GK technical attributes UNKNOWN — GK fit will "
                                              "report INSUFFICIENT_EVIDENCE", eid))

        if gp.identity_status.value == "REVIEW_REQUIRED":
            issues.append(ValidationIssue("identity_ambiguous", "REVIEW",
                                          "identity resolution flagged REVIEW_REQUIRED", eid))
        return ValidationResult(ok=not any(i.severity == "REJECT" for i in issues),
                                issues=issues)

    # ------------------------------------------------------------------ cards
    def validate_card(self, card: UTCard) -> ValidationResult:
        issues: list[ValidationIssue] = []
        vc = self.version_config(card.game_version.value)
        eid = str(card.id)

        if not card.card_name or not card.card_name.strip():
            issues.append(ValidationIssue("required_card_name", "REJECT",
                                          "missing card name", eid))
        if not card.source_card_id:
            issues.append(ValidationIssue("required_source_card_id", "REJECT",
                                          "missing source card id (§39: prefer stable source ids)", eid))
        if card.overall_rating is None:
            if card.validation_hints.get("rating_unparseable"):
                issues.append(ValidationIssue(
                    "invalid_rating", "REJECT",
                    f"overall rating {card.validation_hints['rating_unparseable']!r} "
                    "is not a valid number", eid))
            else:
                issues.append(ValidationIssue("required_rating", "REJECT",
                                              "missing overall rating", eid))
        elif card.overall_rating not in VALID_RATINGS:
            issues.append(ValidationIssue("rating_range", "REJECT",
                                          f"overall rating {card.overall_rating!r} outside 1-99", eid))
        if not card.position:
            issues.append(ValidationIssue("required_position", "REJECT",
                                          "missing position", eid))
        elif vc.positions and not vc.position_allowed(card.position):
            issues.append(ValidationIssue("known_position", "REJECT",
                                          f"position {card.position!r} not recognized", eid))

        for code, val in card.attribute_overrides.items():
            if val is not None and val not in VALID_RATINGS:
                issues.append(ValidationIssue("attribute_range", "REJECT",
                                              f"override {code}={val!r} impossible", eid))

        # PlayStyle+ cap: version-aware reference table. Absent cap => UNKNOWN,
        # which is reported for review rather than guessed.
        cap = vc.playstyle_plus_cap("card") or vc.playstyle_plus_cap("player_base")
        n_plus = len(card.playstyles_plus)
        if cap is None:
            if n_plus > 0:
                issues.append(ValidationIssue("playstyle_plus_cap_unknown", "REVIEW",
                                              f"{card.game_version.value} has no recorded "
                                              f"PlayStyle+ cap; {n_plus} plus styles present", eid))
        elif n_plus > cap:
            issues.append(ValidationIssue("playstyle_plus_cap", "REJECT",
                                          f"{n_plus} PlayStyle+ exceeds cap {cap} for "
                                          f"{card.game_version.value}", eid))

        # PlayStyle+ must be a subset of base PlayStyles on a card
        base = set(card.playstyles_base)
        stray = [p for p in card.playstyles_plus if p not in base]
        if stray:
            issues.append(ValidationIssue("playstyle_plus_subset", "REJECT",
                                          f"PlayStyle+ not present in base PlayStyles: {stray}", eid))

        if card.rarity and card.rarity not in _KNOWN_RARITIES:
            issues.append(ValidationIssue("known_rarity", "REVIEW",
                                          f"unrecognized rarity {card.rarity!r}", eid))
        return ValidationResult(ok=not any(i.severity == "REJECT" for i in issues),
                                issues=issues)


_KNOWN_RARITIES = {"bronze", "silver", "gold", "totw", "icons", "hero",
                   "icon", "heroes", "toty", "ucl", "evo"}
