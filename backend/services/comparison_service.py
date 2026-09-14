"""Comparison service (§32): why is A better for THIS user — not just "+2 OVR".

Compares 2-4 entities (game players or cards) side by side on facades,
detailed attributes, PlayStyles and — when a user context is supplied —
per-component fit for that user's requirements.
"""
from __future__ import annotations

import uuid
from typing import Optional

from backend.data_access.candidate_repository import CandidateRepository
from backend.domain.card_model import Candidate
from backend.domain.user_model import UserRequirements
from backend.services.recommendation_engine_v2 import RecommendationEngineV2
FACADES = ("pace", "shooting", "passing", "dribbling", "defending", "physicality")
KEY_DETAILS = ("acceleration", "sprint_speed", "finishing", "shot_power",
               "vision", "short_passing", "long_passing", "crossing",
               "ball_control", "agility", "balance", "reactions", "composure",
               "stamina", "strength", "defensive_awareness", "interceptions",
               "standing_tackle", "heading_accuracy", "positioning")
GK_DETAILS = ("gk_diving", "gk_handling", "gk_kicking", "gk_positioning",
              "gk_reflexes")


class ComparisonService:
    def __init__(self, engine: Optional[RecommendationEngineV2] = None,
                 candidates: Optional[CandidateRepository] = None):
        self.engine = engine or RecommendationEngineV2()
        self.candidates = candidates or CandidateRepository()

    def compare(self, game_version: str, entity_ids: list[uuid.UUID],
                req: Optional[UserRequirements] = None) -> dict:
        if not 2 <= len(entity_ids) <= 4:
            raise ValueError("compare requires between 2 and 4 entity ids")
        # §11/§12: the comparison pool spans both entity scopes — players AND
        # canonical cards. Cards carry card-level attributes only (§5); the
        # column payload exposes where each value came from.
        pool = {c.entity_id: c for c in self.candidates.load_candidates(game_version)}
        pool.update({c.entity_id: c for c in self.candidates.load_cards(game_version)})
        chosen: list[Candidate] = []
        missing: list[str] = []
        for eid in entity_ids:
            c = pool.get(eid)
            if c is None:
                missing.append(str(eid))
            else:
                chosen.append(c)
        if missing:
            raise LookupError(f"entities not found in {game_version} canonical data: "
                              + ", ".join(missing))

        types = {c.entity_type for c in chosen}
        scope_note = None
        if len(types) > 1:
            scope_note = ("mixed entity comparison: game_player columns show "
                          "base-player data, ut_card columns show card-level "
                          "data only (§5) — they are NOT the same entity scope")

        columns = []
        for c in chosen:
            is_gk = c.position_primary == "GK"
            details = GK_DETAILS if is_gk else KEY_DETAILS
            extra = c.extra or {}
            card_block = None
            if c.entity_type == "ut_card":
                card_block = {
                    "card_type": extra.get("card_type"),
                    "rarity_raw": extra.get("rarity_raw"),
                    "release_date": extra.get("release_date"),
                    "source_card_id": extra.get("source_card_id"),
                    "canonical_card_id": extra.get("canonical_card_id"),
                    "identity_status": extra.get("card_identity_status"),
                    "attribute_source": extra.get("attribute_source"),
                    "price_platform": extra.get("price_platform"),
                    "price_observed_at": extra.get("price_observed_at"),
                    "price_confidence": extra.get("price_confidence"),
                    "roles": extra.get("roles") or [],
                }
            columns.append({
                "entity_id": str(c.entity_id),
                "entity_type": c.entity_type,
                "name": c.name,
                "position": c.position_primary,
                "secondary_positions": c.secondary_positions,
                "nation": c.nation, "club": c.club, "league": c.league,
                "overall_rating": c.overall_rating,
                "facades": {f: c.attributes.get(f) for f in FACADES},
                "details": {d: c.attributes.get(d) for d in details},
                "playstyles_base": c.playstyles_base,
                "playstyles_plus": c.playstyles_plus,
                "playstyle_data_published": c.playstyle_data_published,
                "rarity": c.rarity,
                "price_coins": c.price_coins,   # None => UNKNOWN, never 0
                "card": card_block,
            })

        verdict: dict = {"user_context": False}
        if req is not None:
            req.game_version = game_version
            evals = []
            for c in chosen:
                try:
                    evals.append(self.engine.evaluate(c, req))
                except ValueError:
                    evals.append(None)   # version mismatch etc.
            if all(e is not None for e in evals):
                order = sorted(range(len(evals)),
                               key=lambda i: (-(evals[i].weighted_score or -1),
                                              chosen[i].name), reverse=False)
                order = [i for i in order if evals[i].weighted_score is not None]
                per_component = {}
                for comp in self.engine.config.component_weights:
                    per_component[comp] = [
                        (evals[i].components[comp].to_dict() if evals[i] else None)
                        for i in range(len(chosen))]
                best_i = order[0] if order else None
                verdict = {
                    "user_context": True,
                    "ranked_for_user": [
                        {"name": chosen[i].name,
                         "entity_id": str(chosen[i].entity_id),
                         "weighted_score": round(evals[i].weighted_score or 0, 4)}
                        for i in order],
                    "per_component": per_component,
                    "why": None,
                }
                if best_i is not None and len(order) > 1:
                    second = order[1]
                    from backend.services import explanation_service
                    verdict["why"] = explanation_service.why_not_alternative(
                        chosen[best_i], evals[best_i].components,
                        chosen[second], evals[second].components)
                    verdict["why"].insert(
                        0, f"For THIS request, {chosen[best_i].name} ranks above "
                           f"{chosen[second].name}:")
        out = {"game_version": game_version, "columns": columns, "verdict": verdict}
        if scope_note:
            out["scope_note"] = scope_note
        return out
