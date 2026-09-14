"""ARCHETYPES + GAMEPLAY PROFILE + VERSATILITY (§15, §16, §17).

Everything here is ENGINE-DERIVED from structured data:
  * archetypes are COMPUTED from attributes/PlayStyles per candidate —
    no player is ever manually labeled ("Player X IS a box-to-box" is banned);
  * gameplay-profile labels are derived analytics, clearly marked
    ENGINE_DERIVED, never presented as official EA attributes;
  * versatility credits only meaningful alternates (adjacency >= threshold)
    and is contextual when a formation is known.

Honesty rules:
  * an archetype whose required attributes are largely UNKNOWN yields
    INSUFFICIENT_EVIDENCE — not a low score;
  * PlayStyle facts are only used when `playstyle_data_published`;
  * GK archetypes rely only on `gk_*` attributes (outfield details for GK are
    facade mirrors in the source — not real ability — and stay unused).
"""
from __future__ import annotations

from typing import Optional

from backend.domain.card_model import Candidate
from backend.services.engine_config import (
    GAMEPLAY_PROFILE_STRONG, GAMEPLAY_PROFILE_WEAK, VERSATILITY_MAX_CREDIT,
    VERSATILITY_MIN_ADJACENCY,
)
from backend.services.fit_value import FitValue
from backend.services.scoring_config import POSITION_ADJACENCY, ScoringConfig

# Weight of the archetype_fit component when an archetype is explicitly
# requested; the base weights are renormalized to (1 - ARCHETYPE_WEIGHT).
ARCHETYPE_WEIGHT = 0.10
# candidate outside the archetype's natural positions keeps fit but scaled:
ARCHETYPE_POSITION_MISMATCH_FACTOR = 0.75
# share of archetype score coming from PlayStyle affinity (only when published)
ARCHETYPE_PLAYSTYLE_SHARE = 0.20
# below this share of archetype-attribute weight, INSUFFICIENT_EVIDENCE
ARCHETYPE_MIN_COVERAGE = 0.5

