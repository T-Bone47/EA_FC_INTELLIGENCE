"""Canonical production recommendation endpoint: POST /api/recommendations.

Version-aware (game_version is a first-class, required-in-spirit parameter),
deterministic, explainable. Synthetic fixtures are excluded by the candidate
repository. The old demo V1 path is intentionally gone (§24).

Also hosts the natural-language intent parser: a DETERMINISTIC rule-based
parser converts free text into a structured draft request. An LLM may later
replace the parser front-end, but every produced value is validated against
reference data — the parser can never invent ratings/cards/prices (§16).
"""
from __future__ import annotations

import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import (
    CurrentUser, current_user_optional, rate_limit_default, validate_game_version,
)
from backend.api.schemas import (
    NaturalLanguageRequest, RecommendationRequest,
)
from backend.api.routes.meta import FORMATIONS
from backend.repositories.feedback_repository import FeedbackRepository
from backend.repositories.player_repository import PlayerRepository
from backend.repositories.squad_repository import SquadRepository
from backend.services.recommendation_service import RecommendationService
from backend.services.scoring_config import (
    POSITION_ATTRIBUTE_WEIGHTS, TACTICAL_ATTRIBUTE_WEIGHTS,
)

router = APIRouter(prefix="/api", tags=["recommendations"],
                   dependencies=[Depends(rate_limit_default)])

_service: Optional[RecommendationService] = None


def get_service() -> RecommendationService:
    global _service
    if _service is None:
        _service = RecommendationService()
    return _service


@router.post("/recommendations")
def recommendations(body: RecommendationRequest,
                    user: Optional[CurrentUser] = Depends(current_user_optional)) -> dict:
    gv = validate_game_version(body.game_version)
    if body.position and body.position.upper() not in POSITION_ATTRIBUTE_WEIGHTS:
        raise HTTPException(422, f"Unknown position {body.position!r} for {gv}. "
                                 f"Known: {sorted(POSITION_ATTRIBUTE_WEIGHTS)}")
    if body.tactical_profile.upper() not in TACTICAL_ATTRIBUTE_WEIGHTS:
        raise HTTPException(422, f"Unknown tactical_profile {body.tactical_profile!r}. "
                                 f"Known: {sorted(TACTICAL_ATTRIBUTE_WEIGHTS)}")
    req = body.to_requirements()
    req.game_version = gv

    squad_ctx = None
    if req.squad_id:
        if user is None:
            raise HTTPException(401, "Squad context requires authentication.")
        squad_ctx = SquadRepository().squad_context(uuid.UUID(user.id), req.squad_id)
        if squad_ctx is None:
            raise HTTPException(404, "Squad not found (or not owned by you).")
        if squad_ctx.game_version != gv:
            raise HTTPException(422, f"Squad belongs to {squad_ctx.game_version}; "
                                     f"request targets {gv}. Versions are never mixed.")

    try:
        result = get_service().recommend(req, squad_ctx=squad_ctx)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except KeyError as e:
        raise HTTPException(422, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))

    # feedback: record SHOWN for authenticated users (future ML labels, §34)
    if user is not None and result.get("best"):
        try:
            p_repo = PlayerRepository()
            gvid = p_repo.game_version_id(gv)
            FeedbackRepository().record(
                user_id=uuid.UUID(user.id), game_version_id=gvid,
                action="SHOWN", entity_type=result["best"]["entity_type"],
                entity_id=uuid.UUID(result["best"]["entity_id"]),
                request_context={"position": req.position,
                                 "tactical_profile": req.tactical_profile,
                                 "budget_coins": req.budget_coins,
                                 "squad_id": str(req.squad_id) if req.squad_id else None},
                recommendation_id=result["request_id"])
        except Exception:
            pass  # feedback capture must never break a recommendation
    return result


# ------------------------------------------------------------------ intent parse
_POSITION_WORDS = {
    "st": "ST", "striker": "ST", "forward": "ST",
    "lw": "LW", "left wing": "LW", "left winger": "LW",
    "rw": "RW", "right wing": "RW", "right winger": "RW",
    "cam": "CAM", "attacking mid": "CAM", "attacking midfielder": "CAM", "number 10": "CAM",
    "cm": "CM", "central mid": "CM", "central midfielder": "CM", "midfielder": "CM",
    "cdm": "CDM", "defensive mid": "CDM", "defensive midfielder": "CDM",
    "lm": "LM", "left mid": "LM", "rm": "RM", "right mid": "RM", "right cm": "CM",
    "lb": "LB", "left back": "LB", "rb": "RB", "right back": "RB",
    "cb": "CB", "centre back": "CB", "center back": "CB", "defender": "CB",
    "gk": "GK", "goalkeeper": "GK", "keeper": "GK",
}
_TACTIC_WORDS = {
    "high press": "PRESSING", "pressing": "PRESSING", "gegenpress": "PRESSING",
    "counter": "COUNTER_ATTACK", "quick transition": "COUNTER_ATTACK",
    "transitions": "COUNTER_ATTACK", "possession": "POSSESSION", "tiki": "POSSESSION",
    "dribbl": "DRIBBLE_HEAVY", "skill": "DRIBBLE_HEAVY",
    "cross": "CROSSING", "wing play": "CROSSING",
    "long shot": "LONG_SHOT", "shoot from distance": "LONG_SHOT",
    "direct": "DIRECT_PLAY", "long ball": "DIRECT_PLAY",
    "build up": "BUILD_UP", "build-up": "BUILD_UP", "play out": "BUILD_UP",
    "pace": "PACE_ABUSER", "fast": "PACE_ABUSER", "speed": "PACE_ABUSER",
}
_ATTR_WORDS = {
    "stamina": "stamina", "defensive awareness": "defensive_awareness",
    "passing": "short_passing", "vision": "vision", "pace": "pace",
    "speed": "pace", "shooting": "shooting", "finishing": "finishing",
    "defending": "defending", "physical": "strength", "strength": "strength",
    "dribbling": "dribbling_detail", "crossing": "crossing",
    "long shots": "long_shots", "aggression": "aggression",
    "composure": "composure", "ball control": "ball_control",
}


