"""FORMATION + TACTICAL-DIMENSION intelligence (§6, §7).

Formations are represented as tactical slots, not flat position lists. A slot
carries: the base position, side, duty (DEFEND/SUPPORT/ATTACK) and an attribute
emphasis. Duties/emphases are ENGINE-DERIVED tactical conventions (configurable,
documented) — NOT official EA data, and never presented as such.

Tactical profiles are decomposed into a dimension vector (press intensity,
block height, build-up speed, width, directness, tempo). Combinations
(e.g. PRESSING + FAST_BUILD_UP) merge dimension vectors and derive attribute
importance from them — producing a DIFFERENT profile than PRESSING alone or
PRESSING + POSSESSION. The legacy single-profile tables in scoring_config stay
untouched; dimension-derived weights are only used when a combination or slot
context is explicitly requested.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# §7 — tactical dimensions (0..1). Every profile maps to a vector; combos merge.
# ---------------------------------------------------------------------------
TACTICAL_DIMENSIONS = (
    "press_intensity",    # how aggressively/high the team defends
    "block_height",       # defensive line height
    "build_up_speed",     # how quickly play moves from back to front
    "width",              # reliance on wide areas/crosses
    "directness",         # long balls / verticality vs circulation
    "tempo",              # overall speed of play
)

PROFILE_DIMENSIONS: dict[str, dict[str, float]] = {
    # legacy V2 profiles (dimensions added; legacy scoring paths unchanged)
    "PACE_ABUSER":    {"press_intensity": 0.4, "block_height": 0.5, "build_up_speed": 0.8,
                       "width": 0.6, "directness": 0.6, "tempo": 0.9},
    "COUNTER_ATTACK": {"press_intensity": 0.5, "block_height": 0.4, "build_up_speed": 0.9,
                       "width": 0.5, "directness": 0.7, "tempo": 0.85},
    "POSSESSION":     {"press_intensity": 0.5, "block_height": 0.6, "build_up_speed": 0.35,
                       "width": 0.6, "directness": 0.2, "tempo": 0.4},
    "DRIBBLE_HEAVY":  {"press_intensity": 0.4, "block_height": 0.5, "build_up_speed": 0.5,
                       "width": 0.5, "directness": 0.4, "tempo": 0.55},
    "PRESSING":       {"press_intensity": 0.95, "block_height": 0.8, "build_up_speed": 0.6,
                       "width": 0.5, "directness": 0.4, "tempo": 0.75},
    "CROSSING":       {"press_intensity": 0.4, "block_height": 0.5, "build_up_speed": 0.55,
                       "width": 0.95, "directness": 0.55, "tempo": 0.55},
    "LONG_SHOT":      {"press_intensity": 0.4, "block_height": 0.5, "build_up_speed": 0.5,
                       "width": 0.4, "directness": 0.65, "tempo": 0.55},
    "DIRECT_PLAY":    {"press_intensity": 0.5, "block_height": 0.5, "build_up_speed": 0.7,
                       "width": 0.4, "directness": 0.9, "tempo": 0.7},
    "BUILD_UP":       {"press_intensity": 0.4, "block_height": 0.55, "build_up_speed": 0.45,
                       "width": 0.5, "directness": 0.25, "tempo": 0.45},
    "BALANCED":       {"press_intensity": 0.5, "block_height": 0.5, "build_up_speed": 0.5,
                       "width": 0.5, "directness": 0.5, "tempo": 0.5},
    # NEW profiles (§7 minimum set); registered in user_model TACTICAL_PROFILES
    # and scoring_config TACTICAL_ATTRIBUTE_WEIGHTS.
    "HIGH_PRESS":     {"press_intensity": 0.95, "block_height": 0.85, "build_up_speed": 0.65,
                       "width": 0.5, "directness": 0.4, "tempo": 0.8},
    "MID_BLOCK":      {"press_intensity": 0.45, "block_height": 0.45, "build_up_speed": 0.45,
                       "width": 0.45, "directness": 0.45, "tempo": 0.45},
    "LOW_BLOCK":      {"press_intensity": 0.2, "block_height": 0.2, "build_up_speed": 0.4,
                       "width": 0.4, "directness": 0.5, "tempo": 0.35},
    "FAST_BUILD_UP":  {"press_intensity": 0.5, "block_height": 0.55, "build_up_speed": 0.9,
                       "width": 0.5, "directness": 0.55, "tempo": 0.85},
    "SLOW_BUILD_UP":  {"press_intensity": 0.4, "block_height": 0.55, "build_up_speed": 0.2,
                       "width": 0.55, "directness": 0.15, "tempo": 0.3},
    "CUSTOM":         {},
}

# dimension -> attribute affinities (how each dimension shifts importance).
# Positive/negative deltas applied to position base weights, then renormalized.
DIMENSION_ATTRIBUTE_AFFINITY: dict[str, dict[str, float]] = {
    "press_intensity": {"stamina": 0.30, "aggression": 0.25, "interceptions": 0.20,
                        "defensive_awareness": 0.15, "reactions": 0.10, "positioning": 0.05},
    "block_height":    {"defensive_awareness": 0.15, "positioning": 0.15, "pace": 0.20,
                        "acceleration": 0.15, "interceptions": 0.10, "reactions": 0.05},
    "build_up_speed":  {"acceleration": 0.15, "sprint_speed": 0.10, "short_passing": 0.15,
                        "composure": 0.15, "reactions": 0.15, "ball_control": 0.10,
                        "first_touch_dummy": 0.0},
    "width":           {"crossing": 0.25, "stamina": 0.15, "pace": 0.15, "long_passing": 0.10,
                        "curve": 0.05},
    "directness":      {"long_passing": 0.20, "heading_accuracy": 0.15, "strength": 0.15,
                        "shot_power": 0.10, "sprint_speed": 0.10, "vision": 0.05},
    "tempo":           {"reactions": 0.20, "agility": 0.15, "short_passing": 0.15,
                        "composure": 0.10, "acceleration": 0.10, "stamina": 0.10},
}
# remove the placeholder key defensively (documents that no attr is invented)
DIMENSION_ATTRIBUTE_AFFINITY["build_up_speed"].pop("first_touch_dummy", None)

# dimension value below/above which it does not shift weights (neutral band)
DIMENSION_NEUTRAL = 0.5
DIMENSION_MAX_SHIFT = 0.6   # max multiplier applied to affinity at extreme (0 or 1)


def dimension_vector(profile: str,
                     secondary: Optional[str] = None,
                     primary_share: float = 0.6) -> dict[str, float]:
    """Merged tactical dimension vector. Single profile -> its own vector.
    Combination -> weighted merge (primary_share vs 1-primary_share).
    BALANCED/CUSTOM contribute their vector/empty as defined."""
    prim = PROFILE_DIMENSIONS.get(profile.upper(), {})
    if not secondary:
        return dict(prim)
    sec = PROFILE_DIMENSIONS.get(secondary.upper(), {})
    if not prim:
        return dict(sec)
    if not sec:
        return dict(prim)
    merged = {}
    for dim in TACTICAL_DIMENSIONS:
        p, s = prim.get(dim), sec.get(dim)
        if p is None and s is None:
            continue
        merged[dim] = (primary_share * (p if p is not None else s)
                       + (1 - primary_share) * (s if s is not None else p))
    return merged


def attribute_weights_from_dimensions(position_weights: dict[str, float],
                                      dims: dict[str, float]) -> dict[str, float]:
    """Position base importance shifted by tactical dimensions. Deterministic:
    weight' = weight * (1 + Σ_dim affinity[dim][attr] * shift(dim)), where
    shift(dim) = (value - 0.5) * 2 * DIMENSION_MAX_SHIFT  (0 at neutral)."""
    if not dims:
        return dict(position_weights)
    out = dict(position_weights)
    for dim, value in dims.items():
        shift = (value - DIMENSION_NEUTRAL) * 2.0 * DIMENSION_MAX_SHIFT
        if abs(shift) < 1e-9:
            continue
        for attr, aff in DIMENSION_ATTRIBUTE_AFFINITY.get(dim, {}).items():
            if attr in out:
                out[attr] = max(0.0, out[attr] * (1.0 + aff * shift))
            # attributes outside the position profile are NOT injected:
            # importance models only re-weight what the position already cares
            # about (keeps GK profiles gk-only etc.)
    total = sum(out.values())
    if total <= 0:
        return dict(position_weights)
    return {k: v / total for k, v in out.items()}


def tactical_weights_from_dimensions(dims: dict[str, float]) -> dict[str, float]:
    """Tactical demand vector derived from (combined) dimensions: each
    dimension's DEMAND is its deviation from neutral (|v-0.5|*2); attribute
    importance = Σ affinity × demand, normalized. Used ONLY for tactical
    combinations (secondary profile set) — legacy single-profile tables in
    scoring_config stay untouched."""
    weights: dict[str, float] = {}
    for dim, value in dims.items():
        demand = abs(value - DIMENSION_NEUTRAL) * 2.0
        if demand < 1e-9:
            continue
        for attr, aff in DIMENSION_ATTRIBUTE_AFFINITY.get(dim, {}).items():
            weights[attr] = weights.get(attr, 0.0) + aff * demand
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()} if total > 0 else {}


# ---------------------------------------------------------------------------
# §6 — formation slots. Base positions match meta.FORMATIONS; slots add side +
# duty + emphasis. Emphasis attributes are per-slot attribute-weight deltas
# (multipliers on the position base weights, same mechanism as dimensions).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FormationSlot:
    slot: str          # e.g. "LDM", "CAM", "LCB"
    position: str      # base position code (GK..ST)
    side: str          # "L" | "C" | "R"
    duty: str          # "DEFEND" | "SUPPORT" | "ATTACK"
    emphasis: dict[str, float]   # attribute multipliers (1.0 = neutral)


def _s(slot, position, side, duty, **emphasis) -> FormationSlot:
    return FormationSlot(slot, position, side, duty, dict(emphasis))


FORMATION_SLOTS: dict[str, list[FormationSlot]] = {
    "4-2-3-1": [
        _s("GK", "GK", "C", "DEFEND"),
        _s("LB", "LB", "L", "SUPPORT", stamina=1.10, pace=1.05, crossing=1.10),
        _s("LCB", "CB", "L", "DEFEND"),
        _s("RCB", "CB", "R", "DEFEND"),
        _s("RB", "RB", "R", "SUPPORT", stamina=1.10, pace=1.05, crossing=1.10),
        _s("LDM", "CDM", "L", "DEFEND", interceptions=1.10, defensive_awareness=1.10),
        _s("RDM", "CDM", "R", "SUPPORT", short_passing=1.10, vision=1.05),
        _s("LAM", "LM", "L", "ATTACK", dribbling_detail=1.10, crossing=1.05, pace=1.05),
        _s("CAM", "CAM", "C", "ATTACK", vision=1.15, short_passing=1.10, composure=1.05),
        _s("RAM", "RM", "R", "ATTACK", dribbling_detail=1.10, crossing=1.05, pace=1.05),
        _s("ST", "ST", "C", "ATTACK", finishing=1.10, positioning=1.05),
    ],
    "4-3-3": [
        _s("GK", "GK", "C", "DEFEND"),
        _s("LB", "LB", "L", "SUPPORT", stamina=1.10, pace=1.10, crossing=1.10),
        _s("LCB", "CB", "L", "DEFEND"),
        _s("RCB", "CB", "R", "DEFEND"),
        _s("RB", "RB", "R", "SUPPORT", stamina=1.10, pace=1.10, crossing=1.10),
        _s("LCM", "CM", "L", "SUPPORT", stamina=1.10, short_passing=1.05),
        _s("CDM", "CM", "C", "DEFEND", defensive_awareness=1.15, interceptions=1.15,
           short_passing=1.05),
        _s("RCM", "CM", "R", "ATTACK", vision=1.10, long_shots=1.05, short_passing=1.05),
        _s("LW", "LW", "L", "ATTACK", dribbling_detail=1.10, finishing=1.05, pace=1.05),
        _s("ST", "ST", "C", "ATTACK", finishing=1.10, positioning=1.05),
        _s("RW", "RW", "R", "ATTACK", dribbling_detail=1.10, finishing=1.05, pace=1.05),
    ],
    "4-4-2": [
        _s("GK", "GK", "C", "DEFEND"),
        _s("LB", "LB", "L", "DEFEND", defensive_awareness=1.05, standing_tackle=1.05),
        _s("LCB", "CB", "L", "DEFEND"),
        _s("RCB", "CB", "R", "DEFEND"),
        _s("RB", "RB", "R", "DEFEND", defensive_awareness=1.05, standing_tackle=1.05),
        _s("LM", "LM", "L", "SUPPORT", stamina=1.15, crossing=1.10, pace=1.05),
        _s("LCM", "CM", "L", "SUPPORT", stamina=1.10, short_passing=1.05),
        _s("RCM", "CM", "R", "SUPPORT", stamina=1.10, short_passing=1.05),
        _s("RM", "RM", "R", "SUPPORT", stamina=1.15, crossing=1.10, pace=1.05),
        _s("LST", "ST", "L", "ATTACK", finishing=1.10, positioning=1.05),
        _s("RST", "ST", "R", "ATTACK", strength=1.10, heading_accuracy=1.10),
    ],
    "4-3-2-1": [
        _s("GK", "GK", "C", "DEFEND"),
        _s("LB", "LB", "L", "SUPPORT", stamina=1.15, pace=1.10, crossing=1.15),
        _s("LCB", "CB", "L", "DEFEND"),
        _s("RCB", "CB", "R", "DEFEND"),
        _s("RB", "RB", "R", "SUPPORT", stamina=1.15, pace=1.10, crossing=1.15),
        _s("LCM", "CM", "L", "SUPPORT", stamina=1.10),
        _s("CDM", "CM", "C", "DEFEND", defensive_awareness=1.15, interceptions=1.15),
        _s("RCM", "CM", "R", "SUPPORT", short_passing=1.10, vision=1.05),
        _s("LF", "CAM", "L", "ATTACK", dribbling_detail=1.10, vision=1.05, finishing=1.05),
        _s("RF", "CAM", "R", "ATTACK", dribbling_detail=1.10, vision=1.05, finishing=1.05),
        _s("ST", "ST", "C", "ATTACK", finishing=1.10, positioning=1.05),
    ],
    "4-5-1": [
        _s("GK", "GK", "C", "DEFEND"),
        _s("LB", "LB", "L", "DEFEND"),
        _s("LCB", "CB", "L", "DEFEND"),
        _s("RCB", "CB", "R", "DEFEND"),
        _s("RB", "RB", "R", "DEFEND"),
        _s("LM", "LM", "L", "SUPPORT", stamina=1.15, crossing=1.10),
        _s("LCM", "CM", "L", "SUPPORT", stamina=1.10, short_passing=1.05),
        _s("CDM", "CM", "C", "DEFEND", defensive_awareness=1.15, interceptions=1.15),
        _s("RCM", "CM", "R", "SUPPORT", stamina=1.10, short_passing=1.05),
        _s("RM", "RM", "R", "SUPPORT", stamina=1.15, crossing=1.10),
        _s("ST", "ST", "C", "ATTACK", finishing=1.10, strength=1.05),
    ],
    "4-1-2-1-2": [
        _s("GK", "GK", "C", "DEFEND"),
        _s("LB", "LB", "L", "SUPPORT", stamina=1.10, pace=1.05),
        _s("LCB", "CB", "L", "DEFEND"),
        _s("RCB", "CB", "R", "DEFEND"),
        _s("RB", "RB", "R", "SUPPORT", stamina=1.10, pace=1.05),
        _s("CDM", "CDM", "C", "DEFEND", interceptions=1.15, defensive_awareness=1.15),
        _s("LCM", "CM", "L", "SUPPORT", stamina=1.10, long_shots=1.05),
        _s("RCM", "CM", "R", "SUPPORT", stamina=1.10),
        _s("CAM", "CAM", "C", "ATTACK", vision=1.15, short_passing=1.10),
        _s("LST", "ST", "L", "ATTACK", finishing=1.10, pace=1.05),
        _s("RST", "ST", "R", "ATTACK", finishing=1.10, strength=1.05),
    ],
    "3-5-2": [
        _s("GK", "GK", "C", "DEFEND"),
        _s("LCB", "CB", "L", "DEFEND"),
        _s("CB", "CB", "C", "DEFEND", short_passing=1.05),
        _s("RCB", "CB", "R", "DEFEND"),
        _s("LWB", "LM", "L", "SUPPORT", stamina=1.25, pace=1.15, crossing=1.15),
        _s("LCM", "CM", "L", "SUPPORT", stamina=1.10),
        _s("CDM", "CDM", "C", "DEFEND", defensive_awareness=1.15, interceptions=1.10),
        _s("RCM", "CM", "R", "SUPPORT", short_passing=1.10, vision=1.05),
        _s("RWB", "RM", "R", "SUPPORT", stamina=1.25, pace=1.15, crossing=1.15),
        _s("LST", "ST", "L", "ATTACK", finishing=1.10),
        _s("RST", "ST", "R", "ATTACK", strength=1.10, heading_accuracy=1.05),
    ],
    "3-4-2-1": [
        _s("GK", "GK", "C", "DEFEND"),
        _s("LCB", "CB", "L", "DEFEND"),
        _s("CB", "CB", "C", "DEFEND", short_passing=1.05),
        _s("RCB", "CB", "R", "DEFEND"),
        _s("LM", "LM", "L", "SUPPORT", stamina=1.20, pace=1.10, crossing=1.10),
        _s("LCM", "CM", "L", "SUPPORT", defensive_awareness=1.05,
           interceptions=1.05, short_passing=1.05),
        _s("RCM", "CM", "R", "SUPPORT", short_passing=1.10, vision=1.05),
        _s("RM", "RM", "R", "SUPPORT", stamina=1.20, pace=1.10, crossing=1.10),
        _s("LAM", "CAM", "L", "ATTACK", vision=1.10, dribbling_detail=1.10,
           finishing=1.05),
        _s("RAM", "CAM", "R", "ATTACK", vision=1.10, dribbling_detail=1.10,
           finishing=1.05),
        _s("ST", "ST", "C", "ATTACK", finishing=1.10, positioning=1.05),
    ],
    "3-4-3": [
        _s("GK", "GK", "C", "DEFEND"),
        _s("LCB", "CB", "L", "DEFEND"),
        _s("CB", "CB", "C", "DEFEND", short_passing=1.05),
        _s("RCB", "CB", "R", "DEFEND"),
        _s("LWB", "LM", "L", "SUPPORT", stamina=1.25, pace=1.15, crossing=1.15),
        _s("LCM", "CM", "L", "SUPPORT", stamina=1.10, defensive_awareness=1.05),
        _s("RCM", "CM", "R", "SUPPORT", short_passing=1.10, vision=1.05),
        _s("RWB", "RM", "R", "SUPPORT", stamina=1.25, pace=1.15, crossing=1.15),
        _s("LW", "LW", "L", "ATTACK", dribbling_detail=1.10, pace=1.05),
        _s("ST", "ST", "C", "ATTACK", finishing=1.10, positioning=1.05),
        _s("RW", "RW", "R", "ATTACK", dribbling_detail=1.10, pace=1.05),
    ],
    "5-3-2": [
        _s("GK", "GK", "C", "DEFEND"),
        _s("LWB", "LB", "L", "DEFEND", stamina=1.15, defensive_awareness=1.05),
        _s("LCB", "CB", "L", "DEFEND"),
        _s("CB", "CB", "C", "DEFEND"),
        _s("RCB", "CB", "R", "DEFEND"),
        _s("RWB", "RB", "R", "DEFEND", stamina=1.15, defensive_awareness=1.05),
        _s("LCM", "CM", "L", "SUPPORT", stamina=1.10),
        _s("CDM", "CM", "C", "DEFEND", interceptions=1.15, defensive_awareness=1.15),
        _s("RCM", "CM", "R", "SUPPORT", short_passing=1.10),
        _s("LST", "ST", "L", "ATTACK", finishing=1.10),
        _s("RST", "ST", "R", "ATTACK", strength=1.10, heading_accuracy=1.05),
    ],
    "5-2-1-2": [
        _s("GK", "GK", "C", "DEFEND"),
        _s("LWB", "LB", "L", "SUPPORT", stamina=1.20, pace=1.10, crossing=1.15),
        _s("LCB", "CB", "L", "DEFEND"),
        _s("CB", "CB", "C", "DEFEND"),
        _s("RCB", "CB", "R", "DEFEND"),
        _s("RWB", "RB", "R", "SUPPORT", stamina=1.20, pace=1.10, crossing=1.15),
        _s("LCDM", "CDM", "L", "DEFEND", defensive_awareness=1.10, interceptions=1.10),
        _s("RCDM", "CDM", "R", "DEFEND", stamina=1.10, short_passing=1.05),
        _s("CAM", "CAM", "C", "ATTACK", vision=1.15, short_passing=1.10, composure=1.05),
        _s("LST", "ST", "L", "ATTACK", finishing=1.10),
        _s("RST", "ST", "R", "ATTACK", finishing=1.05, strength=1.10),
    ],
    "4-2-2-2": [
        _s("GK", "GK", "C", "DEFEND"),
        _s("LB", "LB", "L", "SUPPORT", stamina=1.15, pace=1.10, crossing=1.10),
        _s("LCB", "CB", "L", "DEFEND"),
        _s("RCB", "CB", "R", "DEFEND"),
        _s("RB", "RB", "R", "SUPPORT", stamina=1.15, pace=1.10, crossing=1.10),
        _s("LDM", "CDM", "L", "DEFEND", interceptions=1.15, defensive_awareness=1.10),
        _s("RDM", "CDM", "R", "SUPPORT", short_passing=1.10, stamina=1.05),
        _s("LAM", "CAM", "L", "ATTACK", vision=1.10, dribbling_detail=1.10, crossing=1.05),
        _s("RAM", "CAM", "R", "ATTACK", vision=1.10, dribbling_detail=1.10, crossing=1.05),
        _s("LST", "ST", "L", "ATTACK", finishing=1.10, pace=1.05),
        _s("RST", "ST", "R", "ATTACK", finishing=1.05, strength=1.10),
    ],
}

# alias: the flat lists in api/routes/meta.py remain the API reference; slots
# are the scoring-side view. Tests assert both describe the same 11 positions.


def slots_for(formation: Optional[str]) -> list[FormationSlot]:
    if not formation:
        return []
    return FORMATION_SLOTS.get(formation.strip(), [])


def find_slot(formation: Optional[str], slot_name: Optional[str]) -> Optional[FormationSlot]:
    if not formation or not slot_name:
        return None
    key = slot_name.strip().upper()
    for s in slots_for(formation):
        if s.slot.upper() == key:
            return s
    return None


def slot_for_position(formation: Optional[str], position: str) -> Optional[FormationSlot]:
    """First slot matching a base position (deterministic: declaration order)."""
    if not formation or not position:
        return None
    pos = position.strip().upper()
    for s in slots_for(formation):
        if s.position == pos:
            return s
    return None


def slot_adjusted_weights(position_weights: dict[str, float],
                          slot: Optional[FormationSlot]) -> dict[str, float]:
    """Apply slot emphasis multipliers to position base weights, renormalize.
    Unknown emphasis keys are ignored (never inject non-position attributes)."""
    if slot is None or not slot.emphasis or not position_weights:
        return dict(position_weights)
    out = {}
    for attr, w in position_weights.items():
        out[attr] = w * slot.emphasis.get(attr, 1.0)
    total = sum(out.values())
    if total <= 0:
        return dict(position_weights)
    return {k: v / total for k, v in out.items()}
