"""V3 recommendation service for release-scoped player and card references.

Wraps RecommendationEngineV3 with candidate loading and API response
assembly. This is the only layer that touches the database/repository --
the engine itself stays pure (INV-4 pool independence, INV-9 determinism).

Version-aware (Phase 22/23):
  * the frozen reference distribution is resolved from the REQUEST's
    game_version (FC26 -> fc26-players-*, FC27 -> fc27-players-*); a
    distribution is never borrowed across versions;
  * FC27 data is RESEARCH_ONLY. It is served only when the request opts in
    (`include_research_data=true`) AND the deployment is not production;
    the licence gate enforces the second condition structurally
    (ProductionOverrideForbidden). Without the opt-in an FC27 request is
    refused with an explicit reason -- never answered with FC26 data;
  * every response states its dataset: game_version, data_status,
    reference distribution version/universe.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import replace

from backend.api.schemas_v3 import RecommendationRequestV3
from backend.data_access.candidate_repository import CandidateRepository
from backend.domain.card_model import FACADE_ATTRS, Candidate
from backend.domain.user_model import AttributePreference, UserRequirements
from backend.core import config as app_config
from backend.services.data_license_gate import (
    DataLicenseGateFailure,
    Environment, catalogue_releases, environment_from_settings,
    ProductionOverrideForbidden,

)
from backend.services.explanation_service_v3 import explain, why_not
from backend.services.v3_response_blocks import (
    attribute_row as _attr_row, confidence_block, division_block, evidence_block,
    evidence_gap, intervals_overlap as _overlap, leading_pair, near_tie_block, tactical_fit_block)
from backend.services.recommendation_engine_v3 import (
    ENGINE_VERSION,
    RecommendationEngineV3,
    UnsupportedEntityScopeError,
)
from backend.services.reference_distribution import (
    POSITION_GROUPS,
    ReferenceDistributionMismatch,
    ReferenceDistributionUnavailable,
    resolve_serving_reference,
    position_group_for,
)
from backend.services.v3_config import (
    DEFAULT_V3_CONFIG,
    CalibratedValue,
    CalibrationStatus,
)

# Kept for backward compatibility; requests now resolve their own version.
DEFAULT_REFERENCE_VERSION = "fc26-players-2026-09-r1"

# Structured telemetry (Phase 17). Deliberately excludes any per-user
# identifying information -- only request shape, engine/config/data
# versions, and aggregate outcome counts.
telemetry_log = logging.getLogger("eafc.v3.telemetry")


class ServiceRefusal(Exception):
    requires: str | None = None   # machine-readable remedy for the client, e.g. "include_research_data"
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _to_user_requirements(body: RecommendationRequestV3) -> UserRequirements:
    prefs = [
        AttributePreference(attribute=p.attribute, min_value=p.min_value,
                            target_value=p.target_value, weight=p.weight)
        for p in body.attribute_preferences
    ]
    return UserRequirements(
        game_version=body.game_version,
        position=body.position,
        formation=body.formation,
        slot=body.slot,
        tactical_profile=body.tactical_profile,
        secondary_tactical_profile=body.secondary_tactical_profile,
        attribute_preferences=prefs,
        desired_playstyles=list(body.desired_playstyles),
        desired_playstyles_plus=list(body.desired_playstyles_plus),
        required_playstyles=list(body.required_playstyles),
        required_league=body.required_league,
        required_club=body.required_club,
        required_nation=body.required_nation,
        squad_id=body.squad_id,
        entity_scope=body.entity_scope,
        limit=body.limit,
    )


WHAT_IF_DEPTH = 50  # == the request schema's max `limit`: tracked players get a real rank
# Game versions whose source publishes EA division labels. FC26's source only carries a 'male'
# gender value, so a division filter there would silently match nobody -> refused instead.
DIVISIONS_BY_GAME_VERSION: dict[str, tuple[str, ...]] = {"FC27": ("Men's Football", "Women's Football")}


def check_division(body: RecommendationRequestV3) -> None:
    """Refuse a division filter on a game version that carries no division label."""
    if getattr(body, "division", None) and body.game_version not in DIVISIONS_BY_GAME_VERSION:
        raise ServiceRefusal(
            "DIVISION_NOT_APPLICABLE",
            f"{body.game_version} data carries no division label; omit 'division'. "
            f"Divisions exist for: {sorted(DIVISIONS_BY_GAME_VERSION)}.")


class RecommendationServiceV3:
    def __init__(self, repository: CandidateRepository | None = None,
                 reference_version: str | None = None,
                 environment: Environment | None = None):
        self.repository = repository or CandidateRepository()
        # Explicit override (tooling/tests). None = resolve per request.
        self.reference_version = reference_version
        self._environment_override = environment

    def _resolve(self, body: RecommendationRequestV3):
        deployment = environment_from_settings(app_config.get_settings().environment)
        environment = (self._environment_override or deployment) if deployment == Environment.LOCAL else deployment
        research = body.include_research_data
        try:
            ref, research_pool = resolve_serving_reference(
                body.game_version, body.entity_scope, research, environment, self.reference_version)
        except ReferenceDistributionMismatch as exc:
            raise ServiceRefusal("REFERENCE_DISTRIBUTION_MISMATCH", str(exc)) from exc
        except ReferenceDistributionUnavailable as exc:
            refusal = ServiceRefusal("REFERENCE_DISTRIBUTION_UNAVAILABLE", str(exc))
            if not research and body.game_version == "FC27" and body.entity_scope == "game_player":
                refusal.requires = "include_research_data"
                refusal.detail += ". Set include_research_data=true in a non-production deployment."
            raise refusal from exc
        except ProductionOverrideForbidden as exc:
            raise ServiceRefusal("RESEARCH_DATA_REFUSED_IN_PRODUCTION", str(exc)) from exc
        except DataLicenseGateFailure as exc:
            raise ServiceRefusal("DATA_LICENSE_GATE_FAILED", str(exc)) from exc
        if environment != Environment.LOCAL or body.entity_scope == "ut_card":
            approved_environment = Environment.PRODUCTION if environment == Environment.LOCAL else environment
            dataset = catalogue_releases(approved_environment).get(body.game_version, {}).get(body.entity_scope)
            if dataset != ref.version:
                raise ServiceRefusal("DATA_LICENSE_GATE_FAILED", "No matching scoped release is authorized.")
        return ref, research_pool

    def _engine(self, body: RecommendationRequestV3, reference) -> RecommendationEngineV3:
        cfg = DEFAULT_V3_CONFIG
        if body.lam is not None:
            cfg = replace(DEFAULT_V3_CONFIG, lam_default=CalibratedValue(
                body.lam, CalibrationStatus.POLICY, "per-request override"))
        return RecommendationEngineV3(config=cfg, reference=reference,
                                      data_version=reference.version)

    def _pool(self, body: RecommendationRequestV3, research: bool) -> list[Candidate]:
        # Whole position family so the engine's own auditable G4 gate decides
        # adjacency (never a hidden SQL WHERE clause).
        group = position_group_for(body.position)
        family = POSITION_GROUPS.get(group, {body.position}) if group else {body.position}
        if body.entity_scope == "ut_card":
            return self.repository.load_cards(body.game_version, positions=family, use_player_links=False)
        return _division_filter(
            self.repository.load_candidates(body.game_version, positions=family,
                                            include_research_only=research), body)

    def run(self, body: RecommendationRequestV3, request_id: uuid.UUID | None = None):
        """Engine run shared by recommend/compare/what-if. -> (result, pool, ref, research)."""
        check_division(body)
        ref, research = self._resolve(body)
        pool = self._pool(body, research)
        req = _to_user_requirements(body)
        result = self._engine(body, ref).recommend(pool, req, request_id=request_id)
        return result, pool, ref, research

    # ------------------------------------------------------------------ recommend
    def recommend(self, body: RecommendationRequestV3,
                  request_id: uuid.UUID | None = None) -> dict:
        request_id = request_id or uuid.uuid4()
        started = time.monotonic()
        try:
            result, pool, ref, research = self.run(body, request_id=request_id)
        except ServiceRefusal as exc:
            self._emit_telemetry(request_id, body, started, failure_reason=exc.code)
            out = {"error": exc.code, "detail": exc.detail, "entity_scope": body.entity_scope,
                   "game_version": body.game_version}
            if exc.requires:
                out["requires"] = exc.requires
            return out
        except UnsupportedEntityScopeError as exc:
            self._emit_telemetry(request_id, body, started, failure_reason="UNSUPPORTED_ENTITY_SCOPE")
            return {"error": "UNSUPPORTED_ENTITY_SCOPE", "detail": str(exc)}
        except ValueError as exc:
            self._emit_telemetry(request_id, body, started, failure_reason="INVALID_REQUEST")
            return {"error": "INVALID_REQUEST", "detail": str(exc)}

        self._emit_telemetry(request_id, body, started, result=result,
                             candidate_count=len(pool), reference=ref)
        return self._serialise(result, body, pool, ref, research, request_id, started)

    # ------------------------------------------------------------------ compare
    def compare(self, body: RecommendationRequestV3, entity_ids: list[str],
                request_id: uuid.UUID | None = None) -> dict:
        """Same request, same demand vector, restricted to the chosen players.
        By INV-4 (pool independence) each player's score equals the score it
        gets in the full recommendation. Differentials come from
        explanation_service_v3.why_not over the two ScoringContexts."""
        wanted = [str(e) for e in entity_ids]
        try:
            check_division(body)
            ref, research = self._resolve(body)
        except ServiceRefusal as exc:
            return {"error": exc.code, "detail": exc.detail}
        wanted_set = set(wanted)
        pool = [c for c in self._pool(body, research) if str(c.entity_id) in wanted_set]
        found = {str(c.entity_id) for c in pool}
        req = _to_user_requirements(body.model_copy(update={"limit": 50}))
        try:
            result = self._engine(body, ref).recommend(pool, req)
        except ValueError as exc:
            return {"error": "INVALID_REQUEST", "detail": str(exc)}
        by_id = {str(c.entity_id): c for c in pool}
        ctxs = {str(rc.context.candidate_entity_id): rc.context for rc in result.ranked}
        order = [str(rc.context.candidate_entity_id) for rc in result.ranked]
        eps = DEFAULT_V3_CONFIG.tie_epsilon.value
        pairwise = []
        for i, a in enumerate(order):
            for b in order[i + 1:]:
                ca, cb = ctxs[a], ctxs[b]
                pairwise.append({
                    "higher": a, "lower": b,
                    "score_gap": round(ca.r - cb.r, 6),
                    "within_noise_threshold": ca.r - cb.r < eps,
                    "intervals_overlap": _overlap(ca, cb),
                    "decision_evidence": evidence_gap(ca, cb, eps),
                    "why": list(why_not(ca, cb, top_n=4)),
                })
        players = [self._entry(rc, by_id, body, 3) for rc in result.ranked]
        for i in range(len(players) - 1):  # same near-tie semantics as /recommendations
            nt = near_tie_block(result.ranked[i].context, result.ranked[i + 1].context, eps)
            if nt:
                players[i]["near_tie_with_next"] = nt
        return {
            "request_id": str(request_id or uuid.uuid4()),
            "request": _request_echo(body),
            "dataset": _dataset_block(ref, research),
            "players": players,
            "excluded": [{"entity_id": str(e.candidate_entity_id), "name": e.candidate_name,
                          "gate": e.gate, "class": e.exclusion_class.value, "reason": e.reason}
                         for e in list(result.excluded) + list(result.not_evaluable)],
            "not_found": [e for e in wanted if e not in found],
            "pairwise": pairwise,
            "note": ("Comparison is for THIS request only (position, tactic, preferences). "
                     "Scores come from the same deterministic engine run as recommendations."),
        }

    # ------------------------------------------------------------------ what-if
    def what_if(self, base: RecommendationRequestV3,
                variants: list[tuple[str, dict]], track_top: int = 10,
                request_id: uuid.UUID | None = None) -> dict:
        """Recompute the engine for each variant request and report rank /
        score deltas of the base top-N. Every number is a fresh engine run --
        nothing is adjusted by hand."""
        request_id = request_id or uuid.uuid4()
        try:
            base_result, base_pool, ref, research = self.run(base.model_copy(update={"limit": WHAT_IF_DEPTH}), request_id=request_id)
        except ServiceRefusal as exc:
            return {"error": exc.code, "detail": exc.detail}
        except ValueError as exc:
            return {"error": "INVALID_REQUEST", "detail": str(exc)}
        base_top = [rc.context for rc in base_result.ranked[:track_top]]
        base_rank = {str(c.candidate_entity_id): i + 1 for i, c in enumerate(base_top)}
        out_variants = []
        for label, changes in variants:
            vbody = base.model_copy(update={**changes, "limit": WHAT_IF_DEPTH})
            child_id = uuid.uuid4()
            ids = {"parent_request_id": str(request_id), "request_id": str(child_id)}
            try:
                vres, variant_pool, _, _ = self.run(vbody, request_id=child_id)
            except ServiceRefusal as exc:
                out_variants.append({**ids, "label": label, "changes": changes, "error": exc.code,
                                     "detail": exc.detail})
                continue
            except ValueError as exc:
                out_variants.append({**ids, "label": label, "changes": changes,
                                     "error": "INVALID_REQUEST", "detail": str(exc)})
                continue
            full = {str(rc.context.candidate_entity_id): (rc.rank, rc.context)
                    for rc in vres.ranked}
            tracked = []
            for c in base_top:
                eid = str(c.candidate_entity_id)
                new = full.get(eid)
                tracked.append({
                    "entity_id": eid, "name": c.candidate_name,
                    "base_rank": base_rank[eid], "base_score": c.r,
                    "new_rank": new[0] if new else None,
                    "new_score": new[1].r if new else None,
                    "score_delta": round(new[1].r - c.r, 6) if new else None,
                })
            out_variants.append({
                **ids, "label": label, "changes": changes,
                "candidate_count": len(variant_pool),
                "top": [{"rank": rc.rank, "entity_id": str(rc.context.candidate_entity_id),
                         "name": rc.context.candidate_name, "score": rc.context.r}
                        for rc in vres.ranked[:track_top]],
                "entered_top": [rc.context.candidate_name for rc in vres.ranked[:track_top]
                                if str(rc.context.candidate_entity_id) not in base_rank],
                "tracked_from_base": tracked,
                "leading_pair": leading_pair(vres.ranked, DEFAULT_V3_CONFIG.tie_epsilon.value),
                "demand_shift": _demand_shift(base_result.demand.vector, vres.demand.vector),
            })
        return {"request_id": str(request_id), "candidate_count": len(base_pool),
                "request": _request_echo(base), "dataset": _dataset_block(ref, research),
                "base_top": [{"rank": i + 1, "entity_id": str(c.candidate_entity_id),
                              "name": c.candidate_name, "score": c.r}
                             for i, c in enumerate(base_top)],
                "variants": out_variants, "ranking_depth": WHAT_IF_DEPTH,
                "note": ("new_rank is null only when the player is excluded by a gate or ranked "
                         f"beyond depth {WHAT_IF_DEPTH} -- not 'unranked'.")}

    # ------------------------------------------------------------------ diagnostics
    def _emit_telemetry(self, request_id: uuid.UUID, body: RecommendationRequestV3,
                        started: float, result=None, candidate_count: int = 0,
                        failure_reason: str | None = None, reference=None) -> None:
        """One record per request. No raw user data, no attribute values."""
        record = {
            "request_id": str(request_id),
            "engine_version": getattr(result, "engine_version", ENGINE_VERSION),
            "config_version": getattr(result, "config_version", None),
            "game_version": body.game_version,
            "dataset_version": getattr(reference, "version", None),
            "data_status": ((reference.data_status or "CANONICAL") if reference else None),
            "entity_scope": body.entity_scope,
            "position": body.position,
            "tactical_profile": body.tactical_profile,
            "candidate_count": candidate_count,
            "eligible_count": (len(result.ranked) + len(result.not_evaluable)) if result else 0,
            "excluded_count": len(result.excluded) if result else 0,
            "not_evaluable_count": len(result.not_evaluable) if result else 0,
            "result_count": len(result.ranked) if result else 0,
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
            "failure_reason": failure_reason,
        }
        telemetry_log.info("v3_recommendation_request", extra={"telemetry": record})

    def explain_exclusion(self, body: RecommendationRequestV3, entity_id: str) -> dict:
        result_dict = self.recommend(body)
        if "error" in result_dict:
            return result_dict
        for bucket in ("excluded", "not_evaluable"):
            for row in result_dict[bucket]:
                if row["entity_id"] == entity_id:
                    return {"status": bucket.upper(), **row}
        for row in result_dict["ranked"]:
            if row["entity_id"] == entity_id:
                return {"status": "RANKED", "rank": row["rank"], "score": row["score"]}
        return {"status": "NOT_IN_POOL", "entity_id": entity_id}

    def explain_ranking_gap(self, body: RecommendationRequestV3,
                            entity_id_a: str, entity_id_b: str) -> dict:
        try:
            result, _, _, _ = self.run(body)
        except ServiceRefusal as exc:
            return {"error": exc.code, "detail": exc.detail}
        ctxs = {str(rc.context.candidate_entity_id): rc.context for rc in result.ranked}
        if entity_id_a not in ctxs or entity_id_b not in ctxs:
            return {"status": "ONE_OR_BOTH_NOT_RANKED"}
        return {"status": "OK", "differential": list(why_not(ctxs[entity_id_a], ctxs[entity_id_b]))}

    # ------------------------------------------------------------------ serialise
    def _entry(self, rc, by_id: dict, body: RecommendationRequestV3, top_n: int) -> dict:
        ctx = rc.context
        exp = explain(ctx, top_n=top_n)
        cand = by_id.get(str(ctx.candidate_entity_id))
        covered = sorted((a for a in ctx.per_attribute if a.covered),
                         key=lambda a: -a.contribution_lo)
        n = max(top_n, 3)
        strengths = [_attr_row(a) for a in covered[:n]]
        # Weaknesses: demanded (weight >= 2%) attributes whose saturated value
        # is below 0.75 -- the same threshold the explanation service uses.
        weak = [a for a in sorted(covered, key=lambda a: a.s_eff or 0.0)
                if a.s_eff is not None and a.s_eff < 0.75 and a.weight >= 0.02][:n]
        ps_mod = next((m for m in ctx.modifiers if m.name == "playstyle"), None)
        return {
            "rank": rc.rank,
            "entity_id": str(ctx.candidate_entity_id),
            "entity_type": ctx.entity_type,
            "name": ctx.candidate_name,
            "score": ctx.r,
            "score_upper_bound": ctx.r_hi,
            "score_interval": {"low": ctx.r, "high": ctx.r_hi,
                               "ranked_on": "low (C_lo x modifier)"},
            "coverage": ctx.coverage_kappa,
            "confidence_note": ("high coverage" if ctx.coverage_kappa >= 0.9
                                else "partial coverage -- see score_upper_bound"),
            "confidence": confidence_block(ctx),
            "position_eligibility": (ctx.eligibility.position_eligibility
                                     if ctx.eligibility else None),
            "playstyle_contribution": round(ps_mod.capped, 6) if ps_mod else None,
            "key_strengths": strengths,
            "key_weaknesses": [_attr_row(a) for a in weak],
            "tactical_fit": tactical_fit_block(ctx),
            "evidence": evidence_block(ctx, cand),
            "explanation": {
                "reasons": list(exp.reasons),
                "trade_offs": list(exp.trade_offs),
                "unknowns": list(exp.unknowns),
                "reconstructed_score_matches_ranking": exp.matches_ranking_score,
            },
            **({"card": {"id": str(cand.entity_id), "name": cand.name, "position": cand.position_primary,
                         "overall_rating": cand.overall_rating, "data_status": cand.data_status.value}}
               if cand and body.entity_scope == "ut_card" else {"player": _player_block(cand) if cand else None}),
            "scoring_context": ctx.to_dict() if body.provenance_detail == "full" else {
                "demand_vector": ctx.demand_vector,
                "coverage_kappa": ctx.coverage_kappa,
                "missing_attributes": list(ctx.missing_attributes),
                "c_lo": ctx.c_lo, "c_hi": ctx.c_hi,
                "modifier_total": ctx.modifier_total,
            },
        }

    def _serialise(self, result, body: RecommendationRequestV3, pool: list[Candidate],
                   ref, research: bool, request_id: uuid.UUID, started: float) -> dict:
        by_id = {str(c.entity_id): c for c in pool}
        ranked = [self._entry(rc, by_id, body, body.explain_top_n) for rc in result.ranked]
        # Near ties: expose closeness honestly instead of implying a clear order.
        eps = DEFAULT_V3_CONFIG.tie_epsilon.value
        for i in range(len(result.ranked) - 1):
            nt = near_tie_block(result.ranked[i].context, result.ranked[i + 1].context, eps)
            if nt:
                ranked[i]["near_tie_with_next"] = nt
        excluded = [
            {"entity_id": str(e.candidate_entity_id), "name": e.candidate_name,
             "gate": e.gate, "class": e.exclusion_class.value, "reason": e.reason}
            for e in result.excluded
        ]
        not_evaluable = [
            {"entity_id": str(e.candidate_entity_id), "name": e.candidate_name,
             "reason": e.reason}
            for e in result.not_evaluable
        ]
        return {
            "request_id": str(request_id),
            "request": _request_echo(body),
            "entity_scope": result.entity_scope,
            "engine": {"engine_version": result.engine_version,
                       "config_version": result.config_version,
                       "lambda": result.demand.lam},
            "engine_version": result.engine_version,
            "config_version": result.config_version,
            "dataset": _dataset_block(ref, research),
            "data_version": ref.version,
            "reference_distribution_version": result.reference_distribution_version,
            "reference_distribution_universe": result.reference_distribution_universe,
            "demand_vector": dict(result.demand.vector),
            "tactical_demand_neutral": result.demand.tactical_demand_neutral,
            "leading_pair": leading_pair(result.ranked, eps),
            "counts": {"candidates": len(pool), "ranked_returned": len(ranked),
                       "excluded": len(excluded), "not_evaluable": len(not_evaluable)},
            "division": division_block(body.division, pool,
                                       applicable=body.game_version in DIVISIONS_BY_GAME_VERSION),
            "ranked": ranked,
            "excluded": excluded,
            "not_evaluable": not_evaluable,
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
            "provenance_summary": {
                "reference_distribution": {
                    "version": result.reference_distribution_version,
                    "universe": result.reference_distribution_universe,
                    "note": ("This distribution describes Ultimate Team card items for this game version."
                             if result.entity_scope == "ut_card" else
                             "This distribution describes ratings-site players for this game version."),
                },
            },
        }


# ---------------------------------------------------------------------- helpers
def _division_filter(pool: list[Candidate], body: RecommendationRequestV3) -> list[Candidate]:
    """User-chosen division filter applied BEFORE scoring. Scores do not
    depend on the pool (INV-4), so filtering changes membership, never a
    player's score. A candidate whose division is unknown is kept out only
    when a division was requested (it cannot be shown to match)."""
    division = getattr(body, "division", None)
    if not division:
        return pool
    return [c for c in pool if c.extra.get("division") == division]


def _request_echo(body: RecommendationRequestV3) -> dict:
    return {"game_version": body.game_version, "position": body.position,
            **({"formation": body.formation, "slot": body.slot} if body.formation else {}),
            "tactical_profile": body.tactical_profile,
            "secondary_tactical_profile": body.secondary_tactical_profile,
            "limit": body.limit, "lam": body.lam,
            "division": getattr(body, "division", None),
            "include_research_data": bool(getattr(body, "include_research_data", False)),
            **{key: value for key, value in body.model_dump(include={
                "attribute_preferences", "desired_playstyles", "desired_playstyles_plus", "required_playstyles",
                "required_league", "required_club", "required_nation"
            }).items() if value}}


def _dataset_block(ref, research: bool) -> dict:
    return {"game_version": ref.game_version, "data_status": ref.data_status or "CANONICAL",
            "research_only": research,
            "reference_distribution": {"version": ref.version, "universe": ref.universe,
                                       "content_hash": ref.content_hash},
            "notice": ("RESEARCH_ONLY: non-commercial research snapshot; not production data"
                       if research else None)}


def _player_block(c: Candidate) -> dict:
    """Only facts the source published; UNKNOWN stays null."""
    return {
        "overall_rating": c.overall_rating,
        "overall_rating_note": "EA OVR as published -- not an input to the intelligence score",
        "position_primary": c.position_primary,
        "secondary_positions": list(c.secondary_positions),
        "nation": c.nation, "club": c.club, "league": c.league,
        "division": c.extra.get("division"),
        "preferred_foot": c.extra.get("preferred_foot"),
        "weak_foot_stars": c.extra.get("weak_foot_stars"),
        "skill_moves_stars": c.extra.get("skill_moves_stars"),
        "face_stats": {a: c.attributes.get(a) for a in FACADE_ATTRS},
        "playstyles": {"published": c.playstyle_data_published,
                       "base": list(c.playstyles_base) if c.playstyle_data_published else None,
                       "plus": list(c.playstyles_plus) if c.playstyle_data_published else None},
        "data_status": c.data_status.value,
    }


def _demand_shift(before: dict[str, float], after: dict[str, float], top: int = 6) -> list[dict]:
    keys = set(before) | set(after)
    deltas = sorted(((k, after.get(k, 0.0) - before.get(k, 0.0)) for k in keys),
                    key=lambda t: -abs(t[1]))
    return [{"attribute": k, "weight_delta": round(d, 6)} for k, d in deltas[:top] if abs(d) > 1e-9]
