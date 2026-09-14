"""CONTEXTUAL PLAYSTYLE INTELLIGENCE (§12, §13).

PlayStyle present != fixed bonus. The value of a PlayStyle depends on the
tactical context and the position:

    context_value(ps, profile, position) ∈ [0.35 .. 1.0]
      1.00 — the profile explicitly values this PlayStyle
             (scoring_config.TACTICAL_PROFILE_PLAYSTYLES)
      0.75 — the position generally benefits from it
             (POSITION_PLAYSTYLE_AFFINITY, engine convention)
      0.35 — neutral: not wrong to have it, but it does not serve THIS setup

PlayStyle+ rules (§13):
  * a + tier of a DESIRED PlayStyle counts at full context value with the
    legacy 1.5 demand weight; holding it only at base tier counts 0.6×;
  * + is never an automatic win: an irrelevant + (low context value) adds
    almost nothing;
  * redundancy: the same PlayStyle at base AND + tier is counted once
    (×PLAYSTYLE_REDUNDANCY_FACTOR on the duplicate) — data-wise this should
    not occur, but honesty beats silent double counting;
  * PlayStyle data unpublished => INSUFFICIENT_EVIDENCE (never "has none").
"""
from __future__ import annotations

from typing import Optional

from backend.domain.card_model import Candidate
from backend.domain.user_model import UserRequirements
from backend.services.engine_config import (
    PLAYSTYLE_PLUS_CONTEXT_FLOOR, PLAYSTYLE_REDUNDANCY_FACTOR,
)
from backend.services.fit_value import FitValue
from backend.services.scoring_config import TACTICAL_PROFILE_PLAYSTYLES

# Positional affinity (engine convention; names validated against the ingested
# 36-name vocabulary by tests). Deliberately conservative.
POSITION_PLAYSTYLE_AFFINITY: dict[str, tuple[str, ...]] = {
    "GK": ("Cross Claimer", "Rush Out", "Far Reach", "Long Throw", "Far Throw", "Footwork"),
    "CB": ("Aerial Fortress", "Block", "Bruiser", "Enforcer", "Intercept", "Jockey",
           "Anticipate", "Slide Tackle", "Precision Header"),
    "LB": ("Jockey", "Whipped Pass", "Quick Step", "Rapid", "Relentless", "Intercept",
           "Slide Tackle", "Anticipate"),
    "RB": ("Jockey", "Whipped Pass", "Quick Step", "Rapid", "Relentless", "Intercept",
           "Slide Tackle", "Anticipate"),
    "CDM": ("Anticipate", "Intercept", "Jockey", "Enforcer", "Bruiser", "Block",
            "Tiki Taka", "Pinged Pass", "Slide Tackle"),
    "CM": ("Tiki Taka", "First Touch", "Pinged Pass", "Incisive Pass", "Long Ball Pass",
           "Relentless", "Technical", "Inventive", "Press Proven"),
    "CAM": ("Tiki Taka", "First Touch", "Technical", "Inventive", "Incisive Pass",
            "Finesse Shot", "Trickster", "Dead Ball", "Chip Shot", "Gamechanger"),
    "LM": ("Whipped Pass", "Quick Step", "Rapid", "Trickster", "First Touch",
           "Relentless", "Low Driven Shot"),
    "RM": ("Whipped Pass", "Quick Step", "Rapid", "Trickster", "First Touch",
           "Relentless", "Low Driven Shot"),
    "LW": ("Trickster", "Quick Step", "Rapid", "Technical", "Finesse Shot", "Power Shot",
           "First Touch", "Footwork", "Acrobatic", "Chip Shot"),
    "RW": ("Trickster", "Quick Step", "Rapid", "Technical", "Finesse Shot", "Power Shot",
           "First Touch", "Footwork", "Acrobatic", "Chip Shot"),
    "ST": ("Finesse Shot", "Power Shot", "Acrobatic", "Precision Header", "Deflector",
           "Quick Step", "Rapid", "Chip Shot", "Low Driven Shot", "Press Proven"),
}

PROFILE_VALUE = 1.0
POSITION_VALUE = 0.75
NEUTRAL_VALUE = 0.35
PLUS_DEMAND_WEIGHT = 1.5       # legacy semantics preserved
BASE_TIER_ONLY_FACTOR = 0.6    # desired + but only base tier held