# ---------------------------------------------------------------------------
# Archetype definitions — TUNABLE CONFIG (§46). Attribute weights are relative
# (normalized at use). PlayStyle affinities use ONLY names from the ingested
# 36-name FC26 vocabulary (validated by tests). Definitions express football
# convention; they are documented engine knowledge, not EA-published facts.
# ---------------------------------------------------------------------------
ARCHETYPE_DEFINITIONS: dict[str, dict] = {
    "BOX_TO_BOX": {
        "positions": ("CM",),
        "attributes": {"stamina": 20, "short_passing": 13, "defensive_awareness": 12,
                       "interceptions": 10, "long_passing": 9, "ball_control": 9,
                       "strength": 8, "positioning": 7, "long_shots": 6, "aggression": 6},
        "playstyles": ("Relentless", "Press Proven", "Tiki Taka", "Incisive Pass", "Long Ball Pass"),
        "description": "covers both boxes: engine, passing range and defensive contribution",
    },
    "DEEP_PLAYMAKER": {
        "positions": ("CDM", "CM"),
        "attributes": {"long_passing": 20, "vision": 18, "short_passing": 16,
                       "composure": 12, "positioning": 10, "ball_control": 8,
                       "defensive_awareness": 6},
        "playstyles": ("Pinged Pass", "Incisive Pass", "Long Ball Pass", "Tiki Taka", "Inventive"),
        "description": "dictates tempo from deep with range and composure",
    },
    "BALL_WINNER": {
        "positions": ("CDM", "CM", "CB"),
        "attributes": {"interceptions": 18, "standing_tackle": 16, "defensive_awareness": 16,
                       "aggression": 14, "strength": 12, "reactions": 8, "stamina": 8,
                       "positioning": 8},
        "playstyles": ("Anticipate", "Intercept", "Jockey", "Enforcer", "Slide Tackle", "Bruiser"),
        "description": "wins the ball back: reading of the game plus duel reliability",
    },
    "CREATIVE_PLAYMAKER": {
        "positions": ("CAM", "CM", "LW", "RW"),
        "attributes": {"vision": 20, "short_passing": 18, "dribbling_detail": 12,
                       "curve": 10, "composure": 10, "ball_control": 10, "long_passing": 6,
                       "long_shots": 6, "agility": 4},
        "playstyles": ("Tiki Taka", "First Touch", "Inventive", "Technical", "Incisive Pass", "Dead Ball"),
        "description": "creates chances in the final third",
    },
    "INVERTED_WINGER": {
        "positions": ("LW", "RW", "ST", "CAM"),
        "attributes": {"dribbling_detail": 18, "finishing": 16, "ball_control": 12,
                       "agility": 12, "curve": 10, "acceleration": 10, "composure": 8,
                       "long_shots": 6},
        "playstyles": ("Finesse Shot", "Technical", "Trickster", "Footwork", "Chip Shot"),
        "description": "cuts inside from the wing to shoot/create",
    },
    "DIRECT_WINGER": {
        "positions": ("LW", "RW", "LM", "RM"),
        "attributes": {"pace": 20, "acceleration": 16, "crossing": 16, "stamina": 12,
                       "dribbling_detail": 10, "sprint_speed": 10, "curve": 6,
                       "short_passing": 5, "agility": 5},
        "playstyles": ("Quick Step", "Rapid", "Whipped Pass", "Relentless"),
        "description": "beats his man wide and delivers",
    },
    "INSIDE_FORWARD": {
        "positions": ("LW", "RW", "ST"),
        "attributes": {"finishing": 18, "dribbling_detail": 14, "acceleration": 14,
                       "composure": 12, "positioning": 12, "ball_control": 10,
                       "agility": 8, "shot_power": 6},
        "playstyles": ("Finesse Shot", "Power Shot", "Technical", "Quick Step", "Deflector"),
        "description": "attacks the box from wide; goal threat first",
    },
    "TARGET_MAN": {
        "positions": ("ST",),
        "attributes": {"strength": 20, "heading_accuracy": 18, "shot_power": 12,
                       "positioning": 12, "volleys": 10, "jumping": 10, "finishing": 8,
                       "balance": 4},
        "playstyles": ("Aerial Fortress", "Precision Header", "Power Shot", "Bruiser", "Acrobatic"),
        "description": "holds play up and dominates aerially",
    },
    "PRESSING_FORWARD": {
        "positions": ("ST", "LW", "RW", "CAM"),
        "attributes": {"aggression": 18, "stamina": 18, "acceleration": 14,
                       "positioning": 12, "reactions": 10, "interceptions": 8,
                       "finishing": 8, "strength": 6},
        "playstyles": ("Press Proven", "Relentless", "Anticipate", "Quick Step"),
        "description": "leads the press from the front",
    },
    "POACHER": {
        "positions": ("ST",),
        "attributes": {"positioning": 22, "finishing": 20, "reactions": 14,
                       "acceleration": 12, "composure": 10, "volleys": 6, "heading_accuracy": 4},
        "playstyles": ("Finesse Shot", "Quick Step", "Rapid", "Deflector", "Chip Shot", "Acrobatic"),
        "description": "lives off half-chances in the box",
    },
    "FALSE_9": {
        "positions": ("ST", "CAM"),
        "attributes": {"vision": 16, "short_passing": 16, "dribbling_detail": 14,
                       "composure": 12, "ball_control": 12, "long_shots": 10,
                       "finishing": 8, "positioning": 6, "long_passing": 6},
        "playstyles": ("Tiki Taka", "First Touch", "Inventive", "Technical", "Finesse Shot"),
        "description": "drops deep to link play, vacating the box",
    },
    "ATTACKING_FULLBACK": {
        "positions": ("LB", "RB", "LM", "RM"),
        "attributes": {"pace": 18, "stamina": 18, "crossing": 16, "acceleration": 12,
                       "short_passing": 8, "long_passing": 8, "dribbling_detail": 6,
                       "defending": 6, "curve": 5},
        "playstyles": ("Whipped Pass", "Quick Step", "Rapid", "Relentless", "Long Throw"),
        "description": "provides width and overlaps",
    },
    "DEFENSIVE_FULLBACK": {
        "positions": ("LB", "RB", "CB"),
        "attributes": {"defending": 20, "standing_tackle": 16, "interceptions": 14,
                       "defensive_awareness": 14, "strength": 10, "positioning": 8,
                       "pace": 6, "stamina": 6},
        "playstyles": ("Jockey", "Anticipate", "Enforcer", "Block", "Slide Tackle", "Intercept"),
        "description": "defends his flank first",
    },
    "STOPPER": {
        "positions": ("CB",),
        "attributes": {"standing_tackle": 18, "strength": 16, "aggression": 14,
                       "heading_accuracy": 14, "defensive_awareness": 12, "jumping": 10,
                       "interceptions": 8, "positioning": 6},
        "playstyles": ("Enforcer", "Jockey", "Aerial Fortress", "Block", "Bruiser", "Slide Tackle"),
        "description": "wins the defensive duel outright",
    },
    "BALL_PLAYING_DEFENDER": {
        "positions": ("CB", "CDM"),
        "attributes": {"short_passing": 18, "long_passing": 16, "vision": 12,
                       "composure": 12, "defending": 12, "ball_control": 10,
                       "defensive_awareness": 8, "reactions": 6},
        "playstyles": ("Pinged Pass", "Tiki Taka", "First Touch", "Long Ball Pass", "Technical"),
        "description": "starts attacks from the back",
    },
    "SWEEPER_KEEPER": {
        "positions": ("GK",),
        # outfield details for GK are facade mirrors in the FC26 source and are
        # deliberately NOT used — honest limits of the data (§29 data reqs).
        "attributes": {"gk_positioning": 30, "gk_reflexes": 25, "gk_kicking": 25,
                       "gk_handling": 10, "gk_diving": 10},
        "playstyles": ("Rush Out", "Far Reach", "Cross Claimer", "Footwork"),
        "description": "sweeps behind a high line; distribution-oriented (limited to published GK attrs)",
    },
    "SHOT_STOPPER": {
        "positions": ("GK",),
        "attributes": {"gk_reflexes": 30, "gk_diving": 30, "gk_handling": 20,
                       "gk_positioning": 20},
        "playstyles": ("Acrobatic", "Cross Claimer", "Block", "Far Reach"),
        "description": "pure line-stopping",
    },
}


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()} if total > 0 else {}


