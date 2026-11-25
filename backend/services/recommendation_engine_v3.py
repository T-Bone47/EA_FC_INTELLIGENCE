"""V3 recommendation engine.

Card scoring requires a separate, compatible frozen card reference.

Pipeline (INTELLIGENCE_MODEL_SPEC.md, CORE_INTELLIGENCE_ARCHITECTURE.md S4):

    REQUEST
      |
    [1] DEMAND COMPOSITION      once per request, independent of the pool
      |                         (this is what guarantees INV-4 pool independence)
      |
    [2] ELIGIBILITY GATE        per candidate: G1 version, G2 synthetic,
      |                         G3 GK boundary, G4 position, G5 explicit minima,
      |                         G6 required PlayStyles, G7 required links
      |
    [3] CAPABILITY + EVIDENCE   C_lo, C_hi, kappa
      |
      G9 coverage gate          kappa < kappa_min -> NOT_EVALUABLE, leaves ranking
      |
    [4] MODIFIERS               PlayStyle (bounded), interaction (deferred v3.0)
      |
    [5] RANKING                 sort key (-R, -kappa, entity_id) -- see
      |                         "Removed tie-breaks" below
      |
    [6] RESULT                  ranked / excluded / not_evaluable, each carrying
                                 a full ScoringContext or exclusion reason

Removed relative to v2 (measured defects, see CORE_INTELLIGENCE_ARCHITECTURE.md
S1 and S7, S10): `overall_quality` and `position_fit` as scored components;
OVR and candidate name from the sort key; weight redistribution under missing
data; the separate `tactical_floor` exclusion mechanism (superseded by
demand composition -- an unsuitable candidate already scores low because the
tactical signal is inside the single demand vector, not a second, opaque gate).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from backend.domain.card_model import ALL_ATTRS, Candidate, DataStatus
from backend.domain.user_model import UserRequirements
from backend.services import playstyle_context
from backend.services.capability_model import compute_capability
from backend.services.confidence_v2 import compute as compute_confidence_v2
from backend.services.formations import require_formation_slot, validate_tactical_combination
from backend.services.demand_composition import DemandResult, compose_demand
from backend.services.eligibility_gate import (
    ExclusionClass,
    check_coverage_gate,
    check_eligibility,
)
from backend.services.reference_distribution import (
    ReferenceDistribution, Universe,
    check_reference_compatible,
)
from backend.services.scoring_context import ModifierContribution, ScoringContext, reconstruct_score
from backend.services.v3_config import DEFAULT_V3_CONFIG, V3Config

ENGINE_VERSION = "3.2.1"

SUPPORTED_ENTITY_SCOPE = "game_player"


class UnsupportedEntityScopeError(Exception):
    """Raised when a request asks for ut_card scope. Per
    FC26_DATA_BUILD_DECISION.md, no permitted source of FC26 UT card
    evidence exists; the engine refuses rather than silently serving
    player data under a card promise (that would contradict the product's
    own thesis that a player is not a card)."""


@dataclass(frozen=True)
class ExclusionRecord:
    candidate_entity_id: uuid.UUID
    candidate_name: str
    gate: str
    exclusion_class: ExclusionClass
    reason: str


@dataclass(frozen=True)
class RankedCandidate:
    context: ScoringContext
    rank: int


@dataclass(frozen=True)
class RecommendationResultV3:
    ranked: tuple[RankedCandidate, ...]
    excluded: tuple[ExclusionRecord, ...]           # FAILED / UNVERIFIABLE
    not_evaluable: tuple[ExclusionRecord, ...]       # NOT_EVALUABLE (coverage)
    demand: DemandResult
    engine_version: str
    config_version: str
    reference_distribution_version: Optional[str]
    reference_distribution_universe: Optional[str]
    entity_scope: str

    @property
    def best(self) -> Optional[RankedCandidate]:
        return self.ranked[0] if self.ranked else None


def _playstyle_demand(req: UserRequirements) -> dict[str, tuple[float, bool]]:
    def keys(labels):
        return [key for label in labels if (key := playstyle_context.playstyle_key(label))]

    plus = keys(req.desired_playstyles_plus)
    return {key: (playstyle_context.context_value(key, req.tactical_profile, req.position or "")[0], key in plus)
            for key in dict.fromkeys(keys(req.desired_playstyles) + plus)}


def _playstyle_modifier(
    candidate: Candidate, demand: dict[str, tuple[float, bool]], cap: float,
) -> ModifierContribution:
    """Apply the bounded modifier over verified, tier-specific label matches."""
    if not demand:
        return ModifierContribution("playstyle", 0.0, 0.0, cap, "no PlayStyle preference stated")
    if not candidate.playstyle_data_published:
        return ModifierContribution("playstyle", 0.0, 0.0, cap,
                                     "UNVERIFIABLE - source has not published PlayStyle data")

    base = {playstyle_context.playstyle_key(label) for label in candidate.playstyles_base}
    plus = {playstyle_context.playstyle_key(label) for label in candidate.playstyles_plus}
    numerator = 0.0
    for key, (value, requires_plus) in demand.items():
        if key in plus:
            numerator += value
        elif key in base:
            numerator += value * (playstyle_context.BASE_TIER_ONLY_FACTOR if requires_plus else 1.0)

    # Normalize against maximum attainable demand so low affinity stays low
    # even when the user requests only one PlayStyle.
    raw = numerator / len(demand)
    capped = max(0.0, min(cap, cap * raw))
    return ModifierContribution("playstyle", cap * raw, capped, cap,
                                 f"matched {numerator:.2f} of {len(demand)} maximum contextual PlayStyle fit")


class RecommendationEngineV3:
    def __init__(self, config: V3Config = DEFAULT_V3_CONFIG,
                 reference: Optional[ReferenceDistribution] = None,
                 data_version: Optional[str] = None):
        self.config = config
        self.reference = reference
        self.data_version = data_version

    def recommend(self, pool: list[Candidate], req: UserRequirements,
                   request_id: Optional[uuid.UUID] = None) -> RecommendationResultV3:
        scope = SUPPORTED_ENTITY_SCOPE if req.entity_scope == "auto" else req.entity_scope
        card_reference = self.reference is not None and self.reference.universe == Universe.UT_CARDS
        if scope not in (SUPPORTED_ENTITY_SCOPE, "ut_card") or (scope == "ut_card" and not card_reference):
            raise UnsupportedEntityScopeError(
                f"{req.entity_scope} scope is not supported in V3: no permitted source of FC26 "
                "UT card evidence exists (FC26_DATA_BUILD_DECISION.md, "
                "CAN_REAL_FC26_UT_DATA_BE_INGESTED = NO). Use entity_scope='game_player'."
            )
        request_id = request_id or uuid.uuid4()
        if not req.position:
            raise ValueError("v3 engine requires an explicit target position")
        # Version wall for the evidence interval: a distribution frozen from
        # one game version / universe is never applied to another. Refusal,
        # not fallback (Phase 22). Raises ReferenceDistributionMismatch.
        if self.reference is not None:
            check_reference_compatible(self.reference, game_version=req.game_version,
                                       entity_type=scope,
                                       universe=Universe.UT_CARDS if scope == "ut_card" else Universe.RATINGS_SITE_PLAYERS)

        target_position = req.position.upper()
        assignment = require_formation_slot(req.formation, req.slot, target_position)
        validate_tactical_combination(req.tactical_profile, req.secondary_tactical_profile)
        is_gk_request = target_position == "GK"
        lam = self.config.lam_default.value

        unknown_preferences = {p.attribute for p in req.attribute_preferences} - set(ALL_ATTRS)
        if unknown_preferences:
            raise ValueError(f"Unknown attribute preferences: {', '.join(sorted(unknown_preferences))}")
        pref_weights = {p.attribute: (p.weight - 1.0) * 0.05 for p in req.attribute_preferences
                        if p.weight and p.weight != 1.0}

        demand = compose_demand(
            position=target_position,
            tactical_profile=req.tactical_profile,
            secondary_tactical_profile=req.secondary_tactical_profile,
            lam=lam,
            attribute_preference_weights=pref_weights or None,
            slot_emphasis=assignment.emphasis if assignment else None,
        )

        playstyle_demand = _playstyle_demand(req)
        required_styles = [(label, playstyle_context.playstyle_key(label), label.strip().endswith("+"))
                           for label in req.required_playstyles]
        ranked_ctx: list[ScoringContext] = []
        excluded: list[ExclusionRecord] = []
        not_evaluable: list[ExclusionRecord] = []

        permitted = {DataStatus.CANONICAL, DataStatus.SYNTHETIC_TEST}  # synthetic is excluded by G2
        if self.reference and self.reference.data_status == "RESEARCH_ONLY":
            permitted.add(DataStatus.RESEARCH_ONLY)
        for c in pool:
            if c.entity_type != scope or c.data_status not in permitted:
                excluded.append(ExclusionRecord(c.entity_id, c.name, "G2_data_scope", ExclusionClass.FAILED,
                                                "Candidate scope or data status is outside the requested population"))
                continue
            elig = check_eligibility(
                game_version=c.game_version.value if hasattr(c.game_version, "value") else str(c.game_version),
                request_game_version=req.game_version,
                is_gk=(c.position_primary == "GK"),
                request_is_gk=is_gk_request,
                primary_position=c.position_primary,
                secondary_positions=tuple(c.secondary_positions or ()),
                target_position=target_position,
                is_synthetic=c.is_synthetic or c.data_status == DataStatus.SYNTHETIC_TEST,
                theta_pos=self.config.theta_pos.value,
            )
            if not elig.eligible:
                excluded.append(ExclusionRecord(c.entity_id, c.name, elig.gate,
                                                 elig.exclusion_class, elig.reason))
                continue

            # G5 -- explicit attribute minima. Known + below floor -> FAILED.
            # Unknown -> not excluded here (it already reduces kappa below).
            failed_minimum = None
            for p in req.attribute_preferences:
                if p.min_value is None:
                    continue
                v = c.attributes.get(p.attribute)
                if v is not None and v < p.min_value:
                    failed_minimum = f"{p.attribute}={v} < required minimum {p.min_value}"
                    break
            if failed_minimum:
                excluded.append(ExclusionRecord(c.entity_id, c.name, "G5_explicit_minimum",
                                                 ExclusionClass.FAILED, failed_minimum))
                continue

            # G6 -- required PlayStyles.
            if required_styles:
                if not c.playstyle_data_published:
                    excluded.append(ExclusionRecord(
                        c.entity_id, c.name, "G6_required_playstyle", ExclusionClass.UNVERIFIABLE,
                        "PlayStyle data not published for this candidate"))
                    continue
                plus = {playstyle_context.playstyle_key(label) for label in c.playstyles_plus}
                held = plus | {playstyle_context.playstyle_key(label) for label in c.playstyles_base}
                missing_req = [label for label, key, requires_plus in required_styles
                               if key not in (plus if requires_plus else held)]
                if missing_req:
                    excluded.append(ExclusionRecord(
                        c.entity_id, c.name, "G6_required_playstyle", ExclusionClass.FAILED,
                        f"missing required PlayStyle(s): {', '.join(missing_req)}"))
                    continue

            # G7 -- required links (league/club/nation).
            link_fail = None
            link_unverifiable = None
            for field_name, required in (("league", req.required_league),
                                          ("club", req.required_club),
                                          ("nation", req.required_nation)):
                if not required:
                    continue
                actual = getattr(c, field_name)
                if actual is None:
                    link_unverifiable = f"{field_name} is UNKNOWN for this candidate"
                elif actual != required:
                    link_fail = f"{field_name}={actual!r} != required {required!r}"
                    break
            if link_fail:
                excluded.append(ExclusionRecord(c.entity_id, c.name, "G7_required_link",
                                                 ExclusionClass.FAILED, link_fail))
                continue
            if link_unverifiable:
                excluded.append(ExclusionRecord(c.entity_id, c.name, "G7_required_link",
                                                 ExclusionClass.UNVERIFIABLE, link_unverifiable))
                continue

            attr_dict = {a: c.attributes.get(a) for a in demand.vector}
            capability = compute_capability(
                demand=demand.vector, attributes=attr_dict,
                position=target_position, reference=self.reference,
                missing_charge=self.config.missing_value_charge,
            )

            cov_gate = check_coverage_gate(capability.kappa, self.config.kappa_min.value)
            if not cov_gate.eligible:
                not_evaluable.append(ExclusionRecord(c.entity_id, c.name, cov_gate.gate,
                                                      cov_gate.exclusion_class, cov_gate.reason))
                continue

            ps_mod = _playstyle_modifier(c, playstyle_demand, self.config.playstyle_modifier_cap.value)
            interaction_mod = ModifierContribution(
                "interaction", 0.0, 0.0, self.config.interaction_modifier_cap.value,
                "DEFERRED in v3.0 -- not validated for monotonicity under partial "
                "evidence in this session; see V3_MIGRATION_REPORT.md known limitations")
            modifiers = (ps_mod, interaction_mod)
            m_raw = 1.0 + sum(m.capped for m in modifiers)
            m = max(self.config.modifier_min.value, min(self.config.modifier_max.value, m_raw))

            r = round(capability.c_lo * m, 10)
            r_hi = round(capability.c_hi * m, 10)

            # Confidence is computed from coverage (kappa is the dominant
            # dimension per INTELLIGENCE_MODEL_SPEC.md S10) and identity
            # status. It is attached to the context AFTER r/r_hi are fixed
            # and is never read back into either -- see V3_1_CALIBRATION_REPORT.md
            # Phase 11 and the accompanying independence test.
            _identity = getattr(c, "identity_status", None) or c.extra.get("identity_status")
            confidence = compute_confidence_v2(
                legacy_score=capability.kappa,
                identity_status=(_identity.value if hasattr(_identity, "value") else _identity),
            )

            ctx = ScoringContext(
                request_id=request_id, candidate_entity_id=c.entity_id, candidate_name=c.name,
                entity_type=c.entity_type, engine_version=ENGINE_VERSION,
                config_version=self.config.config_version, data_version=self.data_version,
                reference_distribution_version=capability.reference_distribution_version,
                reference_distribution_universe=capability.reference_distribution_universe,
                position=target_position, tactical_profile=req.tactical_profile,
                secondary_tactical_profile=req.secondary_tactical_profile, lam=lam,
                demand_stages=demand.stages, demand_vector=dict(demand.vector),
                per_attribute=capability.per_attribute, coverage_kappa=capability.kappa,
                missing_attributes=capability.missing_attributes,
                c_lo=capability.c_lo, c_hi=capability.c_hi,
                modifiers=modifiers, modifier_total=m, r=r, r_hi=r_hi,
                eligibility=elig, confidence=confidence,
            )
            ranked_ctx.append(ctx)

        ranked_ctx.sort(key=lambda ctx: (-ctx.r, -ctx.coverage_kappa, str(ctx.candidate_entity_id)))
        ranked = tuple(RankedCandidate(ctx, i + 1) for i, ctx in enumerate(ranked_ctx[: req.limit]))

        return RecommendationResultV3(
            ranked=ranked, excluded=tuple(excluded), not_evaluable=tuple(not_evaluable),
            demand=demand, engine_version=ENGINE_VERSION, config_version=self.config.config_version,
            reference_distribution_version=self.reference.version if self.reference else None,
            reference_distribution_universe=self.reference.universe if self.reference else None,
            entity_scope=scope,
        )