def parse_intent(text: str, game_version: str) -> dict:
    """Deterministic natural-language -> structured draft. No fabrication:
    only reference-table values are emitted; unrecognized text is ignored."""
    t = f" {text.lower()} "
    draft: dict = {"game_version": game_version, "parsed_from": text,
                   "confidence_notes": []}

    m = re.search(r"\b(\d(?:-\d){2,4})\b", t)
    if m and m.group(1) in FORMATIONS:
        draft["formation"] = m.group(1)

    best_pos, best_pos_len = None, 0
    for word, pos in _POSITION_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", t) and len(word) > best_pos_len:
            best_pos, best_pos_len = pos, len(word)
    if best_pos:
        draft["position"] = best_pos

    for word, profile in _TACTIC_WORDS.items():
        if word in t:
            draft.setdefault("tactical_profile", profile)
            break

    prefs = []
    for word, attr in _ATTR_WORDS.items():
        if word in t and all(p["attribute"] != attr for p in prefs):
            prefs.append({"attribute": attr, "weight": 1.5})
    if prefs:
        draft["attribute_preferences"] = prefs[:10]

    m = re.search(r"(\d[\d.,]*)\s*(k| thousand)?\s*(coins|budget)?", t)
    budget = None
    for bm in re.finditer(r"(\d[\d.,]*)\s*(k|k coins|thousand)?\b", t):
        num = bm.group(1).replace(",", "")
        try:
            val = float(num)
        except ValueError:
            continue
        if bm.group(2):
            val *= 1000
        if 500 <= val <= 10_000_000:
            budget = int(val)
            break
    if budget:
        draft["budget_coins"] = budget
    else:
        draft["confidence_notes"].append("no budget detected")

    ps = [p for p in ("Tiki Taka", "First Touch", "Quick Step", "Rapid", "Finesse Shot",
                      "Power Shot", "Press Proven", "Relentless", "Whipped Pass",
                      "Incisive Pass", "Pinged Pass", "Anticipate", "Jockey",
                      "Technical", "Trickster", "Intercept")
          if p.lower() in t]
    if ps:
        draft["desired_playstyles"] = ps[:6]

    draft["confidence_notes"].append(
        "deterministic rule parser — every emitted value comes from reference "
        "tables; unrecognized fragments were ignored, never guessed")
    return draft


@router.get("/recommendations/feedback/analytics")
def feedback_analytics(game_version: Optional[str] = Query(default=None)) -> dict:
    """§33 phase-2 MEASURE: deterministic label analytics. No ML, no user
    identifiers, no secrets — counts and readiness only."""
    from backend.services import feedback_analytics as fa
    gv = validate_game_version(game_version) if game_version else None
    return fa.summarize(game_version=gv)


@router.post("/recommendations/parse-intent")
def parse_intent_endpoint(body: NaturalLanguageRequest) -> dict:
    gv = validate_game_version(body.game_version)
    # v2.1: structured intent engine (§2/§3/§4) — every emitted value carries
    # source + confidence + explicit-vs-inferred provenance; hard constraints
    # and soft preferences are separated. Legacy draft keys are preserved.
    from backend.services.intent_parser import parse as parse_structured
    intent = parse_structured(body.text, gv)
    draft = parse_intent(body.text, gv)          # legacy flat draft (compat)
    structured = intent.to_draft()
    merged = {**draft, **{k: v for k, v in structured.items()
                          if k in ("slot", "secondary_tactical_profile", "archetype",
                                   "attribute_bands", "required_playstyles",
                                   "overall_quality_bias", "complement_hint",
                                   "hard_constraints", "soft_preferences", "fields",
                                   "unrecognized_fragments")}}
    # the structured parser is strictly better at tactics/positions/budget:
    for key in ("position", "formation", "tactical_profile", "budget_coins",
                "attribute_preferences", "desired_playstyles"):
        if key in structured:
            merged[key] = structured[key]
    merged["confidence_notes"] = structured["confidence_notes"]
    return {"draft": merged,
            "note": "Review the draft, then POST /api/recommendations with it. "
                    "The parser never invents ratings, cards or prices. Every "
                    "field lists its source (USER_TEXT/INFERRED/DEFAULT), "
                    "confidence and whether it was explicit."}