def archetype_positions(archetype: str) -> tuple[str, ...]:
    return tuple(ARCHETYPE_DEFINITIONS[archetype.upper()]["positions"])


def archetype_score(candidate: Candidate, archetype: str) -> FitValue:
    """Compute (never look up) how strongly this candidate matches an archetype.

    §29: pure per (candidate, archetype) — memoized on the candidate's feature
    cache so repeated requests over a warm pool never recompute it.
    """
    key = archetype.strip().upper()
    cache = getattr(candidate, "feature_cache", None)
    ck = ("archetype_score", key)
    if cache is not None and ck in cache:
        return cache[ck]
    fv = _archetype_score(candidate, key)
    if cache is not None:
        cache[ck] = fv
    return fv


def _archetype_score(candidate: Candidate, key: str) -> FitValue:
    """Compute (never look up) how strongly this candidate matches an archetype."""
    defn = ARCHETYPE_DEFINITIONS.get(key)
    if defn is None:
        return FitValue.unknown(f"unknown archetype {key!r} — no definition, no guessing")

    weights = _normalize(defn["attributes"])
    acc = 0.0
    scored_w = 0.0
    detail: list[str] = []
    missing: list[str] = []
    for attr, w in weights.items():
        v = candidate.attributes.get(attr)
        if v is None:
            missing.append(attr)
            continue
        acc += w * (v / 99.0)
        scored_w += w
        detail.append(f"{attr}={v}")
    if scored_w <= 0:
        return FitValue.insufficient(
            f"none of the {len(weights)} archetype attributes for {key} are "
            "published for this candidate")
    if scored_w < ARCHETYPE_MIN_COVERAGE:
        return FitValue.insufficient(
            f"only {scored_w:.0%} of {key} archetype attribute weight is published "
            f"(missing: {', '.join(sorted(missing)[:5])})",
            evidence=tuple(detail[:6]))
    attr_part = acc / scored_w

    # PlayStyle affinity: only when published; absence of data is not absence
    ps_part = None
    ps_ev: list[str] = []
    if candidate.playstyle_data_published:
        have = set(candidate.playstyles_base) | set(candidate.playstyles_plus)
        aff = defn["playstyles"]
        hits = [p for p in aff if p in have]
        plus_hits = [p for p in hits if p in set(candidate.playstyles_plus)]
        ps_part = len(hits) / len(aff) if aff else None
        if ps_part is not None:
            ps_ev.append(f"PlayStyle affinity {len(hits)}/{len(aff)}"
                         + (f" (+ tier: {', '.join(plus_hits)})" if plus_hits else ""))

    if ps_part is None:
        score = attr_part
        ev = [f"{key} attributes {attr_part:.2f} (PlayStyles unpublished — excluded, not zeroed)"]
    else:
        score = (1 - ARCHETYPE_PLAYSTYLE_SHARE) * attr_part + ARCHETYPE_PLAYSTYLE_SHARE * ps_part
        ev = [f"{key} attributes {attr_part:.2f}"] + ps_ev

    # position naturalness (evidence + soft scaling)
    positions = {s.upper() for s in (candidate.position_primary, *candidate.secondary_positions)}
    if positions & {p.upper() for p in defn["positions"]}:
        ev.append(f"natural {key} positions: {', '.join(defn['positions'])}")
    else:
        score *= ARCHETYPE_POSITION_MISMATCH_FACTOR
        ev.append(f"outside natural {key} positions ({', '.join(defn['positions'])}) — "
                  f"scaled ×{ARCHETYPE_POSITION_MISMATCH_FACTOR}")
    ev += detail[:6]
    return FitValue.known(score, evidence=tuple(ev))


