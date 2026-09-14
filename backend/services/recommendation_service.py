"""RecommendationService — production orchestration for /api/recommendations.

Pipeline:
  1. resolve game_version (never defaults across versions; explicit only)
  2. load candidates from the CANONICAL store (CandidateRepository — production
     module, no test coupling), pre-filtered by position compatibility
  3. entity scope resolution (auto => game_player unless card data exists)
  4. run Engine V2 (deterministic) — v2.1: with squad members / replacement
     current player resolved when the request asks for them
  5. attach deterministic explanations + confidence (+ confidence_v2 §24) +
     freshness + provenance + telemetry (§59)
  6. record SHOWN feedback when a user context is present

The LLM is NOT in this path. Explanations are generated from structured
evidence only (§16).
"""
from __future__ import annotations

import time
import uuid
from typing import Optional

from backend.data_access.candidate_repository import CandidateRepository
from backend.domain.card_model import Candidate
from backend.domain.user_model import SquadContext, UserRequirements
from backend.services import confidence_v2, explanation_service
from backend.services.recommendation_engine_v2 import (
    RecommendationEngineV2, RecommendationResult,
)
from backend.services.scoring_config import ScoringConfig, compatible_positions

# module-level caches for cheap, slowly-changing provenance facts
_META_CACHE: dict[str, tuple[float, dict]] = {}
_META_TTL = 300.0


