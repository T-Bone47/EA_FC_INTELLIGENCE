"""RECOMMENDATION ENGINE V2 (v2.1 intelligence upgrade) — deterministic,
configurable, explainable, evidence-aware. This is the single engine; there is
deliberately no v3/final/new variant (§44 of the build mandate).

Baseline contract (UNCHANGED for legacy requests — protected by golden
scenarios in benchmarks/engine_baseline_v2_2026-09-14.json):
  * Components: overall_quality, position_fit, attribute_fit, tactical_fit,
    playstyle_fit, role_fit (advisory), team_fit.
  * FitValue statuses: KNOWN / UNKNOWN / INSUFFICIENT_EVIDENCE.
  * Unknown component weight is redistributed proportionally across KNOWN
    components — players are never penalized for missing data.
  * Tactical alignment floor: in strict mode candidates below the floor are
    excluded from best_overall; otherwise they are down-ranked and flagged.
  * Pareto alternatives expose tradeoffs instead of one opaque score.
  * Ranking is fully deterministic: (-score, -OVR, name, entity_id).
  * The engine is version-aware: game_version flows through VersionConfig;
    FC26 and FC27 never share records or configuration.

v2.1 intelligence layers (ACTIVE ONLY when the request carries the new
explicit inputs — legacy request shapes score bit-identically):
  * archetype_fit component (requested archetype; weight ARCHETYPE_WEIGHT,
    base table renormalized) — §15, archetypes are COMPUTED, never assigned;
  * slot-aware + tactical-combination attribute importance — §5/§6/§7/§8;
  * attribute interactions and saturation — §9/§10 (opt-in flags);
  * qualitative bands as soft targets — §11;
  * contextual PlayStyle value — §12/§13 (opt-in flag);
  * hard constraints: mandatory PlayStyles, league/club/nation — §2;
  * OVR-stance bias (explicit deprioritization) — §72/§74;
  * squad structural fit (ADVISORY; chemistry stays UNKNOWN) — §18/§19;
  * replacement verdicts UPGRADE/SIDEGRADE/DOWNGRADE — §20;
  * score bands, sensitivity, counterfactuals — §23/§37/§38;
  * engine_version + effective component weights per evaluation — §60.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

from backend.domain.card_model import Candidate, DataStatus
from backend.domain.user_model import SquadContext, UserRequirements
from backend.services import archetypes as archetypes_mod
from backend.services import attribute_model, counterfactual, formations
from backend.services import fit_components as fc
from backend.services import playstyle_context, recommendation_confidence
from backend.services import squad_intelligence
from backend.services.confidence_service import entity_data_confidence
from backend.services import engine_config
from backend.services.engine_config import (
    DIVERSITY_SCAN_TOP_N, ENGINE_VERSION, OVERALL_BIAS_FACTORS, SCORE_BANDS,
)
from backend.services.fit_value import FitStatus, FitValue
from backend.services.role_fit_service import RoleFitService
from backend.services.scoring_config import ScoringConfig

# how many ranked rows receive the derived-intelligence enrichment block
ENRICHMENT_TOP_N = 25


def score_band(weighted: Optional[float],
               evidence_coverage: Optional[float] = None) -> Optional[dict]:
    """§23 — interpretable band for a fit score. NOT a probability.

    §51 honesty gate: when the score rests on less than MIN_BAND_EVIDENCE of
    total component weight, no qualitative band is claimed — the label becomes
    INSUFFICIENT_EVIDENCE. The numeric score itself is untouched (legacy
    contract: UNKNOWN components never lower scores)."""
    if weighted is None:
        return None
    if (evidence_coverage is not None
            and evidence_coverage < engine_config.MIN_BAND_EVIDENCE):
        return {
            "band": "INSUFFICIENT_EVIDENCE",
            "meaning": ("score rests on only "
                        f"{evidence_coverage:.0%} of component weight — too thin "
                        "for a qualitative fit claim"),
            "evidence_coverage": round(evidence_coverage, 3),
            "note": "missing data is neither bad nor equally certain (§51)"}
    band = None
    for threshold, name, meaning in SCORE_BANDS:
        if weighted >= threshold:
            band = {"band": name, "meaning": meaning}
            break
    if band is None:
        band = {"band": SCORE_BANDS[-1][1], "meaning": SCORE_BANDS[-1][2]}
    band["note"] = "engine suitability score — not a probability"
    if evidence_coverage is not None:
        band["evidence_coverage"] = round(evidence_coverage, 3)
    return band


@dataclass
class CandidateEvaluation:
    candidate: Candidate
    components: dict[str, FitValue]
    weighted_score: Optional[float]          # None when nothing is KNOWN
    confidence: recommendation_confidence.RecommendationConfidence
    hard_constraint_violation: Optional[str] = None
    below_tactical_floor: bool = False
    budget_decision: Optional[bool] = None   # None = UNKNOWN
    budget_quote: Optional[dict] = None
    # ---- v2.1 additive ----
    component_weights: dict[str, float] = field(default_factory=dict)  # effective, redistributed
    evidence_coverage: float = 1.0       # share of total component weight that was KNOWN
    score_band: Optional[dict] = None
    intelligence: Optional[dict] = None      # top-N derived analytics (ENGINE-DERIVED)
    squad_structural: Optional[FitValue] = None   # advisory, squad context only
    constraints: Optional[dict] = None       # satisfied/failed/unknown report

    @property
    def rankable(self) -> bool:
        return (self.hard_constraint_violation is None
                and self.weighted_score is not None)

    @property
    def insufficient_evidence(self) -> bool:
        """§51 v2.1: score rests on less than MIN_BAND_EVIDENCE of component
        weight. The score itself is untouched (UNKNOWN never lowers scores —
        legacy contract), but the candidate is down-ranked below well-evidenced
        ones and never receives a qualitative fit band."""
        return (self.weighted_score is not None
                and self.evidence_coverage < engine_config.MIN_BAND_EVIDENCE)

    def to_dict(self) -> dict:
        d = {
            "entity_type": self.candidate.entity_type,
            "entity_id": str(self.candidate.entity_id),
            "name": self.candidate.name,
            "components": {k: v.to_dict() for k, v in self.components.items()},
            "weighted_score": round(self.weighted_score, 5) if self.weighted_score is not None else None,
            "confidence": self.confidence.to_dict(),
            "hard_constraint_violation": self.hard_constraint_violation,
            "below_tactical_floor": self.below_tactical_floor,
            "budget": {"decision": self.budget_decision, "quote": self.budget_quote},
            "score_band": self.score_band,
            "evidence_coverage": round(self.evidence_coverage, 3),
        }
        if self.intelligence is not None:
            d["intelligence"] = self.intelligence
        if self.squad_structural is not None:
            d["squad_structural_fit"] = self.squad_structural.to_dict()
        if self.constraints is not None:
            d["constraints"] = self.constraints
        return d


@dataclass
class RecommendationResult:
    request_id: str
    game_version: str
    best: Optional[Candidate]
    best_evaluation: Optional[CandidateEvaluation]
    best_score: float
    confidence: recommendation_confidence.RecommendationConfidence
    ranked: list[CandidateEvaluation]
    pareto: dict[str, Optional[dict]]
    excluded_hard: list[dict]
    excluded_by_floor: list[dict]
    budget_status: str
    weights_used: dict[str, float]
    evaluations_total: int
    # ---- v2.1 additive (§54/§60) ----
    engine_version: str = ENGINE_VERSION
    sensitivity: Optional[dict] = None
    counterfactuals: Optional[list] = None
    replacement_analysis: Optional[list] = None
    constraints: Optional[dict] = None
    telemetry: Optional[dict] = None
    confidence_v2: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "game_version": self.game_version,
            "engine_version": self.engine_version,
            "best": self.best_evaluation.to_dict() if self.best_evaluation else None,
            "best_score": round(self.best_score, 5),
            "confidence": self.confidence.to_dict(),
            "confidence_v2": self.confidence_v2,
            "ranked": [e.to_dict() for e in self.ranked],
            "pareto": self.pareto,
            "excluded_hard": self.excluded_hard,
            "excluded_by_floor": self.excluded_by_floor,
            "budget_status": self.budget_status,
            "weights_used": self.weights_used,
            "evaluations_total": self.evaluations_total,
            "sensitivity": self.sensitivity,
            "counterfactuals": self.counterfactuals,
            "replacement_analysis": self.replacement_analysis,
            "constraints": self.constraints,
            "telemetry": self.telemetry,
        }


class RecommendationEngineV2:
    def __init__(self, config: Optional[ScoringConfig] = None,
                 role_service: Optional[RoleFitService] = None,
                 budget_provider=None):
        self.config = config or ScoringConfig()
        self.role_service = role_service or RoleFitService(self.config)
        self.budget_provider = budget_provider
        if self.budget_provider is None:
            from backend.services.budget_provider import NullBudgetProvider
            self.budget_provider = NullBudgetProvider()
        self.engine_version = ENGINE_VERSION

    # ------------------------------------------------------------------ weights
    def effective_weights(self, req: UserRequirements) -> dict[str, float]:
        """Request-effective weight table. Legacy requests -> the baseline
        table unchanged. Archetype requests add archetype_fit and renormalize;
        explicit OVR-stance bias scales overall_quality (§72/§74)."""
        w = dict(self.config.component_weights)
        bias = (req.overall_quality_bias or "normal").lower()
        factor = OVERALL_BIAS_FACTORS.get(bias, 1.0)
        if factor != 1.0:
            w["overall_quality"] = w["overall_quality"] * factor
            total = sum(w.values())
            w = {k: v / total for k, v in w.items()}
        if req.archetype:
            base_share = 1.0 - archetypes_mod.ARCHETYPE_WEIGHT
            w = {k: v * base_share for k, v in w.items()}
            w["archetype_fit"] = archetypes_mod.ARCHETYPE_WEIGHT
        return w

    def _context(self, req: UserRequirements):
        """Resolved formation slot + merged tactical dimensions (None-safe)."""
        slot = formations.find_slot(req.formation, req.slot) if req.slot else None
        dims = None
        if req.secondary_tactical_profile:
            dims = formations.dimension_vector(req.tactical_profile,
                                               req.secondary_tactical_profile)
        return slot, dims

    def _uses_intelligence_attrs(self, req) -> bool:
        return bool(req.attribute_bands or req.slot or req.secondary_tactical_profile
                    or req.enable_interactions or req.enable_saturation)

    # ------------------------------------------------------------------ evaluate
    def evaluate(self, candidate: Candidate, req: UserRequirements,
                 squad_ctx: Optional[SquadContext] = None,
                 _eff: Optional[dict[str, float]] = None,
                 _ctx: Optional[tuple] = None) -> CandidateEvaluation:
        """Evaluate one candidate. `_eff`/`_ctx` are internal pre-computation
        hooks so recommend() can hoist per-request work out of the per-candidate
        loop (§57); external callers should never pass them."""
        self._guard_version(candidate, req)
        if candidate.is_synthetic or candidate.data_status == DataStatus.SYNTHETIC_TEST:
            raise ValueError(
                "SYNTHETIC_TEST candidate reached the production engine. "
                "This is a data-boundary violation (§13) — aborting rather than scoring.")

        eff = _eff if _eff is not None else self.effective_weights(req)
        slot, dims = _ctx if _ctx is not None else self._context(req)

        components: dict[str, FitValue] = {
            "overall_quality": fc.overall_quality(candidate),
            "position_fit": fc.position_fit(candidate, req, self.config),
            "attribute_fit": (
                attribute_model.intelligence_attribute_fit(candidate, req, self.config,
                                                           slot=slot, dims=dims)
                if self._uses_intelligence_attrs(req)
                else fc.attribute_fit(candidate, req, self.config)),
            "tactical_fit": self._tactical_fit(candidate, req, dims),
            "playstyle_fit": (
                playstyle_context.contextual_playstyle_fit(candidate, req)
                if req.enable_playstyle_context
                else fc.playstyle_fit(candidate, req, self.config)),
            "role_fit": fc.role_fit(candidate, req, self.role_service),
            "team_fit": fc.team_fit(candidate, req, squad_ctx, self.config),
        }
        if req.archetype:
            components["archetype_fit"] = archetypes_mod.archetype_score(
                candidate, req.archetype)

        # hard constraints (deterministic, checked before scoring)
        violation = self._hard_constraints(candidate, req)

        # budget via provider (UNKNOWN stays UNKNOWN)
        from backend.services.budget_provider import within_budget
        decision, quote = within_budget(candidate, self.budget_provider, req.budget_coins)
        if req.budget_coins is not None and decision is False:
            violation = violation or (
                f"price {quote.price_coins} exceeds budget {req.budget_coins}")

        weighted = self._weighted_score(components, eff)

        relevant = list(self.config.position_attribute_weights(
            (req.position or candidate.position_primary or "").upper()))
        data_conf = entity_data_confidence(
            candidate, relevant, price_relevant=req.budget_coins is not None)
        confidence = recommendation_confidence.compute(components, data_conf, weights=eff)

        below_floor = False
        tf = components["tactical_fit"]
        if tf.status == FitStatus.KNOWN and tf.value < self.config.tactical_floor:
            below_floor = True

        # effective redistributed weights (for sensitivity analysis)
        known_w = sum(eff[n] for n in eff if components.get(n) is not None
                      and components[n].status == FitStatus.KNOWN)
        cw = {n: (eff[n] / known_w if known_w > 0 and components.get(n) is not None
                  and components[n].status == FitStatus.KNOWN else 0.0)
              for n in eff}

        return CandidateEvaluation(
            candidate=candidate, components=components, weighted_score=weighted,
            confidence=confidence, hard_constraint_violation=violation,
            below_tactical_floor=below_floor, budget_decision=decision,
            budget_quote={"price_coins": quote.price_coins, "platform": quote.platform,
                          "observed_at": quote.observed_at, "source_id": quote.source_id}
                          if quote is not None else None,
            component_weights=cw,
            evidence_coverage=known_w,
            score_band=score_band(weighted, known_w),
        )

    def _tactical_fit(self, candidate: Candidate, req: UserRequirements,
                      dims: Optional[dict[str, float]]) -> FitValue:
        """Legacy single-profile path OR combination path (§7) when a secondary
        profile is set: demand weights derived from merged tactical dimensions."""
        if dims is None:
            return fc.tactical_fit(candidate, req, self.config)
        # Use GK-specific dimension affinities for GK candidates with combination tactics
        is_gk = (candidate.position_primary or "").strip().upper() == "GK"
        if is_gk:
            from backend.services.formations import GK_DIMENSION_ATTRIBUTE_AFFINITY
            weights = {}
            for dim, value in dims.items():
                demand = abs(value - 0.5) * 2.0
                if demand < 1e-9:
                    continue
                for attr, aff in GK_DIMENSION_ATTRIBUTE_AFFINITY.get(dim, {}).items():
                    weights[attr] = weights.get(attr, 0.0) + aff * demand
            total = sum(weights.values())
            if total > 0:
                weights = {k: v / total for k, v in weights.items()}
            else:
                weights = {}
        else:
            weights = formations.tactical_weights_from_dimensions(dims)
        if not weights:
            return FitValue.unknown(
                "tactical combination produced no attribute demand (all dimensions neutral)")
        from backend.services.scoring_config import ATTRIBUTE_EVIDENCE_MIN_COVERAGE
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
        combo = f"{req.tactical_profile}+{req.secondary_tactical_profile}"
        if scored_w <= 0:
            return FitValue.insufficient(
                f"no attributes required by {combo} are published for this candidate")
        if scored_w < ATTRIBUTE_EVIDENCE_MIN_COVERAGE:
            return FitValue.insufficient(
                f"only {scored_w:.0%} of {combo} dimension-derived attribute weight "
                f"is published (missing: {', '.join(sorted(missing)[:6])})",
                evidence=tuple(detail[:8]))
        # Calculate coverage for combination tactics
        from backend.services.formations import GK_DIMENSION_ATTRIBUTE_AFFINITY
        total_affinity = 0.0
        for dim in dims:
            if is_gk:
                for aff in GK_DIMENSION_ATTRIBUTE_AFFINITY.get(dim, {}).values():
                    total_affinity += abs(aff)
            else:
                from backend.services.formations import DIMENSION_ATTRIBUTE_AFFINITY
                for aff in DIMENSION_ATTRIBUTE_AFFINITY.get(dim, {}).values():
                    total_affinity += abs(aff)
        # Coverage is scored_w / total_possible_weight (simplified)
        coverage_pct = (scored_w / len(weights) * 100) if weights else 0
        ev = [f"combined profile {combo} (dimension-merged demand)",
              f"coverage {coverage_pct:.0f}%"] + detail[:8]
        if is_gk:
            ev.append("(GK-specific dimension affinities applied)")
        return FitValue.known(acc / scored_w, evidence=tuple(ev))

    def _guard_version(self, candidate: Candidate, req: UserRequirements) -> None:
        if candidate.game_version.value != str(req.game_version).upper():
            raise ValueError(
                f"version mismatch: candidate is {candidate.game_version.value} but "
                f"request is {req.game_version}. FC26/FC27 records are never mixed (§3).")

    def _hard_constraints(self, c: Candidate, req: UserRequirements) -> Optional[str]:
        if req.min_overall is not None and c.overall_rating is not None \
                and c.overall_rating < req.min_overall:
            return f"OVR {c.overall_rating} below min_overall {req.min_overall}"
        if req.max_overall is not None and c.overall_rating is not None \
                and c.overall_rating > req.max_overall:
            return f"OVR {c.overall_rating} above max_overall {req.max_overall}"
        for p in req.attribute_preferences:
            if p.min_value is not None:
                v = c.attributes.get(p.attribute)
                if v is not None and v < p.min_value:
                    return (f"{p.attribute} {v} below required minimum {p.min_value}")
                # v is None -> UNKNOWN: not a violation (§19), lowers coverage instead
        # ---- v2.1 hard constraints (§2) ----
        for ps in req.required_playstyles:
            if not c.playstyle_data_published:
                return (f"mandatory PlayStyle {ps!r} cannot be verified — PlayStyles "
                        "unpublished for this candidate (excluded honestly, not assumed absent)")
            have = {p.strip() for p in (c.playstyles_base + c.playstyles_plus)}
            if ps.strip() not in have:
                return f"mandatory PlayStyle {ps!r} not held"
        for kind, required, actual in (("league", req.required_league, c.league),
                                       ("club", req.required_club, c.club),
                                       ("nation", req.required_nation, c.nation)):
            if required is None:
                continue
            if actual is None:
                return f"required {kind} {required!r} cannot be verified — {kind} UNKNOWN"
            if str(actual).strip().lower() != str(required).strip().lower():
                return f"{kind} {actual!r} does not match required {required!r}"
        return None

    def _weighted_score(self, components: dict[str, FitValue],
                        weights: Optional[dict[str, float]] = None) -> Optional[float]:
        """Redistribute unknown-component weight across KNOWN components."""
        w_table = weights if weights is not None else self.config.component_weights
        known_w = sum(w_table[n] for n in w_table
                      if components.get(n) is not None
                      and components[n].status == FitStatus.KNOWN)
        if known_w <= 0:
            return None
        score = 0.0
        for n, w in w_table.items():
            fv = components.get(n)
            if fv is not None and fv.status == FitStatus.KNOWN:
                score += (w / known_w) * fv.value
        return score

    # ------------------------------------------------------------------ constraints report
    @staticmethod
    def constraint_report(e: CandidateEvaluation, req: UserRequirements) -> dict:
        """§54 constraints_satisfied / constraints_failed / unknown_factors."""
        satisfied: list[str] = []
        failed: list[str] = []
        unknown: list[str] = []
        c = e.candidate
        satisfied.append(f"game_version {c.game_version.value} matches the request")
        pf = e.components.get("position_fit")
        if req.position and pf is not None and pf.status == FitStatus.KNOWN:
            satisfied.append(f"position: {pf.evidence[0] if pf.evidence else 'evaluated'}")
        for p in req.attribute_preferences:
            if p.min_value is None:
                continue
            v = c.attributes.get(p.attribute)
            if v is None:
                unknown.append(f"{p.attribute} minimum {p.min_value}: value UNKNOWN")
            elif v >= p.min_value:
                satisfied.append(f"{p.attribute} {v} ≥ required {p.min_value}")
            else:
                failed.append(f"{p.attribute} {v} < required {p.min_value}")
        from backend.services.engine_config import QUALITY_BANDS
        for b in req.attribute_bands or []:
            v = c.attributes.get(b.attribute)
            target = QUALITY_BANDS.get(b.band)
            if v is None or target is None:
                unknown.append(f"{b.attribute} band {b.band}: value UNKNOWN")
            elif v >= target:
                satisfied.append(f"{b.attribute} {v} meets '{b.band}' target {target} (soft)")
            else:
                failed.append(f"{b.attribute} {v} below '{b.band}' target {target} (soft preference, not exclusion)")
        for ps in req.required_playstyles:
            if not c.playstyle_data_published:
                unknown.append(f"mandatory PlayStyle {ps}: data unpublished")
            elif ps in {p.strip() for p in (c.playstyles_base + c.playstyles_plus)}:
                satisfied.append(f"mandatory PlayStyle {ps} held")
            else:
                failed.append(f"mandatory PlayStyle {ps} not held")
        for kind, required, actual in (("league", req.required_league, c.league),
                                       ("club", req.required_club, c.club),
                                       ("nation", req.required_nation, c.nation)):
            if required is None:
                continue
            if actual is None:
                unknown.append(f"required {kind} {required}: UNKNOWN")
            elif str(actual).lower() == str(required).lower():
                satisfied.append(f"{kind} {actual} matches requirement")
            else:
                failed.append(f"{kind} {actual} ≠ required {required}")
        if req.budget_coins is not None:
            if e.budget_decision is None:
                unknown.append(f"budget {req.budget_coins}: price UNKNOWN — BUDGET_UNVERIFIED")
            elif e.budget_decision:
                satisfied.append(f"price within budget {req.budget_coins}")
            else:
                failed.append(f"price exceeds budget {req.budget_coins}")
        if e.hard_constraint_violation:
            failed.append(e.hard_constraint_violation)
        return {"satisfied": satisfied, "failed": failed, "unknown": unknown}

    # ------------------------------------------------------------------ recommend
    def recommend(self, candidates: list[Candidate], req: UserRequirements,
                  squad_ctx: Optional[SquadContext] = None,
                  request_id: Optional[str] = None,
                  squad_members: Optional[list[Candidate]] = None,
                  replacement_current: Optional[Candidate] = None) -> RecommendationResult:
        problems = req.validate()
        if problems:
            raise ValueError("invalid requirements: " + "; ".join(problems))

        eff = self.effective_weights(req)
        ctx = self._context(req)          # hoisted: computed once per request (§57)
        evaluations = [self.evaluate(c, req, squad_ctx, _eff=eff, _ctx=ctx)
                       for c in candidates]

        excluded_hard = [
            {"entity_id": str(e.candidate.entity_id), "name": e.candidate.name,
             "reason": e.hard_constraint_violation}
            for e in evaluations if e.hard_constraint_violation]

        rankable = [e for e in evaluations if e.rankable]

        excluded_floor: list[dict] = []
        if req.strict_tactics:
            kept = []
            for e in rankable:
                if e.below_tactical_floor:
                    excluded_floor.append({
                        "entity_id": str(e.candidate.entity_id), "name": e.candidate.name,
                        "reason": (f"tactical_fit {e.components['tactical_fit'].value:.2f} "
                                   f"below floor {self.config.tactical_floor:.2f}")})
                else:
                    kept.append(e)
            rankable = kept

        # non-strict mode: floor-breakers are down-ranked (sorted after all
        # others). NOTE (v2.1 §51 decision): thin-evidence candidates are NOT
        # down-ranked — the legacy contract (pinned by tests) is that UNKNOWN
        # data never penalizes. Honesty is carried by the INSUFFICIENT_EVIDENCE
        # score band, LOW confidence and unknown_factors instead.
        rankable.sort(key=lambda e: (
            e.below_tactical_floor,                       # floor-breakers last
            -(e.weighted_score or 0.0),
            -(e.candidate.overall_rating or 0),
            e.candidate.name,
            str(e.candidate.entity_id),
        ))
        ranked = rankable[: max(1, req.limit)]

        best_eval = ranked[0] if ranked and not ranked[0].below_tactical_floor else (ranked[0] if ranked else None)
        if best_eval is not None and best_eval.below_tactical_floor and not req.strict_tactics:
            # everything broke the floor: still return best, but flag it honestly
            pass

        pareto = self._pareto(evaluations)

        budget_status = self._budget_status(req, evaluations)

        # ---- v2.1 enrichment (additive; bounded payload) ----
        self._enrich_top(ranked, req)
        constraints = None
        sensitivity = None
        cfs = None
        replacement = None
        if best_eval is not None:
            best_eval.constraints = self.constraint_report(best_eval, req)
            constraints = best_eval.constraints
            if squad_members:
                for e in ranked[:5]:
                    e.squad_structural = squad_intelligence.squad_structural_fit(
                        e.candidate, squad_members, req, squad_ctx)
            sensitivity = counterfactual.sensitivity(
                [e for e in ranked if not e.below_tactical_floor][:2] or ranked[:2])
            if not req.disable_counterfactuals:
                by_id = {str(c.entity_id): c for c in candidates}
                cfs = counterfactual.counterfactuals(
                    self, by_id, req,
                    _ResultView(ranked, excluded_hard, excluded_floor,
                                budget_status, best_eval))
            if replacement_current is not None:
                try:
                    cur_eval = self.evaluate(replacement_current, req, squad_ctx,
                                             _eff=eff, _ctx=ctx)
                    replacement = squad_intelligence.replacement_analysis(
                        replacement_current.name, cur_eval.components,
                        cur_eval.weighted_score, replacement_current, ranked[:10])
                except ValueError as ex:
                    replacement = [{"error": str(ex)}]

        if best_eval is None:
            empty_conf = recommendation_confidence.compute(
                {"overall_quality": FitValue.unknown("no candidates passed constraints")})
            return RecommendationResult(
                request_id=request_id or str(uuid.uuid4()),
                game_version=str(req.game_version).upper(),
                best=None, best_evaluation=None, best_score=0.0,
                confidence=empty_conf, ranked=[], pareto=pareto,
                excluded_hard=excluded_hard, excluded_by_floor=excluded_floor,
                budget_status=budget_status,
                weights_used=dict(eff),
                evaluations_total=len(evaluations),
                engine_version=self.engine_version,
                sensitivity=sensitivity, counterfactuals=cfs,
                replacement_analysis=replacement, constraints=constraints)

        return RecommendationResult(
            request_id=request_id or str(uuid.uuid4()),
            game_version=str(req.game_version).upper(),
            best=best_eval.candidate, best_evaluation=best_eval,
            best_score=best_eval.weighted_score or 0.0,
            confidence=best_eval.confidence,
            ranked=ranked, pareto=pareto,
            excluded_hard=excluded_hard, excluded_by_floor=excluded_floor,
            budget_status=budget_status,
            weights_used=dict(eff),
            evaluations_total=len(evaluations),
            engine_version=self.engine_version,
            sensitivity=sensitivity, counterfactuals=cfs,
            replacement_analysis=replacement, constraints=constraints)

    # ------------------------------------------------------------------ enrichment
    def _enrich_top(self, ranked: list[CandidateEvaluation],
                    req: UserRequirements) -> None:
        """§15/§16/§17 derived analytics for the top rows (ENGINE-DERIVED,
        bounded payload). Pure computation over published data."""
        slots = formations.slots_for(req.formation) or None
        for e in ranked[:ENRICHMENT_TOP_N]:
            dom = archetypes_mod.dominant_archetype(e.candidate)
            gp = archetypes_mod.gameplay_profile(e.candidate)
            vers = archetypes_mod.versatility(e.candidate, slots)
            e.intelligence = {
                "dominant_archetype": ({"archetype": dom[0], "score": round(dom[1], 3),
                                        "description": archetypes_mod.ARCHETYPE_DEFINITIONS[dom[0]]["description"]}
                                       if dom else None),
                "gameplay_profile": gp,
                "versatility": vers.to_dict(),
                "engine_derived": True,
            }

    # ------------------------------------------------------------------ pareto
    def _pareto(self, evaluations: list[CandidateEvaluation]) -> dict[str, Optional[dict]]:
        def best_by(component: str, require_known: bool = True) -> Optional[dict]:
            pool = [e for e in evaluations if e.rankable
                    and e.components.get(component) is not None
                    and e.components[component].status == FitStatus.KNOWN]
            if not pool:
                return None
            e = max(pool, key=lambda e: (e.components[component].value,
                                         e.weighted_score or 0.0,
                                         e.candidate.name))
            return {"dimension": component, "entity_id": str(e.candidate.entity_id),
                    "name": e.candidate.name,
                    "component_value": round(e.components[component].value, 4),
                    "weighted_score": round(e.weighted_score or 0.0, 4)}

        pool_score = [e for e in evaluations if e.rankable]
        best_overall = None
        if pool_score:
            e = max(pool_score, key=lambda e: (e.weighted_score or 0.0,
                                               e.candidate.overall_rating or 0,
                                               e.candidate.name))
            best_overall = {"dimension": "best_overall",
                            "entity_id": str(e.candidate.entity_id),
                            "name": e.candidate.name,
                            "weighted_score": round(e.weighted_score or 0.0, 4)}

        # best_value requires KNOWN prices — none exist yet -> honest null + reason
        value_pool = [e for e in pool_score
                      if e.budget_decision is not None and e.budget_quote
                      and e.budget_quote.get("price_coins")]
        best_value = None
        if value_pool:
            e = max(value_pool, key=lambda e: ((e.weighted_score or 0.0) /
                                               max(e.budget_quote["price_coins"], 1)))
            best_value = {"dimension": "best_value",
                          "entity_id": str(e.candidate.entity_id),
                          "name": e.candidate.name,
                          "price_coins": e.budget_quote["price_coins"]}

        # §64 — meaningful diversity: best scorer with a DIFFERENT dominant archetype
        alt_arch = self._best_alternative_archetype(pool_score, best_overall)

        out = {
            "best_overall": best_overall,
            "best_attribute_fit": best_by("attribute_fit"),
            "best_tactical_alignment": best_by("tactical_fit"),
            "best_playstyle_fit": best_by("playstyle_fit"),
            "best_chemistry_fit": best_by("team_fit"),
            "best_value": best_value,
            "best_alternative_archetype": alt_arch,
            "unavailable_dimensions": self._unavailable_dims(evaluations, value_pool, alt_arch),
        }
        if any(e.rankable and e.components.get("archetype_fit") is not None
               and e.components["archetype_fit"].status == FitStatus.KNOWN
               for e in evaluations):
            out["best_archetype_fit"] = best_by("archetype_fit")
        return out

    def _best_alternative_archetype(self, pool_score, best_overall) -> Optional[dict]:
        if not pool_score or best_overall is None:
            return None
        scan = sorted(pool_score, key=lambda e: (-(e.weighted_score or 0.0),
                                                 e.candidate.name))[:DIVERSITY_SCAN_TOP_N]
        best_arch = None
        rows = []
        for e in scan:
            dom = (e.intelligence or {}).get("dominant_archetype") if e.intelligence else None
            if dom is None:
                dom_a = archetypes_mod.dominant_archetype(e.candidate)
                dom = {"archetype": dom_a[0], "score": round(dom_a[1], 3)} if dom_a else None
            rows.append((e, dom))
            if str(e.candidate.entity_id) == best_overall["entity_id"]:
                best_arch = dom["archetype"] if dom else None
        for e, dom in rows:
            if dom and dom["archetype"] != best_arch:
                return {"dimension": "best_alternative_archetype",
                        "entity_id": str(e.candidate.entity_id),
                        "name": e.candidate.name,
                        "archetype": dom["archetype"],
                        "weighted_score": round(e.weighted_score or 0.0, 4),
                        "note": f"highest scorer with a different dominant archetype "
                                f"than the winner ({best_arch or 'UNKNOWN'}) — ENGINE-DERIVED"}
        return None

    def _unavailable_dims(self, evaluations, value_pool, alt_arch) -> dict[str, str]:
        out = {}
        if not value_pool:
            out["best_value"] = ("no verified market prices exist — value ranking "
                                 "withheld rather than fabricated (price = UNKNOWN)")
        if not any(e.rankable and e.components["team_fit"].status == FitStatus.KNOWN
                   for e in evaluations):
            out["best_chemistry_fit"] = ("chemistry rules unverified / no squad context — "
                                         "chemistry ranking withheld (UNKNOWN)")
        if alt_arch is None:
            out["best_alternative_archetype"] = (
                "no archetype-diverse alternative could be derived (insufficient "
                "attribute evidence or single-archetype pool)")
        return out

    def _budget_status(self, req: UserRequirements,
                       evaluations: list[CandidateEvaluation]) -> str:
        if req.budget_coins is None:
            return "NO_BUDGET_CONSTRAINT"
        decided = [e for e in evaluations if e.budget_decision is not None]
        if not decided:
            return ("BUDGET_UNVERIFIED: no candidate has a verified price; budget "
                    "constraint could not be enforced (prices are UNKNOWN, never "
                    "assumed affordable)")
        return f"BUDGET_ENFORCED on {len(decided)}/{len(evaluations)} candidates with verified prices"


class _ResultView:
    """Lightweight view passed to counterfactual analysis (avoids recursion
    into a full RecommendationResult before it is constructed)."""
    def __init__(self, ranked, excluded_hard, excluded_by_floor, budget_status, best_eval):
        self.ranked = ranked
        self.excluded_hard = excluded_hard
        self.excluded_by_floor = excluded_by_floor
        self.budget_status = budget_status
        self.best = best_eval.candidate if best_eval else None