def dominant_archetype(candidate: Candidate) -> Optional[tuple[str, float]]:
    """Highest-scoring archetype among those the candidate is position-eligible
    for, with sufficient evidence. Deterministic tie-break: name."""
    cache = getattr(candidate, "feature_cache", None)
    if cache is not None and "dominant_archetype" in cache:
        return cache["dominant_archetype"]
    out = _dominant_archetype(candidate)
    if cache is not None:
        cache["dominant_archetype"] = out
    return out


def _dominant_archetype(candidate: Candidate) -> Optional[tuple[str, float]]:
    best: Optional[tuple[str, float]] = None
    positions = {s.upper() for s in (candidate.position_primary, *candidate.secondary_positions)}
    for name in sorted(ARCHETYPE_DEFINITIONS):
        defn = ARCHETYPE_DEFINITIONS[name]
        if not (positions & {p.upper() for p in defn["positions"]}):
            continue
        fv = archetype_score(candidate, name)
        if fv.is_known and (best is None or fv.value > best[1]):
            best = (name, fv.value)
    return best


# ---------------------------------------------------------------------------
# §16 — gameplay profile (ENGINE-DERIVED labels; never official EA attributes)
# ---------------------------------------------------------------------------
_GAMEPLAY_LABELS: dict[str, tuple[tuple[str, ...], str]] = {
    # label -> (required KNOWN attributes, aggregation)
    "EXPLOSIVE": (("acceleration", "pace"), "all"),
    "TECHNICAL": (("ball_control", "dribbling_detail", "agility"), "avg"),
    "PHYSICAL": (("strength", "stamina", "aggression"), "avg"),
    "CREATIVE": (("vision", "short_passing", "long_passing", "curve"), "avg"),
    "DEFENSIVE": (("defensive_awareness", "interceptions", "standing_tackle"), "avg"),
    "PRESS_RESISTANT": (("composure", "ball_control", "short_passing"), "avg"),
    "DIRECT": (("long_passing", "heading_accuracy", "shot_power"), "avg"),
    "CLINICAL": (("finishing", "composure", "positioning"), "avg"),
}
_GK_LABELS: dict[str, tuple[str, ...]] = {
    "REFLEX_LINE_KEEPER": ("gk_reflexes", "gk_diving"),
    "POSITIONAL_KEEPER": ("gk_positioning", "gk_handling"),
    "DISTRIBUTING_KEEPER": ("gk_kicking",),
}