class RecommendationService:
    def __init__(self, engine: Optional[RecommendationEngineV2] = None,
                 candidates: Optional[CandidateRepository] = None,
                 config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig()
        self.engine = engine or RecommendationEngineV2(self.config)
        self.candidates = candidates or CandidateRepository()

    # ------------------------------------------------------------------ main
    def recommend(self, req: UserRequirements,
                  squad_ctx: Optional[SquadContext] = None) -> dict:
        started = time.perf_counter()
        problems = req.validate()
        if problems:
            raise ValueError("; ".join(problems))
        gv = str(req.game_version).upper()
        vc = self.config.version(gv)   # raises KeyError for unconfigured versions

        pool = self._load_pool(req)
        if not pool and vc.data_status == "NO_DATA":
            raise LookupError(
                f"{gv} has NO ingested production data (status NO_DATA). "
                "Zero records were acquired for this version and none were "
                "fabricated — recommendations are unavailable until legitimate "
                f"{gv} data is ingested.")

        # ---- v2.1: resolve squad members + replacement target ----------------
        squad_members = self._squad_members(squad_ctx, gv) if squad_ctx else None
        replacement_current = None
        if req.replacement_for is not None:
            replacement_current = self._find_entity(gv, req.replacement_for)
            if replacement_current is None:
                raise LookupError(
                    f"replacement_for entity {req.replacement_for} not found in "
                    f"{gv} canonical data (or firewalled) — nothing assumed.")

        engine_started = time.perf_counter()
        result: RecommendationResult = self.engine.recommend(
            pool, req, squad_ctx=squad_ctx, request_id=str(uuid.uuid4()),
            squad_members=squad_members, replacement_current=replacement_current)
        scoring_ms = round((time.perf_counter() - engine_started) * 1000, 2)

        payload = result.to_dict()
        payload["explanations"] = self._explanations(result, req)
        payload["data_freshness"] = self._freshness(gv)
        payload["provenance"] = self._provenance(gv)
        payload["candidate_pool"] = {
            "evaluated": result.evaluations_total,
            "loaded": len(pool),
            "position_prefilter": sorted(compatible_positions(req.position))
            if req.position else None,
            "entity_scope": req.entity_scope,
            "version_config_status": vc.data_status,
        }
        # ---- §24 confidence 2.0 (additive; legacy confidence untouched) ------
        if result.best_evaluation is not None:
            meta = self._version_meta(gv)
            last_obs = None
            if payload["data_freshness"].get("last_source_observation"):
                from datetime import datetime
                try:
                    last_obs = datetime.fromisoformat(
                        payload["data_freshness"]["last_source_observation"])
                except ValueError:
                    last_obs = None
            payload["confidence_v2"] = confidence_v2.compute(
                legacy_score=result.confidence.score,
                last_observed=last_obs,
                source_tier=meta.get("authority_tier"),
                identity_status=(result.best_evaluation.candidate.extra or {}).get("identity_status"),
                unresolved_conflicts=meta.get("unresolved_conflicts", 0),
            )
        # ---- §59 telemetry (no secrets, no user data beyond counts) ----------
        stats = getattr(self.candidates, "last_load_stats", {}) or {}
        payload["telemetry"] = {
            "engine_version": self.engine.engine_version,
            "candidates_loaded": len(pool),
            "candidates_evaluated": result.evaluations_total,
            "excluded_hard": len(result.excluded_hard),
            "excluded_by_floor": len(result.excluded_by_floor),
            "cache_hit": stats.get("cache_hit"),
            "data_version": stats.get("data_version"),
            "scoring_ms": scoring_ms,
            "unknown_components_best": (
                result.confidence.unknown_components + result.confidence.insufficient_components
                if result.best_evaluation is not None else []),
        }
        # ---- Phase 3 §14/§17: card value + Pareto card dimensions ------------
        # Only for explicit ut_card scope — legacy payloads stay bit-identical.
        if req.entity_scope == "ut_card" and result.ranked:
            from backend.services import card_value_service, engine_config as ec
            from backend.services.counterfactual import card_counterfactuals
            payload["card_counterfactuals"] = card_counterfactuals(
                self.engine, req, result, squad_members=squad_members)
            from backend.services.chemistry_service import (
                chemistry_assessment, rule_status)
            payload["chemistry"] = {
                "rule_status": rule_status(gv),
                "best_assessment": (
                    chemistry_assessment(result.best, squad_members or [], gv)
                    if result.best is not None else None),
            }
            top = result.ranked[:ec.VALUE_RANK_TOP_N]
            utilities = {ev.candidate.entity_id: ev.weighted_score for ev in top}
            value_rows = card_value_service.value_rank(
                [ev.candidate for ev in top], utilities,
                budget=req.budget_coins if hasattr(req, "budget_coins") else None)
            payload["card_value"] = {
                "status": ("SCORED" if any(r["status"] == "VALUE_SCORED"
                                           for r in value_rows)
                           else "VALUE_UNAVAILABLE"),
                "method": value_rows[0]["method"] if value_rows else None,
                "ranked": value_rows[:20],
                "note": ("value = marginal contextual utility per verified "
                         "cost; cards without verified prices are listed as "
                         "VALUE_UNAVAILABLE, never as free or worthless"),
            }
            scored = [r for r in value_rows if r["status"] == "VALUE_SCORED"]
            pareto = dict(payload.get("pareto") or {})
            pareto["best_value"] = (
                {"entity_id": scored[0]["entity_id"], "name": scored[0]["name"],
                 "value_score": scored[0]["value_score"]}
                if scored else
                {"unavailable": "no verified price observations in the ranked "
                                "set — value dimension cannot be computed (§14)"})
            within = [r for r in value_rows
                      if (r.get("budget") or {}).get("status") == "WITHIN_BUDGET"]
            pareto["best_within_budget"] = (
                {"entity_id": within[0]["entity_id"], "name": within[0]["name"]}
                if within else
                {"unavailable": ("no verified-price card fits the given budget"
                                 if getattr(req, "budget_coins", None) else
                                 "budget not provided or no verified prices — "
                                 "budget dimension cannot be computed (§13)")})
            payload["pareto"] = pareto

        payload["timing_ms"] = round((time.perf_counter() - started) * 1000, 2)
        return payload

    # ------------------------------------------------------------------ pool
    def _load_pool(self, req: UserRequirements) -> list[Candidate]:
        # §11: entity scopes are NEVER mixed silently. 'ut_card' loads the
        # card pool (card attributes only — never base-player fallback, §5);
        # 'game_player'/'auto' load players. When a scope has no canonical
        # data we say so instead of downgrading to the other scope.
        if req.entity_scope == "ut_card":
            positions = (compatible_positions(req.position.upper())
                         if req.position else None)
            cards = self.candidates.load_cards(req.game_version,
                                               positions=positions)
            if not cards:
                raise LookupError(
                    f"No canonical (non-synthetic) UT card data is ingested for "
                    f"{req.game_version}. Card-level recommendations require real "
                    "card data — nothing is fabricated. Use entity_scope="
                    "'game_player' for player-level intelligence.")
            return cards
        if req.position:
            pool = self.candidates.load_for_position(
                req.game_version, req.position, include_adjacent=True)
        else:
            pool = self.candidates.load_candidates(req.game_version)
        if req.entity_scope == "auto":
            players = [c for c in pool if c.entity_type == "game_player"]
            return players if players else pool
        return [c for c in pool if c.entity_type == req.entity_scope]

    def _find_entity(self, gv: str, entity_id: uuid.UUID) -> Optional[Candidate]:
        """Resolve one canonical entity by id — players then cards (cache-backed)."""
        for c in self.candidates.load_candidates(gv):
            if c.entity_id == entity_id:
                return c
        for c in self.candidates.load_cards(gv):
            if c.entity_id == entity_id:
                return c
        return None

    def _squad_members(self, squad_ctx: SquadContext,
                       gv: str) -> list[Candidate]:
        """Resolve filled squad slots to canonical Candidates (verified facts
        only). Slots whose entity cannot be resolved are skipped — and that is
        reported in the structural evidence, never papered over."""
        filled = squad_ctx.filled_slots()
        if not filled:
            return []
        ids = {s.game_player_id for s in filled if s.game_player_id}
        ids |= {s.ut_card_id for s in filled if s.ut_card_id}
        if not ids:
            return []
        members = [c for c in self.candidates.load_candidates(gv) if c.entity_id in ids]
        return members

    # ------------------------------------------------------------------ extras
    def _explanations(self, result: RecommendationResult,
                      req: UserRequirements) -> dict:
        if result.best_evaluation is None:
            return {"summary": explanation_service.recommendation_summary(result, req),
                    "why_this": [], "why_not_alternatives": [],
                    "strengths": [], "weaknesses": []}
        best_ev = result.best_evaluation
        why_this = explanation_service.why_this_player(
            best_ev.candidate, best_ev.components, req)
        sw = explanation_service.strengths_weaknesses(
            best_ev.candidate, req, self.engine.config)
        why_not = []
        for alt in result.ranked[1:4]:
            why_not.append({
                "name": alt.candidate.name,
                "entity_id": str(alt.candidate.entity_id),
                "reasons": explanation_service.why_not_alternative(
                    best_ev.candidate, best_ev.components,
                    alt.candidate, alt.components),
            })
        return {
            "summary": explanation_service.recommendation_summary(result, req),
            "why_this": why_this,
            "why_not_alternatives": why_not,
            "strengths": sw["strengths"],
            "weaknesses": sw["weaknesses"],
        }

    def _freshness(self, gv: str) -> dict:
        try:
            from backend.core.db import query_one
            row = query_one(
                """SELECT max(so.observed_at) AS last_observed
                   FROM source_observation so
                   JOIN game_version g ON g.id = so.game_version_id
                   WHERE g.code = %s""", (gv,))
            last = row["last_observed"] if row else None
            return {"game_version": gv,
                    "last_source_observation": last.isoformat() if last else None,
                    "market_prices": "UNAVAILABLE — price data is UNKNOWN (§21)",
                    "chemistry_rules": "UNVERIFIED — chemistry withheld (§22)"}
        except Exception:
            return {"game_version": gv, "last_source_observation": None,
                    "market_prices": "UNKNOWN", "chemistry_rules": "UNKNOWN"}

    def _version_meta(self, gv: str) -> dict:
        """Cached provenance meta: authority tier of the sources behind this
        version's game_players + unresolved conflict count (§26/§27)."""
        now = time.monotonic()
        hit = _META_CACHE.get(gv)
        if hit and now - hit[0] < _META_TTL:
            return hit[1]
        meta: dict = {}
        try:
            from backend.core.db import query_one
            row = query_one(
                """SELECT min(sr.authority_tier) AS authority_tier
                   FROM source_registry sr
                   WHERE sr.source_id IN (
                       SELECT DISTINCT gp.source_id FROM game_player gp
                       JOIN game_version g ON g.id = gp.game_version_id
                       WHERE g.code = %s)""", (gv,))
            meta["authority_tier"] = row["authority_tier"] if row else None
            row = query_one(
                """SELECT count(*) AS n FROM attribute_conflict_log acl
                   JOIN game_version g ON g.id = acl.game_version_id
                   WHERE g.code = %s AND acl.resolution = 'UNRESOLVED'""", (gv,))
            meta["unresolved_conflicts"] = row["n"] if row else 0
        except Exception:
            meta = {}                     # UNKNOWN inputs — excluded downstream
        _META_CACHE[gv] = (now, meta)
        return meta

    def _provenance(self, gv: str) -> dict:
        """§25 evidence-graph anchor: which sources carry this version's facts.
        Recommendation -> components -> attributes -> source observation ->
        dataset. The full graph lives in the DB (source_observation, claim,
        evidence); this block is the response-level entry point."""
        try:
            from backend.core.db import query
            rows = query(
                """SELECT sr.source_id, sr.name, sr.license, sr.usage_status,
                          sr.authority_tier, sr.url
                   FROM source_registry sr
                   WHERE sr.source_id IN (
                       SELECT DISTINCT gp.source_id FROM game_player gp
                       JOIN game_version g ON g.id = gp.game_version_id
                       WHERE g.code = %s)
                   ORDER BY sr.authority_tier""", (gv,))
            sources = [dict(r) for r in rows]
        except Exception:
            sources = []
        return {
            "game_version": gv,
            "sources": sources if sources else "UNKNOWN (no source rows resolved)",
            "note": ("attribute values on every candidate trace to these sources "
                     "via source_observation rows recorded at ingestion; component "
                     "evidence strings name the exact attributes used"),
        }