def context_value(playstyle: str, profile: Optional[str], position: str) -> tuple[float, str]:
    """How valuable is this PlayStyle in THIS tactical/positional context."""
    if profile:
        valued = TACTICAL_PROFILE_PLAYSTYLES.get(profile.upper(), [])
        if playstyle in valued:
            return PROFILE_VALUE, f"explicitly valued by {profile.upper()} tactics"
    aff = POSITION_PLAYSTYLE_AFFINITY.get(position.upper(), ())
    if playstyle in aff:
        return POSITION_VALUE, f"generally useful at {position.upper()}"
    return NEUTRAL_VALUE, "context-neutral (not wrong, just not what this setup demands)"


def contextual_playstyle_fit(candidate: Candidate, req: UserRequirements) -> FitValue:
    """Contextual replacement for legacy playstyle_fit — used ONLY when
    req.enable_playstyle_context is set. Legacy behavior stays default."""
    if not candidate.playstyle_data_published:
        return FitValue.insufficient(
            "PlayStyles are not published for this candidate by the source; "
            "cannot verify contextual fit (absence of data is not absence of PlayStyles)")

    have_base = {p.strip() for p in candidate.playstyles_base if p and p.strip()}
    have_plus = {p.strip() for p in candidate.playstyles_plus if p and p.strip()}
    have_all = have_base | have_plus
    position = (req.position or candidate.position_primary or "").strip().upper()
    profile = req.tactical_profile if req.tactical_profile not in (None, "CUSTOM") else None

    desired_base = [p.strip() for p in req.desired_playstyles if p and p.strip()]
    desired_plus = [p.strip() for p in req.desired_playstyles_plus if p and p.strip()]

    ev: list[str] = []
    total_w = 0.0
    acc = 0.0

    if desired_base or desired_plus:
        for ps in desired_base:
            ctx, why = context_value(ps, profile, position)
            total_w += 1.0
            if ps in have_all:
                acc += ctx
                ev.append(f"{ps}: held — context value {ctx:.2f} ({why})")
            else:
                ev.append(f"{ps}: not held — context value {ctx:.2f} forgone")
        for ps in desired_plus:
            ctx, why = context_value(ps, profile, position)
            total_w += PLUS_DEMAND_WEIGHT
            if ps in have_plus:
                acc += PLUS_DEMAND_WEIGHT * ctx
                ev.append(f"{ps}+: held at + tier — context value {ctx:.2f} ({why})")
            elif ps in have_base:
                acc += PLUS_DEMAND_WEIGHT * ctx * BASE_TIER_ONLY_FACTOR
                ev.append(f"{ps}: base tier only (+ requested) — {BASE_TIER_ONLY_FACTOR}× of context value")
            else:
                ev.append(f"{ps}+: not held — context value forgone")
        if total_w <= 0:
            return FitValue.unknown("no PlayStyle requirements specified")
        return FitValue.known(acc / total_w, evidence=tuple(ev))

    # No explicit desires: score the candidate's kit against the tactical
    # context (only meaningful when the profile values PlayStyles at all).
    if not profile or not TACTICAL_PROFILE_PLAYSTYLES.get(profile.upper()):
        return FitValue.unknown(
            "no PlayStyle requirements and no profile-valued PlayStyles to score against")
    valued = TACTICAL_PROFILE_PLAYSTYLES[profile.upper()]
    hits = [p for p in valued if p in have_all]
    plus_hits = [p for p in hits if p in have_plus]
    # redundancy: same PS at base+plus counted once (×factor on the duplicate)
    redundant = sorted(have_base & have_plus)
    score = len(hits) / len(valued)
    if plus_hits:
        # transparent bounded bonus: a + tier on a context-valued PlayStyle adds
        # half-credit for that hit — + is never an automatic win (§13)
        score = min(1.0, score + 0.5 * len(plus_hits) / len(valued))
    ev.append(f"{profile.upper()} values {len(valued)} PlayStyles; candidate holds {len(hits)}: "
              + (", ".join(hits) if hits else "none"))
    if plus_hits:
        ev.append(f"+ tier on context-valued: {', '.join(plus_hits)} (bounded boost — + is never an automatic win)")
    if redundant:
        ev.append(f"redundant base+plus pairs counted once ×{PLAYSTYLE_REDUNDANCY_FACTOR}: "
                  + ", ".join(redundant))
    return FitValue.known(score, evidence=tuple(ev))
