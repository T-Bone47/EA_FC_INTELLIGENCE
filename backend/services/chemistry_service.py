"""Chemistry architecture (§15/§16) — honest by construction.

No verified FC26 chemistry rules exist in this system, therefore:
* `chemistry_score` is UNKNOWN (None) — never computed, never approximated;
* what IS reported is STRUCTURAL FIT: factual shared club/league/nation links
  between a candidate and squad members. Structural fit is explicitly NOT a
  chemistry score and is labelled as such everywhere it surfaces;
* the moment verified rules are ingested into `chemistry_rule`
  (verified=TRUE, CANONICAL), scoring activates through the same code path —
  the rule rows define contributions; nothing is hard-coded here.

Squad-optimization prep (§16): `squad_impact` answers "does this card make
the squad better?" using ONLY verified facts — contextual utility delta from
the engine (replacement analysis) plus structural links. It never claims a
chemistry effect that cannot be verified.
"""
from __future__ import annotations

import uuid
from typing import Optional

from backend.domain.card_model import Candidate

LINK_FACTS = ("club", "league", "nation")


def verified_rules(game_version: str) -> list[dict]:
    """Verified, canonical chemistry rules for a game version (may be empty)."""
    from backend.core.db import query
    rows = query(
        """SELECT cr.rule_code, cr.link_type, cr.contribution, cr.threshold,
                  cr.evidence_note, cr.source_observation_id
           FROM chemistry_rule cr
           JOIN game_version gv ON gv.id = cr.game_version_id
           WHERE gv.code = %s AND cr.verified = TRUE
             AND cr.data_status = 'CANONICAL'""",
        (str(game_version).upper(),))
    return [dict(r) for r in rows]


def rule_status(game_version: str) -> dict:
    rules = verified_rules(game_version)
    if not rules:
        return {
            "status": "NO_VERIFIED_RULES",
            "chemistry_available": False,
            "note": ("no verified chemistry rules are ingested for "
                     f"{str(game_version).upper()} — any chemistry score would "
                     "be invented, so none is produced (§15)"),
        }
    return {"status": "RULES_AVAILABLE", "chemistry_available": True,
            "rules": [r["rule_code"] for r in rules]}


def structural_links(candidate: Candidate,
                     squad_members: list[Candidate]) -> list[dict]:
    """Factual shared-attribute links. NOT chemistry — labelled structural."""
    links: list[dict] = []
    for m in squad_members:
        if m.entity_id == candidate.entity_id:
            continue
        for fact in LINK_FACTS:
            cv, mv = getattr(candidate, fact, None), getattr(m, fact, None)
            if cv and mv and str(cv).strip().lower() == str(mv).strip().lower():
                links.append({"member": m.name, "member_id": str(m.entity_id),
                              "link_type": fact, "shared_value": cv})
    return links


def structural_fit(candidate: Candidate,
                   squad_members: list[Candidate]) -> dict:
    links = structural_links(candidate, squad_members)
    by_type: dict[str, int] = {}
    for l in links:
        by_type[l["link_type"]] = by_type.get(l["link_type"], 0) + 1
    return {
        "kind": "STRUCTURAL_FIT",
        "is_chemistry": False,
        "shared": by_type,
        "links": links,
        "note": ("structural links are factual overlaps (club/league/nation), "
                 "not a chemistry score"),
    }


def chemistry_assessment(candidate: Candidate,
                         squad_members: list[Candidate],
                         game_version: str,
                         rules: Optional[list[dict]] = None) -> dict:
    """Chemistry score IF and only IF verified rules exist (§15).

    `rules` may be injected (tests/experiments); production callers leave it
    None and rules are read from the verified canonical store only.
    """
    if rules is None:
        rules = verified_rules(game_version)
    structural = structural_fit(candidate, squad_members)
    if not rules:
        return {
            "status": "CHEMISTRY_UNKNOWN",
            "chemistry_score": None,
            "reason": rule_status(game_version)["note"],
            "structural_fit": structural,
        }
    # Data-driven application: each verified rule contributes per matching
    # structural link, subject to its own threshold/cap. The rule rows (from
    # an authorized source) define the numbers — nothing is invented here.
    score = 0.0
    evidence = []
    for r in rules:
        link_type = (r.get("link_type") or "").lower()
        matching = [l for l in structural["links"] if l["link_type"] == link_type]
        contribution = r.get("contribution") or {}
        threshold = r.get("threshold") or {}
        min_members = int(threshold.get("min_members", 1))
        if len(matching) < min_members:
            continue
        points = float(contribution.get("points", 0))
        per_link = bool(contribution.get("per_link", False))
        cap = contribution.get("cap")
        gained = points * (len(matching) if per_link else 1)
        if cap is not None:
            gained = min(gained, float(cap))
        score += gained
        evidence.append({"rule": r["rule_code"], "link_type": link_type,
                         "matched_links": len(matching), "gained": gained,
                         "note": r.get("evidence_note")})
    return {
        "status": "SCORED",
        "chemistry_score": round(score, 4),
        "evidence": evidence,
        "structural_fit": structural,
    }


def squad_impact(candidate: Candidate, squad_members: list[Candidate],
                 game_version: str,
                 replaced: Optional[Candidate] = None,
                 utility_delta: Optional[float] = None) -> dict:
    """§16 prep: 'would this card make the squad better?' — verified facts only.

    * `utility_delta` — contextual engine score difference (candidate minus
      the member it would replace), computed by the caller from real
      evaluations; None => UNKNOWN.
    * chemistry contribution — only when verified rules exist.
    """
    chem = chemistry_assessment(candidate, squad_members, game_version)
    structural = chem["structural_fit"]
    verdict = "UNKNOWN"
    reasons = []
    if utility_delta is None:
        reasons.append("contextual utility delta unavailable — cannot judge "
                       "squad improvement from ratings alone")
    elif utility_delta > 0:
        verdict = "IMPROVES"
        reasons.append(f"contextual utility delta +{utility_delta:.4f}"
                       + (f" vs {replaced.name}" if replaced else ""))
    elif utility_delta < 0:
        verdict = "DOES_NOT_IMPROVE"
        reasons.append(f"contextual utility delta {utility_delta:.4f}"
                       + (f" vs {replaced.name}" if replaced else ""))
    else:
        verdict = "NEUTRAL"
        reasons.append("contextual utility delta is 0")
    if chem["status"] == "CHEMISTRY_UNKNOWN":
        reasons.append("chemistry effect UNKNOWN (no verified rules) — not "
                       "counted for or against")
    return {
        "verdict": verdict,
        "utility_delta": utility_delta,
        "replaces": replaced.name if replaced else None,
        "chemistry": {"status": chem["status"],
                      "score": chem.get("chemistry_score")},
        "structural_fit": structural,
        "reasons": reasons,
    }
