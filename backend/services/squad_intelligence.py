"""SQUAD INTELLIGENCE (§18, §19, §20).

Separates three concepts the V2 baseline conflated or lacked:
  * individual_fit  — the engine's per-candidate weighted score (unchanged);
  * squad_fit       — ADVISORY structural analysis: verified link density,
    position coverage, duplicate archetypes, complementarity. Chemistry itself
    stays UNKNOWN/INSUFFICIENT until rules are verified — squad_fit never
    pretends otherwise (it is explicitly not a chemistry score);
  * replacement_fit — candidate vs CURRENT_PLAYER comparison with an honest
    UPGRADE / SIDEGRADE / DOWNGRADE verdict and evidence (never "upgrade
    because +2 OVR").

All inputs are verified facts (canonical attributes, club/league/nation links,
computed archetypes). Missing data -> UNKNOWN, never assumed.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Optional

from backend.domain.card_model import Candidate
from backend.domain.user_model import SquadContext, UserRequirements
from backend.services import archetypes
from backend.services.engine_config import (
    REPLACEMENT_SACRIFICE_CRITICAL, REPLACEMENT_UPGRADE_MARGIN,
    SQUAD_COMPLEMENT_BONUS, SQUAD_DUPLICATE_ARCHETYPE_FACTOR,
)
from backend.services.fit_value import FitStatus, FitValue

# attribute groups used to derive a coarse stylistic bias for complementarity
_ATTACK_OUTPUT = ("finishing", "vision", "long_shots", "positioning", "dribbling_detail")
_DEFENSE_OUTPUT = ("interceptions", "standing_tackle", "defensive_awareness", "defending")


def stylistic_bias(candidate: Candidate) -> Optional[str]:
    """ATTACKING / DEFENSIVE / BALANCED from KNOWN attributes only.
    None when evidence is insufficient (never guessed)."""
    atk = [candidate.attributes.get(a) for a in _ATTACK_OUTPUT]
    dfs = [candidate.attributes.get(a) for a in _DEFENSE_OUTPUT]
    atk = [v for v in atk if v is not None]
    dfs = [v for v in dfs if v is not None]
    if len(atk) < 3 or len(dfs) < 2:
        return None
    a, d = sum(atk) / len(atk), sum(dfs) / len(dfs)
    if a - d >= 6:
        return "ATTACKING"
    if d - a >= 6:
        return "DEFENSIVE"
    return "BALANCED"


def _complements(bias_a: Optional[str], bias_b: Optional[str]) -> Optional[bool]:
    if bias_a is None or bias_b is None:
        return None
    if bias_a == bias_b == "BALANCED":
        return True
    return bias_a != bias_b


def squad_structural_fit(candidate: Candidate, squad_members: list[Candidate],
                         req: UserRequirements,
                         squad_ctx: Optional[SquadContext] = None) -> FitValue:
    """ADVISORY structural analysis for a squad-context recommendation.

    squad_members: the already-filled squad players (resolved Candidates).
    Scores (0..1): link density (verified club/league/nation facts) +
    archetype diversity + complementarity. Explicitly NOT chemistry."""
    if not squad_members:
        return FitValue.unknown("squad has no filled slots to analyze structurally")

    ev: list[str] = []
    # 1) verified link density
    link_hits = 0
    link_total = 0
    for m in squad_members:
        for fact in ("club", "league", "nation"):
            cv, mv = getattr(candidate, fact), getattr(m, fact)
            if mv is not None:
                link_total += 1
                if cv is not None and cv == mv:
                    link_hits += 1
    link_share = (link_hits / link_total) if link_total else None
    if link_share is None:
        ev.append("link facts UNKNOWN across the squad — link density not scored")
    else:
        ev.append(f"verified link density {link_hits}/{link_total} shared club/league/nation facts")

    # 2) duplicate archetypes (§18: two elite AMs — second is less valuable)
    cand_arch = archetypes.dominant_archetype(candidate)
    duplicates = []
    if cand_arch:
        for m in squad_members:
            m_arch = archetypes.dominant_archetype(m)
            if m_arch and m_arch[0] == cand_arch[0]:
                duplicates.append(m.name)
    dup_factor = 1.0
    if duplicates:
        dup_factor = SQUAD_DUPLICATE_ARCHETYPE_FACTOR
        ev.append(f"duplicate archetype {cand_arch[0]} already in squad "
                  f"({', '.join(duplicates[:3])}) — value scaled ×{dup_factor}")
    elif cand_arch:
        ev.append(f"adds archetype {cand_arch[0]} not yet in the squad")

    # 3) complementarity (§19) at the requested position
    comp_bonus = 0.0
    same_pos = [m for m in squad_members
                if (m.position_primary or "").upper() == (req.position or "").upper()]
    if same_pos and req.position:
        cand_bias = stylistic_bias(candidate)
        for m in same_pos:
            pair = _complements(cand_bias, stylistic_bias(m))
            if pair is None:
                ev.append(f"complementarity vs {m.name}: UNKNOWN (insufficient attribute evidence)")
            elif pair:
                comp_bonus = max(comp_bonus, SQUAD_COMPLEMENT_BONUS)
                ev.append(f"complements {m.name} ({stylistic_bias(m)} ↔ {cand_bias})")
            else:
                ev.append(f"duplicates the profile of {m.name} ({cand_bias}) — no complement bonus")
    # complement hint without squad members at the position (from parsed intent)
    hint = getattr(req, "complement_hint", None)
    if hint and not same_pos:
        hint_bias = (hint.get("bias") or "").upper()
        cand_bias = stylistic_bias(candidate)
        pair = _complements(hint_bias or None, cand_bias)
        if pair:
            comp_bonus = max(comp_bonus, SQUAD_COMPLEMENT_BONUS)
            ev.append(f"complements the described partner ({hint_bias or 'unknown bias'}) — advisory")
        elif pair is False:
            ev.append(f"mirrors the described partner profile ({hint_bias}) — advisory")

    # weighted aggregation over KNOWN parts only (same honesty pattern as the
    # engine: unknown parts are excluded and weights renormalized)
    parts: list[tuple[float, float]] = []   # (weight, value)
    if link_share is not None:
        parts.append((0.5, min(1.0, link_share * 2)))   # 50% shared facts -> full marks
    if cand_arch is not None:
        parts.append((0.3, 1.0 if not duplicates else 0.25))
    if comp_bonus > 0:
        parts.append((0.2, 1.0))
    elif same_pos or hint:
        parts.append((0.2, 0.5))                        # analyzed, no complement found
    if not parts:
        return FitValue.insufficient(
            "no verified structural evidence (links, archetypes or position "
            "partners) to analyze — withheld, not scored low",
            evidence=tuple(ev))
    wsum = sum(w for w, _ in parts)
    score = min(1.0, sum(w * v for w, v in parts) / wsum)
    ev.append("ADVISORY structural fit — NOT a chemistry score "
              "(chemistry rules remain unverified/UNKNOWN)")
    return FitValue.known(score, evidence=tuple(ev))


# ---------------------------------------------------------------------------
# §20 — replacement intelligence
# ---------------------------------------------------------------------------
def replacement_analysis(current_name: str,
                         current_components: dict[str, FitValue],
                         current_score: Optional[float],
                         current_candidate: Candidate,
                         ranked_evaluations: list,
                         ) -> list[dict]:
    """For each ranked candidate: UPGRADE / SIDEGRADE / DOWNGRADE vs the
    current player, with component-level evidence. Never verdicts on OVR."""
    out: list[dict] = []
    for e in ranked_evaluations:
        improved, sacrificed = [], []
        for name, fv in e.components.items():
            cur = current_components.get(name)
            if cur is None or cur.status != FitStatus.KNOWN or fv.status != FitStatus.KNOWN:
                continue
            delta = fv.value - cur.value
            if delta >= 0.05:
                improved.append(f"{name} {cur.value:.2f}→{fv.value:.2f} ({delta:+.2f})")
            elif delta <= -0.05:
                sacrificed.append(f"{name} {cur.value:.2f}→{fv.value:.2f} ({delta:+.2f})")
        critical = any(
            (cur.status == FitStatus.KNOWN and fv.status == FitStatus.KNOWN
             and (fv.value - cur.value) <= -REPLACEMENT_SACRIFICE_CRITICAL)
            for name, fv in e.components.items()
            if (cur := current_components.get(name)) is not None)

        if current_score is None or e.weighted_score is None:
            verdict, reason = "UNKNOWN", "insufficient evidence to compare"
        elif e.weighted_score >= current_score + REPLACEMENT_UPGRADE_MARGIN and not critical:
            verdict = "UPGRADE"
            reason = f"fit score {e.weighted_score:.3f} vs current {current_score:.3f}"
        elif e.weighted_score <= current_score - REPLACEMENT_UPGRADE_MARGIN:
            verdict = "DOWNGRADE"
            reason = f"fit score {e.weighted_score:.3f} vs current {current_score:.3f}"
        else:
            verdict = "SIDEGRADE"
            reason = (f"fit score within ±{REPLACEMENT_UPGRADE_MARGIN} of current "
                      f"({e.weighted_score:.3f} vs {current_score:.3f}) — lateral move")
        if critical and verdict == "UPGRADE":
            verdict = "SIDEGRADE"
            reason += f"; downgraded from UPGRADE: critical sacrifice (> {REPLACEMENT_SACRIFICE_CRITICAL})"

        # attribute-level deltas (top movers, KNOWN on both sides only)
        attr_deltas = []
        for attr in sorted(set(current_candidate.attributes.known()) &
                           set(e.candidate.attributes.known())):
            d = e.candidate.attributes.get(attr) - current_candidate.attributes.get(attr)
            if abs(d) >= 5:
                attr_deltas.append((d, attr,
                                    current_candidate.attributes.get(attr),
                                    e.candidate.attributes.get(attr)))
        attr_deltas.sort(reverse=True)
        out.append({
            "name": e.candidate.name,
            "entity_id": str(e.candidate.entity_id),
            "verdict": verdict,
            "reason": reason,
            "improved_components": improved[:5],
            "sacrificed_components": sacrificed[:5],
            "critical_sacrifice": critical,
            "attribute_movers": [
                {"attribute": a, "delta": d, "current": c, "candidate": n}
                for d, a, c, n in (attr_deltas[:3] + attr_deltas[-3:])
            ],
            "ovr_note": _ovr_honesty(current_candidate, e.candidate),
        })
    return out


def _ovr_honesty(current: Candidate, cand: Candidate) -> str:
    co, no = current.overall_rating, cand.overall_rating
    if co is None or no is None:
        return "OVR comparison UNKNOWN (not published) — verdict is fit-based only"
    if no > co:
        return (f"candidate OVR {no} > current {co}, but the verdict is based on "
                "contextual fit, not OVR")
    if no < co:
        return (f"candidate OVR {no} < current {co} — a lower-OVR player can still "
                "be the better fit for THIS context")
    return "same OVR — verdict is fit-based only"
