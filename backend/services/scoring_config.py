"""Deterministic scoring configuration for Recommendation Engine V2.

Everything the engine needs is declared here (or in version-aware reference
tables) — no hidden magic numbers inside scoring code.

Top-level component weights (documented project convention):
    overall_quality 0.15 | attribute_fit 0.30 | position_fit 0.15
    tactical_fit    0.15 | playstyle_fit 0.15 | team_fit      0.10
`role_fit` is evaluated and reported but is not part of the top-level weight
table (matches the documented V2 design); it acts as an advisory gate until
real Role data exists.

Unknown components are NOT penalized: their weight is redistributed
proportionally across KNOWN components (see recommendation_engine_v2).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------- weights
COMPONENT_WEIGHTS: dict[str, float] = {
    "overall_quality": 0.15,
    "attribute_fit": 0.30,
    "position_fit": 0.15,
    "tactical_fit": 0.15,
    "playstyle_fit": 0.15,
    "team_fit": 0.10,
}
assert abs(sum(COMPONENT_WEIGHTS.values()) - 1.0) < 1e-9

WEIGHTED_COMPONENTS = tuple(COMPONENT_WEIGHTS)
ADVISORY_COMPONENTS = ("role_fit",)

# Minimum tactical fit for strict mode / down-ranking (tactical alignment floor)
TACTICAL_FIT_FLOOR = 0.35

# overall_quality normalization curve (absolute, deterministic).
# Calibrated on observed FC26 OVR range (47-91, CC0 foundation).
OVR_QUALITY_FLOOR = 55
OVR_QUALITY_CEIL = 92

# attribute_fit: below this share of required-weight evidence, the component is
# INSUFFICIENT_EVIDENCE rather than a shaky score.
ATTRIBUTE_EVIDENCE_MIN_COVERAGE = 0.5

# position_fit ladder
POSITION_FIT_EXACT = 1.0
POSITION_FIT_SECONDARY = 0.85
POSITION_FIT_FALLBACK = 0.05

# Adjacency (>=0.4 is considered "compatible" for candidate pre-filtering)
POSITION_ADJACENCY: dict[str, dict[str, float]] = {
    "CB":  {"LB": 0.40, "RB": 0.40, "CDM": 0.30},
    "LB":  {"CB": 0.45, "RB": 0.50, "LM": 0.40, "CDM": 0.25},
    "RB":  {"CB": 0.45, "LB": 0.50, "RM": 0.40, "CDM": 0.25},
    "CDM": {"CM": 0.60, "CB": 0.30, "LB": 0.25, "RB": 0.25},
    "CM":  {"CDM": 0.60, "CAM": 0.60, "LM": 0.45, "RM": 0.45},
    "CAM": {"CM": 0.60, "LM": 0.50, "RM": 0.50, "LW": 0.40, "RW": 0.40, "ST": 0.35},
    "LM":  {"LW": 0.60, "CAM": 0.50, "CM": 0.45, "LB": 0.40, "RM": 0.50},
    "RM":  {"RW": 0.60, "CAM": 0.50, "CM": 0.45, "RB": 0.40, "LM": 0.50},
    "LW":  {"LM": 0.60, "ST": 0.50, "RW": 0.45, "CAM": 0.40},
    "RW":  {"RM": 0.60, "ST": 0.50, "LW": 0.45, "CAM": 0.40},
    "ST":  {"LW": 0.50, "RW": 0.50, "CAM": 0.35},
    "GK":  {},
}

# ---------------------------------------------------------------- position profiles
# Position-specific attribute importance (relative weights; normalized at use).
# GK uses GK-specific attributes (real data available since the 2026-03 scrape).
POSITION_ATTRIBUTE_WEIGHTS: dict[str, dict[str, float]] = {
    "GK": {"gk_diving": 22, "gk_handling": 18, "gk_kicking": 14,
           "gk_positioning": 23, "gk_reflexes": 23},
    "CB": {"defending": 18, "standing_tackle": 12, "interceptions": 11,
           "heading_accuracy": 10, "strength": 12, "defensive_awareness": 11,
           "jumping": 8, "aggression": 7, "reactions": 6, "pace": 5},
    "LB": {"defending": 14, "pace": 14, "stamina": 10, "crossing": 9,
           "standing_tackle": 9, "interceptions": 8, "defensive_awareness": 8,
           "dribbling_detail": 6, "short_passing": 6, "strength": 5, "acceleration": 6,
           "sprint_speed": 5},
    "RB": {"defending": 14, "pace": 14, "stamina": 10, "crossing": 9,
           "standing_tackle": 9, "interceptions": 8, "defensive_awareness": 8,
           "dribbling_detail": 6, "short_passing": 6, "strength": 5, "acceleration": 6,
           "sprint_speed": 5},
    "CDM": {"defending": 13, "interceptions": 11, "standing_tackle": 10,
            "short_passing": 10, "defensive_awareness": 10, "strength": 9,
            "stamina": 8, "aggression": 7, "long_passing": 7, "vision": 6,
            "ball_control": 5, "positioning": 4},
    "CM": {"short_passing": 12, "vision": 11, "long_passing": 10, "stamina": 10,
           "ball_control": 9, "defensive_awareness": 7, "interceptions": 6,
           "positioning": 6, "composure": 7, "dribbling_detail": 6, "strength": 5,
           "long_shots": 5},
    "CAM": {"vision": 13, "short_passing": 12, "dribbling_detail": 11,
            "ball_control": 9, "long_shots": 8, "finishing": 7, "composure": 8,
            "curve": 6, "agility": 7, "positioning": 6, "long_passing": 5},
    "LM": {"pace": 12, "crossing": 12, "stamina": 10, "dribbling_detail": 10,
           "short_passing": 8, "curve": 6, "agility": 7, "long_passing": 6,
           "defending": 5, "finishing": 5, "acceleration": 8, "balance": 5},
    "RM": {"pace": 12, "crossing": 12, "stamina": 10, "dribbling_detail": 10,
           "short_passing": 8, "curve": 6, "agility": 7, "long_passing": 6,
           "defending": 5, "finishing": 5, "acceleration": 8, "balance": 5},
    "LW": {"pace": 14, "dribbling_detail": 13, "finishing": 9, "agility": 8,
           "ball_control": 8, "crossing": 7, "curve": 6, "composure": 6,
           "acceleration": 10, "balance": 7, "short_passing": 5, "long_shots": 5},
    "RW": {"pace": 14, "dribbling_detail": 13, "finishing": 9, "agility": 8,
           "ball_control": 8, "crossing": 7, "curve": 6, "composure": 6,
           "acceleration": 10, "balance": 7, "short_passing": 5, "long_shots": 5},
    "ST": {"finishing": 16, "positioning": 12, "shot_power": 9, "pace": 11,
           "composure": 8, "heading_accuracy": 6, "volleys": 6, "long_shots": 5,
           "strength": 6, "agility": 6, "ball_control": 6, "acceleration": 6,
           "reactions": 5, "dribbling_detail": 4},
}

# ---------------------------------------------------------------- tactical profiles
# Attribute weightings expressing what a tactical system demands. BALANCED has
# no demand -> tactical_fit returns UNKNOWN (redistributed, no penalty).
TACTICAL_ATTRIBUTE_WEIGHTS: dict[str, dict[str, float]] = {
    "PACE_ABUSER": {"acceleration": 20, "sprint_speed": 20, "pace": 18,
                    "agility": 10, "stamina": 8, "reactions": 6, "dribbling_detail": 8,
                    "balance": 5, "composure": 5},
    "COUNTER_ATTACK": {"acceleration": 16, "sprint_speed": 16, "pace": 12,
                       "long_passing": 8, "vision": 8, "finishing": 8, "composure": 6,
                       "stamina": 8, "positioning": 6, "short_passing": 6, "reactions": 6},
    "POSSESSION": {"short_passing": 18, "vision": 14, "ball_control": 14,
                   "composure": 12, "long_passing": 8, "dribbling_detail": 8,
                   "positioning": 8, "reactions": 6, "curve": 6, "agility": 6},
    "DRIBBLE_HEAVY": {"dribbling_detail": 20, "agility": 14, "balance": 14,
                      "ball_control": 12, "pace": 8, "acceleration": 8,
                      "composure": 6, "curve": 5, "reactions": 5, "strength": 4},
    "PRESSING": {"stamina": 18, "aggression": 14, "interceptions": 12,
                 "defensive_awareness": 10, "standing_tackle": 8, "positioning": 8,
                 "reactions": 8, "strength": 7, "acceleration": 7, "pace": 6},
    "CROSSING": {"crossing": 22, "curve": 12, "long_passing": 10, "vision": 10,
                 "pace": 8, "acceleration": 6, "dribbling_detail": 6,
                 "short_passing": 6, "stamina": 6, "finishing": 4, "heading_accuracy": 6},
    "LONG_SHOT": {"long_shots": 22, "shot_power": 16, "curve": 10, "finishing": 10,
                  "composure": 8, "vision": 6, "free_kick_accuracy": 6,
                  "positioning": 6, "long_passing": 5, "ball_control": 5},
    "DIRECT_PLAY": {"long_passing": 16, "strength": 12, "heading_accuracy": 10,
                    "vision": 10, "shot_power": 8, "pace": 8, "sprint_speed": 8,
                    "aggression": 7, "jumping": 7, "positioning": 6, "crossing": 5},
    "BUILD_UP": {"short_passing": 16, "long_passing": 12, "vision": 12,
                 "ball_control": 10, "composure": 10, "defensive_awareness": 6,
                 "positioning": 6, "standing_tackle": 5, "interceptions": 5,
                 "reactions": 6, "stamina": 6},
    # v2.1 additions (§7): documented engine conventions, same style as above.
    "HIGH_PRESS": {"stamina": 18, "aggression": 12, "interceptions": 10,
                   "defensive_awareness": 9, "acceleration": 9, "pace": 8,
                   "reactions": 8, "standing_tackle": 7, "positioning": 7,
                   "strength": 6},
    "MID_BLOCK": {"defensive_awareness": 14, "positioning": 13, "interceptions": 11,
                  "standing_tackle": 10, "stamina": 10, "strength": 8,
                  "reactions": 7, "short_passing": 7, "aggression": 6},
    "LOW_BLOCK": {"defensive_awareness": 16, "positioning": 15, "standing_tackle": 13,
                  "interceptions": 12, "strength": 12, "heading_accuracy": 9,
                  "aggression": 7, "reactions": 6, "jumping": 6, "short_passing": 4},
    "FAST_BUILD_UP": {"acceleration": 13, "short_passing": 12, "sprint_speed": 11,
                      "composure": 11, "reactions": 11, "ball_control": 9,
                      "vision": 9, "long_passing": 7, "agility": 6, "stamina": 6},
    "SLOW_BUILD_UP": {"short_passing": 16, "composure": 13, "ball_control": 13,
                      "vision": 12, "long_passing": 8, "positioning": 8,
                      "reactions": 6, "defensive_awareness": 5, "stamina": 5,
                      "strength": 4},
    "BALANCED": {},   # no tactical demand -> UNKNOWN component
    "CUSTOM": {},     # weights come from requirements.custom_tactics
}

TACTICAL_PROFILE_PLAYSTYLES: dict[str, list[str]] = {
    # advisory only (reported in explanations; not scored without user request)
    "PACE_ABUSER": ["Quick Step", "Rapid"],
    "COUNTER_ATTACK": ["Quick Step", "Rapid", "Incisive Pass", "Pinged Pass"],
    "POSSESSION": ["Tiki Taka", "First Touch", "Technical", "Inventive"],
    "DRIBBLE_HEAVY": ["Trickster", "First Touch", "Technical", "Acrobatic"],
    "PRESSING": ["Press Proven", "Relentless", "Anticipate", "Jockey", "Enforcer"],
    "CROSSING": ["Whipped Pass", "Dead Ball", "Precision Header", "Aerial Fortress"],
    "LONG_SHOT": ["Power Shot", "Finesse Shot", "Low Driven Shot", "Dead Ball"],
    "DIRECT_PLAY": ["Long Ball Pass", "Pinged Pass", "Power Shot", "Aerial Fortress"],
    "BUILD_UP": ["Tiki Taka", "Pinged Pass", "Long Ball Pass", "Inventive", "Gamechanger"],
    "HIGH_PRESS": ["Press Proven", "Relentless", "Anticipate", "Jockey", "Enforcer", "Quick Step"],
    "MID_BLOCK": ["Anticipate", "Jockey", "Intercept", "Block", "Enforcer"],
    "LOW_BLOCK": ["Block", "Bruiser", "Enforcer", "Aerial Fortress", "Intercept", "Anticipate", "Slide Tackle"],
    "FAST_BUILD_UP": ["Quick Step", "Rapid", "Pinged Pass", "Incisive Pass", "First Touch", "Long Ball Pass"],
    "SLOW_BUILD_UP": ["Tiki Taka", "First Touch", "Technical", "Inventive", "Pinged Pass"],
    "BALANCED": [],
    "CUSTOM": [],
}


# ---------------------------------------------------------------- version config
@dataclass(frozen=True)
class VersionConfig:
    """Version-aware reference configuration (replaces hardcoded FC26 assumptions).

    In production, loaded from game_version.config (reference table). The
    fallback below exists so pure-engine unit tests remain DB-independent; it
    mirrors the FC26 row seeded in db/seed_reference_data.sql.
    """
    code: str
    positions: tuple[str, ...]
    position_types: dict[str, list[str]]
    facades: tuple[str, ...]
    gk_attributes: tuple[str, ...]
    playstyle_plus_caps: dict[str, int]      # scope -> cap; absence = UNKNOWN
    roles_available: bool
    market_data_available: bool
    chemistry_rules_verified: bool
    women_universe_included: Optional[bool] = None
    data_status: str = "ACTIVE"

    def position_allowed(self, pos: str) -> bool:
        return not self.positions or pos in self.positions

    def playstyle_plus_cap(self, scope: str) -> Optional[int]:
        return self.playstyle_plus_caps.get(scope)   # None => UNKNOWN, do not guess


_FC26_FALLBACK = VersionConfig(
    code="FC26",
    positions=("GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "ST"),
    position_types={"Defense": ["GK", "CB", "LB", "RB"],
                    "Midfielder": ["CDM", "CM", "CAM", "LM", "RM"],
                    "Attack": ["LW", "RW", "ST"]},
    facades=("pace", "shooting", "passing", "dribbling", "defending", "physicality"),
    gk_attributes=("gk_diving", "gk_handling", "gk_kicking", "gk_positioning", "gk_reflexes"),
    # evidence-based cap (forensics: max 1 per player across all 119 PS+ holders)
    playstyle_plus_caps={"player_base": 1},
    roles_available=False,
    market_data_available=False,
    chemistry_rules_verified=False,
    women_universe_included=False,
)

# FC27: NO DATA. An empty/unknown config; nothing is copied from FC26.
_FC27_FALLBACK = VersionConfig(
    code="FC27",
    positions=(),                 # UNKNOWN until FC27 data legitimately exists
    position_types={},
    facades=("pace", "shooting", "passing", "dribbling", "defending", "physicality"),
    gk_attributes=("gk_diving", "gk_handling", "gk_kicking", "gk_positioning", "gk_reflexes"),
    playstyle_plus_caps={},       # UNKNOWN — deliberately not guessed
    roles_available=False,
    market_data_available=False,
    chemistry_rules_verified=False,
    women_universe_included=None,
    data_status="NO_DATA",
)

_VERSION_FALLBACKS: dict[str, VersionConfig] = {"FC26": _FC26_FALLBACK, "FC27": _FC27_FALLBACK}


class ScoringConfig:
    """Immutable-ish runtime configuration bundle for the engine."""

    def __init__(self,
                 component_weights: Optional[dict[str, float]] = None,
                 version_configs: Optional[dict[str, VersionConfig]] = None,
                 tactical_floor: float = TACTICAL_FIT_FLOOR):
        self.component_weights = dict(component_weights or COMPONENT_WEIGHTS)
        self.version_configs = dict(version_configs or _VERSION_FALLBACKS)
        self.tactical_floor = tactical_floor
        # §29: normalized weight tables are pure per position/profile — they
        # are rebuilt thousands of times per request without this cache.
        self._weights_cache: dict[tuple, dict[str, float]] = {}

    def version(self, code: str) -> VersionConfig:
        key = str(code).strip().upper()
        if key not in self.version_configs:
            raise KeyError(
                f"No version configuration for {key!r}. Add it to game_version "
                f"(DB) or VersionConfig fallbacks. Versions are never silently "
                f"substituted — FC26 config must not be used for FC27.")
        return self.version_configs[key]

    @classmethod
    def with_versions(cls, configs: list[VersionConfig]) -> "ScoringConfig":
        return cls(version_configs={c.code: c for c in configs})

    # -- profile helpers ------------------------------------------------------
    def position_attribute_weights(self, position: str) -> dict[str, float]:
        cached = self._weights_cache.get(("pos", position))
        if cached is not None:
            return cached
        raw = POSITION_ATTRIBUTE_WEIGHTS.get(position)
        if not raw:
            self._weights_cache[("pos", position)] = {}
            return {}
        total = sum(raw.values())
        out = {k: v / total for k, v in raw.items()}
        self._weights_cache[("pos", position)] = out
        return out

    def tactical_attribute_weights(self, profile: str,
                                   custom: Optional[dict[str, float]] = None) -> dict[str, float]:
        cacheable = custom is None and profile != "CUSTOM"
        if cacheable:
            cached = self._weights_cache.get(("tac", profile))
            if cached is not None:
                return cached
        raw = (custom or {}) if profile == "CUSTOM" else TACTICAL_ATTRIBUTE_WEIGHTS.get(profile, {})
        if not raw:
            if cacheable:
                self._weights_cache[("tac", profile)] = {}
            return {}
        total = sum(raw.values())
        out = {k: v / total for k, v in raw.items()}
        if cacheable:
            self._weights_cache[("tac", profile)] = out
        return out

    def tactical_playstyles(self, profile: str) -> list[str]:
        return list(TACTICAL_PROFILE_PLAYSTYLES.get(profile, []))


def compatible_positions(position: str) -> set[str]:
    """Positions whose fit vs `position` clears the 0.4 adjacency bar
    (plus the exact position). Used for candidate pre-filtering only —
    precise scoring still happens in position_fit."""
    out = {position}
    for other, adj in POSITION_ADJACENCY.items():
        if other == position:
            out |= {p for p, v in adj.items() if v >= 0.4}
        elif adj.get(position, 0.0) >= 0.4:
            out.add(other)
    return out