def gameplay_profile(candidate: Candidate) -> dict:
    """Derived analytical labels with evidence. Only emitted when ALL required
    attributes are KNOWN — UNKNOWN never produces a label (and never blocks one
    it cannot disprove either; absent = not derived, listed in skipped).

    §29: pure per candidate — memoized; callers receive a fresh shallow copy
    so cached state can never be mutated.
    """
    cache = getattr(candidate, "feature_cache", None)
    if cache is not None and "gameplay_profile" in cache:
        return dict(cache["gameplay_profile"])
    out = _gameplay_profile(candidate)
    if cache is not None:
        cache["gameplay_profile"] = out
    return dict(out)


def _gameplay_profile(candidate: Candidate) -> dict:
    scored: list[tuple[float, dict]] = []
    skipped: list[str] = []
    is_gk = (candidate.position_primary or "").upper() == "GK"
    table = _GK_LABELS if is_gk else _GAMEPLAY_LABELS
    for label, spec in table.items():
        attrs, mode = spec if not is_gk else (spec, "all")
        vals = [candidate.attributes.get(a) for a in attrs]
        if any(v is None for v in vals):
            skipped.append(label)
            continue
        agg = min(vals) if mode == "all" else sum(vals) / len(vals)
        threshold = GAMEPLAY_PROFILE_STRONG
        if agg >= threshold:
            scored.append((agg, {"label": label, "engine_derived": True,
                                 "evidence": f"{', '.join(f'{a}={v}' for a, v in zip(attrs, vals))}"
                                             f" ({mode} {agg:.0f} >= {threshold})"}))
    # cap at the 4 strongest labels — world-class players would otherwise carry
    # every label and say nothing (deterministic: by aggregate, then name)
    scored.sort(key=lambda t: (-t[0], t[1]["label"]))
    labels = [d for _, d in scored[:4]]
    return {"labels": labels,
            "additional_qualified": [d["label"] for _, d in scored[4:]],
            "skipped_unknown": skipped,
            "note": "ENGINE-DERIVED analytics — not official EA attributes"}


# ---------------------------------------------------------------------------
# §17 — versatility (contextual; no credit for useless alternates)
# ---------------------------------------------------------------------------
def versatility(candidate: Candidate, formation_slots: Optional[list] = None) -> FitValue:
    """Σ adjacency(primary→alternate) over meaningful alternates, capped.
    When formation slots are known, alternates that cover another slot in the
    formation count fully; others count half (contextual versatility).
    §29: memoized per (candidate, slot-signature)."""
    cache = getattr(candidate, "feature_cache", None)
    sig = tuple(sorted(s.position.upper() for s in formation_slots)) if formation_slots else None
    ck = ("versatility", sig)
    if cache is not None and ck in cache:
        return cache[ck]
    fv = _versatility(candidate, formation_slots)
    if cache is not None:
        cache[ck] = fv
    return fv


def _versatility(candidate: Candidate, formation_slots: Optional[list] = None) -> FitValue:
    primary = (candidate.position_primary or "").upper()
    if not primary or primary not in POSITION_ADJACENCY:
        return FitValue.unknown("no primary position — versatility not derived")
    adj = POSITION_ADJACENCY.get(primary, {})
    slot_positions = None
    if formation_slots:
        slot_positions = {s.position.upper() for s in formation_slots}

    credits: list[str] = []
    total = 0.0
    alts = []
    for alt in dict.fromkeys(s.strip().upper() for s in candidate.secondary_positions if s and s.strip()):
        if alt == primary:
            continue
        a = adj.get(alt, 0.0)
        if a < VERSATILITY_MIN_ADJACENCY:
            continue                      # useless alternate — no credit (§17)
        factor = 1.0
        ctx = ""
        if slot_positions is not None:
            if alt in slot_positions:
                ctx = " (covers a formation slot)"
            else:
                factor = 0.5
                ctx = " (outside formation — half credit)"
        alts.append(f"{alt} adjacency {a:.2f}{ctx}")
        total += a * factor
    if not alts:
        return FitValue.known(
            0.0, evidence=("no alternate position clears the "
                           f"{VERSATILITY_MIN_ADJACENCY:.2f} adjacency bar — specialist",))
    score = min(1.0, total / VERSATILITY_MAX_CREDIT)
    credits = alts[:5]
    return FitValue.known(score, evidence=tuple(credits))
