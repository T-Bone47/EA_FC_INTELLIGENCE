"""COUNTERFACTUALS + SENSITIVITY (§37, §38).

Deterministic post-processing over an existing recommendation result — no pool
reload, no randomness:

  * sensitivity: which components actually decided #1 vs #2 (weighted deltas,
    noise-thresholded) — "the recommendation is highly sensitive to X";
  * counterfactuals: re-score the TOP-N under small, explicit request changes
    (alternative tactical profile, budget removed, attribute minimums removed,
    strict tactics toggled) and report what WOULD change. If nothing changes,
    that is reported too — an honest null result.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Optional

from backend.domain.user_model import UserRequirements
from backend.services.engine_config import (
    COUNTERFACTUAL_PROFILE_ALTERNATIVES, COUNTERFACTUAL_TOP_N,
    SENSITIVITY_MIN_SWING,
)
from backend.services.fit_value import FitStatus


def sensitivity(top_two) -> dict:
    """top_two: the first two rankable CandidateEvaluations (may be <2)."""
    if len(top_two) < 2:
        return {"status": "INSUFFICIENT_ALTERNATIVES",
                "note": "fewer than two rankable candidates — no differential drivers"}
    a, b = top_two[0], top_two[1]
    drivers = []
    for name, fv in a.components.items():
        other = b.components.get(name)
        if other is None:
            continue
        if fv.status == FitStatus.KNOWN and other.status == FitStatus.KNOWN:
            w = a_weight(a, name)
            delta = (fv.value - other.value) * w
            if abs(delta) >= SENSITIVITY_MIN_SWING:
                drivers.append({"component": name, "weighted_delta": round(delta, 4),
                                "winner_value": round(fv.value, 3),
                                "runner_up_value": round(other.value, 3)})
        elif fv.status == FitStatus.KNOWN and other.status != FitStatus.KNOWN:
            drivers.append({"component": name, "weighted_delta": None,
                            "note": f"runner-up is {other.status.value} here — "
                                    "component not comparable (no penalty applied to either)"})
    drivers.sort(key=lambda d: -(abs(d["weighted_delta"]) if d["weighted_delta"] is not None else -1))
    if not drivers:
        summary = ("no single component decided this — the margin is below the "
                   f"{SENSITIVITY_MIN_SWING} noise threshold (tie-breakers ordered the top)")
    else:
        top = drivers[0]
        summary = (f"the ranking is most sensitive to {top['component'].replace('_', ' ')}"
                   + (f" (weighted Δ {top['weighted_delta']:+.3f})" if top["weighted_delta"] is not None else ""))
    return {"status": "OK", "drivers": drivers[:5], "summary": summary}


def a_weight(evaluation, component: str) -> float:
    """Effective (redistributed) weight used for this evaluation."""
    return evaluation.component_weights.get(component, 0.0) if hasattr(evaluation, "component_weights") else 0.0


# ---------------------------------------------------------------------------
def counterfactuals(engine, candidates_by_id: dict, req: UserRequirements,
                    result) -> list[dict]:
    """Re-score the top-N under explicit request mutations. Deterministic and
    cheap: only already-evaluated candidates are re-run."""
    top = [e for e in result.ranked if not e.below_tactical_floor][:COUNTERFACTUAL_TOP_N]
    if not top:
        top = result.ranked[:COUNTERFACTUAL_TOP_N]
    if not top:
        return []
    pool = [e.candidate for e in top]
    # candidates excluded by attribute minimums are re-admitted for the
    # remove-minimums variant (bounded: only those excluded for that reason)
    min_excluded = [d for d in result.excluded_hard
                    if "below required minimum" in (d.get("reason") or "")]

    out: list[dict] = []
    current_winner = result.best.name if result.best else None

    def rerun(modified: UserRequirements, extra: Optional[list] = None) -> Optional[str]:
        evals = []
        for c in pool + (extra or []):
            try:
                e = engine.evaluate(c, modified)
            except ValueError:
                continue
            if e.rankable and not (modified.strict_tactics and e.below_tactical_floor):
                evals.append(e)
        if not evals:
            return None
        # identical ordering contract to the engine: floor-breakers last, then
        # (-score, -OVR, name, entity_id)
        evals.sort(key=lambda e: (
            e.below_tactical_floor,
            -(e.weighted_score or 0.0),
            -(e.candidate.overall_rating or 0),
            e.candidate.name,
            str(e.candidate.entity_id),
        ))
        return evals[0].candidate.name

    # 1) alternative tactical profiles
    for alt in COUNTERFACTUAL_PROFILE_ALTERNATIVES:
        if alt == req.tactical_profile:
            continue
        winner = rerun(replace(req, tactical_profile=alt, secondary_tactical_profile=None))
        changed = winner is not None and winner != current_winner
        out.append({
            "if": f"tactical profile changed to {alt}",
            "then": (f"the top fit becomes {winner}" if changed else
                     f"{current_winner} remains the top fit" if winner else
                     "no rankable candidates under this change"),
            "changes_recommendation": changed,
        })

    # 2) budget removed
    if req.budget_coins is not None:
        if result.budget_status.startswith("BUDGET_UNVERIFIED"):
            out.append({"if": "budget removed",
                        "then": "no effect — the budget was never enforceable "
                                "(no verified prices; BUDGET_UNVERIFIED)",
                        "changes_recommendation": False})
        else:
            winner = rerun(replace(req, budget_coins=None))
            changed = winner is not None and winner != current_winner
            out.append({"if": "budget removed",
                        "then": f"the top fit becomes {winner}" if changed
                                else f"{current_winner} remains the top fit",
                        "changes_recommendation": changed})

    # 3) attribute minimums removed
    if min_excluded:
        extra = [candidates_by_id[d["entity_id"]] for d in min_excluded[:50]
                 if d["entity_id"] in candidates_by_id]
        no_prefs = replace(req, attribute_preferences=[])
        winner = rerun(no_prefs, extra=extra)
        changed = winner is not None and winner != current_winner
        out.append({
            "if": f"the {len(min_excluded)} attribute-minimum exclusion(s) removed",
            "then": (f"{winner} (previously excluded) would take the top spot"
                     if changed and winner in {d['name'] for d in min_excluded}
                     else f"the top fit becomes {winner}" if changed
                     else f"{current_winner} remains the top fit even with "
                          f"{len(min_excluded)} excluded candidate(s) re-admitted"),
            "changes_recommendation": changed,
        })

    # 4) strict tactics toggled
    if result.excluded_by_floor:
        winner = rerun(replace(req, strict_tactics=False))
        changed = winner is not None and winner != current_winner
        out.append({
            "if": "strict tactical floor disabled",
            "then": (f"{len(result.excluded_by_floor)} floor-excluded candidate(s) "
                     f"re-enter; top fit becomes {winner}" if changed else
                     f"{len(result.excluded_by_floor)} floor-excluded candidate(s) "
                     f"re-enter but {current_winner} remains the top fit"),
            "changes_recommendation": changed,
        })
    return out


# ---------------------------------------------------------------------------
# Phase 3 §35 — CARD counterfactuals. Only invoked for entity_scope='ut_card';
# legacy counterfactuals() output is untouched. Deterministic: every variant
# re-scores already-evaluated candidates through the SAME engine.
def card_counterfactuals(engine, req, result,
                         squad_members: Optional[list] = None) -> list[dict]:
    from dataclasses import replace as _replace

    from backend.services.engine_config import BUDGET_COUNTERFACTUAL_STEP
    from backend.services.scoring_config import compatible_positions
    top = [e for e in result.ranked if not e.below_tactical_floor] or list(result.ranked)
    if not top:
        return []
    pool = [e.candidate for e in top[:COUNTERFACTUAL_TOP_N]]
    current_winner = result.best.name if result.best else None
    out: list[dict] = []

    def rerun(candidates, modified) -> Optional[str]:
        evals = []
        for c in candidates:
            try:
                e = engine.evaluate(c, modified)
            except ValueError:
                continue
            if e.rankable and not (modified.strict_tactics and e.below_tactical_floor):
                evals.append(e)
        if not evals:
            return None
        evals.sort(key=lambda e: (
            e.below_tactical_floor,
            -(e.weighted_score or 0.0),
            -(e.candidate.overall_rating or 0),
            e.candidate.name,
            str(e.candidate.entity_id),
        ))
        return evals[0].candidate.name

    def variant(label: str, candidates, modified) -> None:
        winner = rerun(candidates, modified)
        changed = winner is not None and winner != current_winner
        out.append({
            "if": label,
            "then": (f"the top fit becomes {winner}" if changed else
                     f"{current_winner} remains the top fit" if winner else
                     "no rankable candidates under this change"),
            "changes_recommendation": changed,
        })

    # 1) budget +100K (§35)
    if req.budget_coins is not None:
        if result.budget_status.startswith("BUDGET_UNVERIFIED"):
            out.append({"if": f"budget raised by {BUDGET_COUNTERFACTUAL_STEP:,} coins",
                        "then": "no effect — the budget was never enforceable "
                                "(no verified prices; BUDGET_UNVERIFIED)",
                        "changes_recommendation": False})
        else:
            variant(f"budget raised by {BUDGET_COUNTERFACTUAL_STEP:,} coins",
                    pool,
                    _replace(req, budget_coins=req.budget_coins + BUDGET_COUNTERFACTUAL_STEP))

    # 2) top card WITHOUT its PlayStyle+ (§35/§6 — does the + actually matter?)
    best = top[0].candidate
    if best.playstyles_plus:
        stripped = _replace(best, playstyles_plus=[])
        others = pool[1:]
        winner = rerun([stripped] + others, req)
        changed = winner is not None and winner != current_winner
        out.append({
            "if": f"{best.name} had NO PlayStyle+",
            "then": (f"the top fit becomes {winner}" if changed else
                     f"{current_winner} remains the top fit even without its "
                     "PlayStyle+ (context, not the +, is driving the fit)"),
            "changes_recommendation": changed,
        })

    # 3) alternative position (§35)
    if req.position:
        alts = sorted(compatible_positions(req.position.upper()) - {req.position.upper()})
        if alts:
            variant(f"the requested position were {alts[0]} instead of "
                    f"{req.position.upper()}", pool, _replace(req, position=alts[0]))

    # 4) removing a squad player (§35/§16)
    if squad_members:
        for m in squad_members[:3]:
            remaining = [x for x in squad_members if x.entity_id != m.entity_id]
            try:
                alt_result = engine.recommend(
                    pool, req, squad_members=remaining,
                    replacement_current=None, request_id="cf-squad")
            except Exception:
                continue
            winner = alt_result.best.name if alt_result.best else None
            changed = winner is not None and winner != current_winner
            out.append({
                "if": f"{m.name} were removed from the squad",
                "then": (f"the top fit becomes {winner}" if changed else
                         f"{current_winner} remains the top fit"),
                "changes_recommendation": changed,
            })

    # 5) chemistry (§35/§15) — honest unavailability
    from backend.services.chemistry_service import rule_status
    chem = rule_status(req.game_version)
    if not chem.get("chemistry_available"):
        out.append({
            "if": "verified chemistry rules existed",
            "then": "cannot be computed — no verified chemistry rules are "
                    "ingested for this version, and inventing a chemistry "
                    "effect is prohibited (§15). Structural links are "
                    "reported separately and are not chemistry.",
            "changes_recommendation": None,
        })
    return out
