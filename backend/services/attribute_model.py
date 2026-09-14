"""ATTRIBUTE MODEL v2.1 (§8, §9, §10, §11) — the opt-in intelligence path for
attribute_fit.

The legacy path (`fit_components.attribute_fit`) stays bit-identical for
legacy requests. This module is used ONLY when the request carries explicit
intelligence inputs (bands, slot context, tactical combination, interaction or
saturation flags). Rules:

  * §10 saturation: above a per-attribute knee, extra points count at
    SATURATION_EXCESS_FACTOR — 99 pace is not vastly better than 95 when the
    need is already met. Configurable, deterministic, evidence-logged.
  * §11 bands: qualitative language -> soft targets from engine_config
    (QUALITY_BANDS). A band is a SOFT preference; only explicit user numbers
    become hard floors.
  * §9 interactions: controlled, explainable feature combos (min / geometric
    mean over KNOWN attributes only). A feature whose attributes are not all
    published is SKIPPED (honesty over guessing) and reported.
  * §8 importance: position base weights × slot emphasis × tactical-dimension
    shifts (formations.attribute_weights_from_dimensions), renormalized.
"""
from __future__ import annotations

import math
from typing import Optional

from backend.domain.card_model import Candidate
from backend.domain.user_model import UserRequirements
from backend.services import formations
from backend.services.engine_config import (
    BAND_RAMP_POINTS, DEFAULT_SATURATION_KNEE, INTERACTION_FEATURES,
    INTERACTION_TOTAL_CAP, QUALITY_BANDS, SATURATION_EXCESS_FACTOR,
    SATURATION_KNEES,
)
from backend.services.fit_value import FitValue
from backend.services.scoring_config import ATTRIBUTE_EVIDENCE_MIN_COVERAGE, ScoringConfig


# ------------------------------------------------------------------ §10
def saturate(value: int, attr: str, enabled: bool = True) -> float:
    """Normalized attribute score with diminishing returns above the knee."""
    if not enabled:
        return value / 99.0
    knee = SATURATION_KNEES.get(attr, DEFAULT_SATURATION_KNEE)
    if value <= knee:
        return value / 99.0
    return (knee + (value - knee) * SATURATION_EXCESS_FACTOR) / 99.0


# ------------------------------------------------------------------ §11
def band_score(value: int, band: str) -> tuple[float, str]:
    """Soft-target ramp toward the band's configured target. Reaching the
    target saturates (no bonus above) — bands express 'enough', not 'more'."""
    target = QUALITY_BANDS[band]
    if value >= target:
        return 1.0, f">= band target {target} ({band})"
    return max(0.0, 1.0 - (target - value) / BAND_RAMP_POINTS), \
        f"below band target {target} ({band}), ramp {BAND_RAMP_POINTS:.0f} pts"


# ------------------------------------------------------------------ §9
def interaction_values(candidate: Candidate, position: str,
                       profiles: tuple[str, ...]) -> list[dict]:
    """Evaluate every interaction feature relevant to this position/profiles.
    ALL attrs of a feature must be KNOWN, else the feature is skipped and
    listed in `skipped` (missing data never fabricates an interaction).

    §29: pure per (candidate, position, profiles) — memoized on the candidate
    feature cache. Consumers are read-only, so sharing the result is safe."""
    cache = getattr(candidate, "feature_cache", None)
    ck = ("interactions", position, tuple(profiles))
    if cache is not None and ck in cache:
        return cache[ck]
    out = _interaction_values(candidate, position, profiles)
    if cache is not None:
        cache[ck] = out
    return out


def _interaction_values(candidate: Candidate, position: str,
                        profiles: tuple[str, ...]) -> list[dict]:
    active: list[dict] = []
    skipped: list[dict] = []
    for name, feat in sorted(INTERACTION_FEATURES.items()):
        pos_ok = (not feat["positions"]) or position in feat["positions"]
        prof_ok = (not feat["profiles"]) or any(p in feat["profiles"] for p in profiles)
        if not (pos_ok and prof_ok):
            continue
        vals = {}
        for a in feat["attrs"]:
            v = candidate.attributes.get(a)
            if v is None:
                vals = None
                break
            vals[a] = v
        if vals is None:
            skipped.append({"feature": name, "reason": "attributes not all published"})
            continue
        if feat["op"] == "min":
            raw = min(vals.values()) / 99.0
        else:  # geo mean of normalized values (0-safe: any 0 -> 0)
            raw = math.exp(sum(math.log(max(v / 99.0, 1e-9)) for v in vals.values())
                           / len(vals))
        active.append({"feature": name, "value": raw, "weight": feat["weight"],
                       "op": feat["op"], "inputs": vals, "why": feat["why"]})
    return [{"active": active, "skipped": skipped}] if (active or skipped) else []


