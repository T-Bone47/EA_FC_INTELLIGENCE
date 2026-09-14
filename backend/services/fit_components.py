"""Fit components for Recommendation Engine V2.

Each component returns a FitValue (KNOWN / UNKNOWN / INSUFFICIENT_EVIDENCE).
Absolute rules enforced here:
  * missing data is never converted into 0 / penalty;
  * partial evidence below the coverage threshold degrades to
    INSUFFICIENT_EVIDENCE instead of producing a shaky score;
  * every KNOWN value carries deterministic evidence strings so explanations
    can be generated without an LLM.
"""
from __future__ import annotations

from typing import Optional

from backend.domain.card_model import Candidate
from backend.domain.user_model import SquadContext, UserRequirements
from backend.services.fit_value import FitValue
from backend.services.scoring_config import (
    ATTRIBUTE_EVIDENCE_MIN_COVERAGE,
    OVR_QUALITY_CEIL,
    OVR_QUALITY_FLOOR,
    POSITION_ADJACENCY,
    POSITION_FIT_EXACT,
    POSITION_FIT_FALLBACK,
    POSITION_FIT_SECONDARY,
    ScoringConfig,
)


# ------------------------------------------------------------------ overall_quality
def overall_quality(candidate: Candidate) -> FitValue:
    ovr = candidate.overall_rating
    if ovr is None:
        return FitValue.unknown("overall rating not published for this candidate")
    span = OVR_QUALITY_CEIL - OVR_QUALITY_FLOOR
    q = (ovr - OVR_QUALITY_FLOOR) / span
    return FitValue.known(
        q,
        evidence=(f"OVR {ovr} normalized on [{OVR_QUALITY_FLOOR},{OVR_QUALITY_CEIL}] "
                  f"(absolute deterministic curve)",),
    )


# ------------------------------------------------------------------ position_fit
def position_fit(candidate: Candidate, req: UserRequirements,
                 config: ScoringConfig) -> FitValue:
    if not req.position:
        return FitValue.unknown("no target position specified in requirements")
    target = req.position.strip().upper()
    primary = (candidate.position_primary or "").strip().upper()
    if not primary:
        return FitValue.unknown("candidate position not published")

    if primary == target:
        return FitValue.known(POSITION_FIT_EXACT,
                              evidence=(f"primary position {primary} matches target",))
    secondaries = {s.strip().upper() for s in candidate.secondary_positions if s and s.strip()}
    if target in secondaries:
        return FitValue.known(
            POSITION_FIT_SECONDARY,
            evidence=(f"target {target} is a listed alternate position "
                      f"(primary {primary})",))
    adj = POSITION_ADJACENCY.get(target, {}).get(primary)
    adj_rev = POSITION_ADJACENCY.get(primary, {}).get(target)
    best = max(v for v in (adj, adj_rev) if v is not None) if (adj or adj_rev) else None
    if best is not None:
        return FitValue.known(
            best,
            evidence=(f"position adjacency {primary}->{target} rated {best:.2f} "
                      f"(deterministic adjacency table)",))
    return FitValue.known(
        POSITION_FIT_FALLBACK,
        evidence=(f"position {primary} has no meaningful affinity with target "
                  f"{target}",))


# ------------------------------------------------------------------ attribute_fit
def _attr_requirements(req: UserRequirements, candidate: Candidate,
                       config: ScoringConfig) -> tuple[dict[str, float], dict[str, dict]]:
    """Returns (normalized weights, per-attribute constraint spec)."""
    weights: dict[str, float] = {}
    specs: dict[str, dict] = {}
    if req.attribute_preferences:
        for p in req.attribute_preferences:
            weights[p.attribute] = weights.get(p.attribute, 0.0) + max(p.weight, 0.0)
            spec = specs.setdefault(p.attribute, {"min": None, "target": None})
            if p.min_value is not None:
                spec["min"] = p.min_value if spec["min"] is None else max(spec["min"], p.min_value)
            if p.target_value is not None:
                spec["target"] = p.target_value
    else:
        pos = (req.position or candidate.position_primary or "").strip().upper()
        weights = config.position_attribute_weights(pos)
    total = sum(weights.values())
    if total <= 0:
        return {}, specs
    return {k: v / total for k, v in weights.items()}, specs


def _attribute_score(value: int, spec: dict) -> float:
    if spec.get("min") is not None and spec.get("target") is None:
        mn = spec["min"]
        if value >= mn:
            return 1.0
        # deterministic ramp: 25 points below min -> 0
        return max(0.0, 1.0 - (mn - value) / 25.0)
    if spec.get("target") is not None:
        return max(0.0, 1.0 - abs(value - spec["target"]) / 99.0)
    # no explicit constraint: higher is better for position-relevant attributes
    return value / 99.0


def attribute_fit(candidate: Candidate, req: UserRequirements,
                  config: ScoringConfig) -> FitValue:
    weights, specs = _attr_requirements(req, candidate, config)
    if not weights:
        return FitValue.unknown(
            "no attribute preferences given and no position profile available "
            f"for position {req.position or candidate.position_primary!r}")

    scored_w = 0.0
    acc = 0.0
    missing: list[str] = []
    detail: list[str] = []
    for attr, w in weights.items():
        v = candidate.attributes.get(attr)
        if v is None:
            missing.append(attr)
            continue
        s = _attribute_score(v, specs.get(attr, {}))
        acc += w * s
        scored_w += w
        detail.append(f"{attr}={v}")

    if scored_w <= 0:
        return FitValue.insufficient(
            f"none of the {len(weights)} required attributes are published "
            f"for this candidate (e.g. {', '.join(sorted(weights)[:4])}...)")
    coverage = scored_w
    if coverage < ATTRIBUTE_EVIDENCE_MIN_COVERAGE:
        return FitValue.insufficient(
            f"only {coverage:.0%} of required attribute weight is published "
            f"(missing: {', '.join(sorted(missing)[:6])})",
            evidence=tuple(detail[:8]))
    ev = [f"coverage {coverage:.0%} of required attribute weight"]
    ev += detail[:10]
    if missing:
        ev.append(f"missing (excluded, not zeroed): {', '.join(sorted(missing)[:6])}")
    return FitValue.known(acc / scored_w, evidence=tuple(ev))


