"""User-side domain model: requirements, squad context, preferences, feedback."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

TACTICAL_PROFILES = (
    "PACE_ABUSER", "COUNTER_ATTACK", "POSSESSION", "DRIBBLE_HEAVY", "PRESSING",
    "CROSSING", "LONG_SHOT", "DIRECT_PLAY", "BUILD_UP", "BALANCED", "CUSTOM",
    # v2.1 additions (§7 minimum set) — additive; legacy keys untouched
    "HIGH_PRESS", "MID_BLOCK", "LOW_BLOCK", "FAST_BUILD_UP", "SLOW_BUILD_UP",
)


@dataclass
class AttributePreference:
    """A user's desired level for one attribute (0-99 target, or 'important' weight)."""
    attribute: str
    min_value: Optional[int] = None      # hard floor when set
    target_value: Optional[int] = None   # soft target used for fit shaping
    weight: float = 1.0                  # relative importance within attribute_fit


@dataclass
class AttributeBand:
    """Qualitative requirement (§11): 'excellent pace' -> configurable soft
    target band. NEVER a hard floor; band mapping lives in engine_config."""
    attribute: str
    band: str                      # elite|excellent|very_good|good|average|weak


@dataclass
class UserRequirements:
    """Structured form of 'what THIS user needs for THIS situation'."""
    game_version: str = "FC26"
    position: Optional[str] = None
    formation: Optional[str] = None
    tactical_profile: str = "BALANCED"
    custom_tactics: dict[str, float] = field(default_factory=dict)  # attr->weight for CUSTOM
    role: Optional[str] = None
    attribute_preferences: list[AttributePreference] = field(default_factory=list)
    desired_playstyles: list[str] = field(default_factory=list)
    desired_playstyles_plus: list[str] = field(default_factory=list)
    budget_coins: Optional[int] = None          # None = no budget constraint
    min_overall: Optional[int] = None
    max_overall: Optional[int] = None
    squad_id: Optional[uuid.UUID] = None
    entity_scope: str = "auto"                  # 'auto' | 'game_player' | 'ut_card'
    strict_tactics: bool = False                # enforce tactical floor as hard exclusion
    limit: int = 10
    # ---- v2.1 intelligence inputs (all optional; legacy requests unaffected) ----
    archetype: Optional[str] = None             # §15 requested archetype (computed, never assigned)
    slot: Optional[str] = None                  # §6 formation slot (e.g. "LAM" in 4-2-3-1)
    secondary_tactical_profile: Optional[str] = None   # §7 tactical combination
    attribute_bands: list[AttributeBand] = field(default_factory=list)  # §11
    enable_interactions: bool = False           # §9 attribute interaction features
    enable_saturation: bool = False             # §10 diminishing returns
    enable_playstyle_context: bool = False      # §12/§13 contextual PlayStyle value
    required_playstyles: list[str] = field(default_factory=list)  # §2 HARD PlayStyle reqs
    required_league: Optional[str] = None       # §2 HARD link requirements
    required_club: Optional[str] = None
    required_nation: Optional[str] = None
    replacement_for: Optional[uuid.UUID] = None # §20 replacement intelligence
    overall_quality_bias: Optional[str] = None  # 'low'|'normal'|'high' (§72/§74)
    complement_hint: Optional[dict] = None      # §19 pair-complement hint from intent
    disable_counterfactuals: bool = False       # §37 perf opt-out

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.tactical_profile not in TACTICAL_PROFILES:
            problems.append(f"unknown tactical_profile {self.tactical_profile!r}")
        if self.entity_scope not in ("auto", "game_player", "ut_card"):
            problems.append(f"unknown entity_scope {self.entity_scope!r}")
        if self.budget_coins is not None and self.budget_coins < 0:
            problems.append("budget_coins must be >= 0")
        if self.min_overall is not None and not (1 <= self.min_overall <= 99):
            problems.append("min_overall out of range")
        if self.max_overall is not None and not (1 <= self.max_overall <= 99):
            problems.append("max_overall out of range")
        if self.min_overall and self.max_overall and self.min_overall > self.max_overall:
            problems.append("min_overall > max_overall")
        for p in self.attribute_preferences:
            if p.min_value is not None and not (1 <= p.min_value <= 99):
                problems.append(f"attribute {p.attribute}: min_value out of range")
            if p.weight < 0:
                problems.append(f"attribute {p.attribute}: negative weight")
        if not 1 <= self.limit <= 50:
            problems.append("limit must be between 1 and 50")
        # ---- v2.1 validation (unknown values are rejected, never guessed) ----
        if self.secondary_tactical_profile is not None \
                and self.secondary_tactical_profile not in TACTICAL_PROFILES:
            problems.append(f"unknown secondary_tactical_profile "
                            f"{self.secondary_tactical_profile!r}")
        if self.archetype is not None:
            from backend.services.archetypes import ARCHETYPE_DEFINITIONS
            if self.archetype.strip().upper() not in ARCHETYPE_DEFINITIONS:
                problems.append(f"unknown archetype {self.archetype!r}; known: "
                                f"{sorted(ARCHETYPE_DEFINITIONS)}")
        from backend.services.engine_config import QUALITY_BANDS
        for b in self.attribute_bands:
            if b.band not in QUALITY_BANDS:
                problems.append(f"unknown band {b.band!r} for {b.attribute}; "
                                f"known: {sorted(QUALITY_BANDS)}")
        if self.overall_quality_bias is not None and \
                self.overall_quality_bias not in ("low", "normal", "high"):
            problems.append("overall_quality_bias must be low|normal|high")
        return problems


@dataclass
class SquadSlot:
    slot_index: int
    slot_position: str
    game_player_id: Optional[uuid.UUID] = None
    ut_card_id: Optional[uuid.UUID] = None
    # denormalized link facts (verified values only; UNKNOWN stays None)
    club: Optional[str] = None
    league: Optional[str] = None
    nation: Optional[str] = None


@dataclass
class SquadContext:
    squad_id: Optional[uuid.UUID]
    formation: str
    game_version: str
    slots: list[SquadSlot] = field(default_factory=list)

    def filled_slots(self) -> list[SquadSlot]:
        return [s for s in self.slots if s.game_player_id or s.ut_card_id]


@dataclass
class FeedbackEvent:
    action: str                       # SHOWN | SELECTED | REJECTED | ALTERNATIVE_SELECTED | SAVED
    entity_type: str
    entity_id: Optional[uuid.UUID]
    game_version: str
    request_context: dict[str, Any] = field(default_factory=dict)
    recommendation_id: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
    reason: Optional[str] = None