# ------------------------------------------------------------------ main
def intelligence_attribute_fit(candidate: Candidate, req: UserRequirements,
                               config: ScoringConfig,
                               slot: Optional[formations.FormationSlot] = None,
                               dims: Optional[dict[str, float]] = None) -> FitValue:
    """Attribute fit with the v2.1 intelligence layers. Deterministic; every
    layer leaves evidence strings."""
    # ---- base importance (§8)
    user_prefs = bool(req.attribute_preferences)
    specs: dict[str, dict] = {}
    if user_prefs:
        weights: dict[str, float] = {}
        for p in req.attribute_preferences:
            weights[p.attribute] = weights.get(p.attribute, 0.0) + max(p.weight, 0.0)
            spec = specs.setdefault(p.attribute, {"min": None, "target": None})
            if p.min_value is not None:
                spec["min"] = p.min_value if spec["min"] is None else max(spec["min"], p.min_value)
            if p.target_value is not None:
                spec["target"] = p.target_value
        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()} if total > 0 else {}
    else:
        pos = (req.position or candidate.position_primary or "").strip().upper()
        weights = config.position_attribute_weights(pos)
        if slot is not None:
            weights = formations.slot_adjusted_weights(weights, slot)
        if dims:
            weights = formations.attribute_weights_from_dimensions(weights, dims)

    # bands add soft targets (§11) — never override explicit user prefs' mins
    def _band_pair(b):
        # accept AttributeBand dataclasses (API/domain path) and plain dicts
        if hasattr(b, "attribute"):
            return b.attribute, b.band
        return b["attribute"], b["band"]
    bands = dict(_band_pair(b) for b in (req.attribute_bands or []))
    for attr, band in bands.items():
        if attr not in weights and weights:
            weights[attr] = weights.get(attr, 0.0)
        specs.setdefault(attr, {"min": None, "target": None})
    if bands and not user_prefs and weights:
        # re-normalize after band attributes were ensured presence
        total = sum(weights.values())
        if total > 0:
            base_share = 1.0 / total if not user_prefs else 0.0
            for attr in bands:
                if weights.get(attr, 0) == 0.0:
                    weights[attr] = base_share
            total = sum(weights.values())
            weights = {k: v / total for k, v in weights.items()}

    if not weights:
        return FitValue.unknown(
            "no attribute preferences, bands or position profile available")

    # ---- per-attribute scoring
    enable_sat = bool(req.enable_saturation)
    scored_w = 0.0
    acc = 0.0
    missing: list[str] = []
    detail: list[str] = []
    for attr, w in weights.items():
        v = candidate.attributes.get(attr)
        if v is None:
            missing.append(attr)
            continue
        spec = specs.get(attr, {})
        if attr in bands and spec.get("min") is None and spec.get("target") is None:
            s, note = band_score(v, bands[attr])
            detail.append(f"{attr}={v} [{note}]")
        elif spec.get("min") is not None and spec.get("target") is None:
            mn = spec["min"]
            s = 1.0 if v >= mn else max(0.0, 1.0 - (mn - v) / 25.0)
            detail.append(f"{attr}={v} (hard min {mn})")
        elif spec.get("target") is not None:
            s = max(0.0, 1.0 - abs(v - spec["target"]) / 99.0)
            detail.append(f"{attr}={v} (target {spec['target']})")
        else:
            s = saturate(v, attr, enable_sat)
            detail.append(f"{attr}={v}" + (" [saturated]" if enable_sat and
                                           v > SATURATION_KNEES.get(attr, DEFAULT_SATURATION_KNEE) else ""))
        acc += w * s
        scored_w += w

    if scored_w <= 0:
        return FitValue.insufficient(
            f"none of the {len(weights)} relevant attributes are published")
    if scored_w < ATTRIBUTE_EVIDENCE_MIN_COVERAGE:
        return FitValue.insufficient(
            f"only {scored_w:.0%} of required attribute weight is published "
            f"(missing: {', '.join(sorted(missing)[:6])})",
            evidence=tuple(detail[:8]))

    base = acc / scored_w

    # ---- interactions (§9)
    iw_total = 0.0
    inter_acc = 0.0
    inter_ev: list[str] = []
    if req.enable_interactions:
        pos = (req.position or candidate.position_primary or "").strip().upper()
        profiles = tuple(p for p in (req.tactical_profile,
                                     req.secondary_tactical_profile) if p)
        blocks = interaction_values(candidate, pos, profiles)
        for blk in blocks:
            for f in blk["active"]:
                iw = min(f["weight"], INTERACTION_TOTAL_CAP - iw_total)
                if iw <= 0:
                    break
                iw_total += iw
                inter_acc += iw * f["value"]
                inter_ev.append(
                    f"{f['feature']} ({f['op']} of {', '.join(f'{a}={v}' for a, v in sorted(f['inputs'].items()))})"
                    f" = {f['value']:.2f} — {f['why']}")
            for sk in blk["skipped"]:
                inter_ev.append(f"{sk['feature']} skipped — {sk['reason']} (UNKNOWN, not 0)")

    if iw_total > 0:
        final = (1.0 - iw_total) * base + inter_acc
    else:
        final = base

    ev = [f"coverage {scored_w:.0%}"]
    if slot is not None:
        ev.append(f"slot {slot.slot} ({slot.duty}) emphasis applied")
    if dims:
        ev.append("tactical-dimension importance shift applied: "
                  + ", ".join(f"{k}={v:.2f}" for k, v in sorted(dims.items())))
    ev += detail[:8]
    ev += inter_ev[:4]
    if missing:
        ev.append(f"missing (excluded, not zeroed): {', '.join(sorted(missing)[:6])}")
    return FitValue.known(final, evidence=tuple(ev))