# ------------------------------------------------------------------ tactical_fit
def tactical_fit(candidate: Candidate, req: UserRequirements,
                 config: ScoringConfig) -> FitValue:
    weights = config.tactical_attribute_weights(req.tactical_profile, req.custom_tactics)
    if not weights:
        if req.tactical_profile == "CUSTOM":
            return FitValue.unknown("CUSTOM tactical profile given without attribute weights")
        return FitValue.unknown(
            f"tactical profile {req.tactical_profile} imposes no specific attribute demand")

    scored_w = 0.0
    acc = 0.0
    missing: list[str] = []
    detail: list[str] = []
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
            f"no attributes required by {req.tactical_profile} are published "
            "for this candidate")
    if scored_w < ATTRIBUTE_EVIDENCE_MIN_COVERAGE:
        return FitValue.insufficient(
            f"only {scored_w:.0%} of {req.tactical_profile} attribute weight is "
            f"published (missing: {', '.join(sorted(missing)[:6])})",
            evidence=tuple(detail[:8]))
    ev = [f"profile {req.tactical_profile}", f"coverage {scored_w:.0%}"] + detail[:8]
    return FitValue.known(acc / scored_w, evidence=tuple(ev))


# ------------------------------------------------------------------ playstyle_fit
def playstyle_fit(candidate: Candidate, req: UserRequirements,
                  config: ScoringConfig) -> FitValue:
    desired_base = [p.strip() for p in req.desired_playstyles if p and p.strip()]
    desired_plus = [p.strip() for p in req.desired_playstyles_plus if p and p.strip()]
    if not desired_base and not desired_plus:
        return FitValue.unknown("no PlayStyle requirements specified")

    if not candidate.playstyle_data_published:
        # §19: missing PlayStyle data != "has no PlayStyles"
        return FitValue.insufficient(
            "PlayStyles are not published for this candidate by the source; "
            "cannot verify fit (absence of data is not absence of PlayStyles)")

    have_base = {p.strip() for p in candidate.playstyles_base if p and p.strip()}
    have_plus = {p.strip() for p in candidate.playstyles_plus if p and p.strip()}
    have_all = have_base | have_plus

    total_w = 0.0
    acc = 0.0
    matched: list[str] = []
    missed: list[str] = []
    for p in desired_base:
        total_w += 1.0
        if p in have_all:
            acc += 1.0
            matched.append(p)
        else:
            missed.append(p)
    for p in desired_plus:
        total_w += 1.5     # PlayStyle+ demands weigh more than base desires
        if p in have_plus:
            acc += 1.5
            matched.append(f"{p}+")
        elif p in have_all:
            acc += 0.75    # has it, but only at base tier
            matched.append(f"{p} (base tier only, + requested)")
        else:
            missed.append(f"{p}+")

    ev = []
    if matched:
        ev.append("matched: " + ", ".join(matched))
    if missed:
        ev.append("missing: " + ", ".join(missed))
    return FitValue.known(acc / total_w, evidence=tuple(ev))


# ------------------------------------------------------------------ role_fit (advisory)
def role_fit(candidate: Candidate, req: UserRequirements,
             role_service) -> FitValue:
    if not req.role:
        return FitValue.unknown("no Role requirement specified")
    return role_service.evaluate(candidate, req)


# ------------------------------------------------------------------ team_fit
def team_fit(candidate: Candidate, req: UserRequirements,
             squad_ctx: Optional[SquadContext], config: ScoringConfig) -> FitValue:
    if squad_ctx is None or not squad_ctx.filled_slots():
        return FitValue.unknown("no squad context provided; chemistry not evaluated")

    vc = config.version(candidate.game_version.value)
    # verified link facts (club/league/nation overlap) — always computable
    links = {"club": 0, "league": 0, "nation": 0}
    for slot in squad_ctx.filled_slots():
        if candidate.club and slot.club and slot.club == candidate.club:
            links["club"] += 1
        if candidate.league and slot.league and slot.league == slot.league:
            links["league"] += 1
        if candidate.nation and slot.nation and slot.nation == candidate.nation:
            links["nation"] += 1
    link_ev = (f"shared club links: {links['club']}, league: {links['league']}, "
               f"nation: {links['nation']} (verified identity facts)")

    if not vc.chemistry_rules_verified:
        # §22: never fake chemistry. Rules unverified => INSUFFICIENT_EVIDENCE,
        # but the verified link facts are still surfaced as evidence.
        return FitValue.insufficient(
            f"{candidate.game_version.value} chemistry rules are not verified in "
            "this system; chemistry score withheld rather than fabricated",
            evidence=(link_ev,))

    # Reserved: verified-rules chemistry computation would go here.
    return FitValue.insufficient(
        "chemistry engine for verified rules not yet implemented",
        evidence=(link_ev,))
