"""Phase 43 Domain Contracts: Personal Tactical Experimentation Lab & Empirical Football Intelligence.

Strict epistemic invariants enforced throughout:
- Immutable versioned TacticalConfigurationSnapshot capturing explicit unknowns (no silent defaults).
- Phase-separated TacticalFingerprint distinguishing nominal formation from observed in/out-of-possession shape.
- Match-clustered statistical inference (never treating correlated video frames as independent samples).
- Explicit separation of Theoretical Suitability vs Observed Association vs Controlled Experiment Evidence vs Unsupported Causal Inference.
- Frozen V3.2.1 math and FC26/FC27 edition + patch walls preserved at every layer.
- Zero invented market prices (MARKET_PRICE_UNAVAILABLE).
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ExperimentType(str, Enum):
    FORMATION_COMPARISON = "FORMATION_COMPARISON"
    TACTICAL_PRESET_COMPARISON = "TACTICAL_PRESET_COMPARISON"
    PLAYER_ROLE_FOCUS_COMPARISON = "PLAYER_ROLE_FOCUS_COMPARISON"
    DEFENSIVE_HEIGHT_PRESS_COMPARISON = "DEFENSIVE_HEIGHT_PRESS_COMPARISON"
    BUILD_UP_STYLE_COMPARISON = "BUILD_UP_STYLE_COMPARISON"
    PLAYER_PARTNERSHIP_COMPARISON = "PLAYER_PARTNERSHIP_COMPARISON"
    SINGLE_POSITION_REPLACEMENT = "SINGLE_POSITION_REPLACEMENT"
    PERSONAL_PLAYSTYLE_COMPATIBILITY = "PERSONAL_PLAYSTYLE_COMPATIBILITY"


class ExperimentStatus(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    ACTIVE = "ACTIVE"
    COLLECTING_EVIDENCE = "COLLECTING_EVIDENCE"
    READY_FOR_ANALYSIS = "READY_FOR_ANALYSIS"
    COMPLETED = "COMPLETED"
    INCONCLUSIVE = "INCONCLUSIVE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class DesignType(str, Enum):
    RANDOMIZED_BLOCKED = "RANDOMIZED_BLOCKED"
    MATCHED_COMPARISON = "MATCHED_COMPARISON"
    CROSSOVER_ABBA = "CROSSOVER_ABBA"
    DESCRIPTIVE_BEFORE_AFTER = "DESCRIPTIVE_BEFORE_AFTER"


class ExperimentArm(str, Enum):
    BASELINE_A = "BASELINE_A"
    VARIANT_B = "VARIANT_B"


class EvidenceGrade(str, Enum):
    THEORETICAL_SUITABILITY = "THEORETICAL_SUITABILITY"
    OBSERVED_ASSOCIATION = "OBSERVED_ASSOCIATION"
    CONTROLLED_EXPERIMENT_EVIDENCE = "CONTROLLED_EXPERIMENT_EVIDENCE"
    UNSUPPORTED_CAUSAL_INFERENCE = "UNSUPPORTED_CAUSAL_INFERENCE"


class StatisticalVerdict(str, Enum):
    SUPPORTED_IMPROVEMENT = "SUPPORTED_IMPROVEMENT"
    SUPPORTED_REGRESSION = "SUPPORTED_REGRESSION"
    NO_CLEAR_DIFFERENCE = "NO_CLEAR_DIFFERENCE"
    INCONCLUSIVE = "INCONCLUSIVE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class TacticalSlotConfig(BaseModel):
    slot_index: int = Field(ge=0, le=10)
    slot_position: str = Field(min_length=1, max_length=12)
    entity_id: Optional[str] = None
    entity_type: Literal["ut_card", "game_player", "custom", "UNKNOWN"] = "game_player"
    player_name: Optional[str] = None
    overall_rating: Optional[int] = Field(default=None, ge=40, le=99)
    assigned_role: Optional[str] = Field(default=None, max_length=48)
    role_focus: Optional[str] = Field(default=None, max_length=48)
    role_familiarity: Literal["BASE", "ROLE_PLUS", "ROLE_PLUS_PLUS", "UNKNOWN"] = "UNKNOWN"
    playstyles: List[str] = Field(default_factory=list)
    attributes: Dict[str, Optional[float]] = Field(default_factory=dict)


class MidMatchTacticalChange(BaseModel):
    minute: int = Field(ge=0, le=130)
    trigger: str = Field(default="USER_CONFIRMED", max_length=64)
    from_formation: Optional[str] = None
    to_formation: Optional[str] = None
    from_profile: Optional[str] = None
    to_profile: Optional[str] = None
    notes: str = Field(default="", max_length=240)
    source: Literal["OBSERVED_TELEMETRY", "USER_CONFIRMED"] = "USER_CONFIRMED"


class TacticalSnapshotCreate(BaseModel):
    label: str = Field(default="Tactical Setup", min_length=1, max_length=120)
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = Field(default="PATCH_1.04", max_length=32)
    gameplay_mode: str = Field(default="COMPETITIVE_RIVALS", max_length=40)
    source_squad_id: Optional[str] = Field(default=None, max_length=64)
    parent_snapshot_id: Optional[str] = Field(default=None, max_length=64)
    formation: str = Field(default="4-3-3", max_length=16)
    tactical_profile: str = Field(default="BALANCED", max_length=32)
    build_up_style: Optional[str] = Field(default=None, max_length=40)
    defensive_approach: Optional[str] = Field(default=None, max_length=40)
    line_height: Optional[int] = Field(default=None, ge=1, le=100)
    width_setting: Optional[int] = Field(default=None, ge=1, le=100)
    tactical_instructions: Dict[str, Any] = Field(default_factory=dict)
    mid_match_changes: List[MidMatchTacticalChange] = Field(default_factory=list)
    notes: str = Field(default="", max_length=400)
    slots: List[TacticalSlotConfig] = Field(default_factory=list, max_length=11)


class TacticalConfigurationSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: f"TSNP-{str(uuid4())[:8]}")
    user_id: str
    label: str
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = "PATCH_1.04"
    gameplay_mode: str = "COMPETITIVE_RIVALS"
    source_squad_id: Optional[str] = None
    formation: str
    tactical_profile: str = "BALANCED"
    build_up_style: Optional[str] = None
    defensive_approach: Optional[str] = None
    line_height: Optional[int] = None
    width_setting: Optional[int] = None
    tactical_instructions: Dict[str, Any] = Field(default_factory=dict)
    mid_match_changes: List[MidMatchTacticalChange] = Field(default_factory=list)
    notes: str = ""
    slots: List[TacticalSlotConfig] = Field(default_factory=list)
    chemistry_summary: Optional[Dict[str, Any]] = None
    cohesion_summary: Optional[Dict[str, Any]] = None
    partnership_summary: Optional[Dict[str, Any]] = None
    gamer_style_preferences: Optional[Dict[str, Any]] = None
    unknown_fields: List[str] = Field(default_factory=list)
    config_hash: str
    version_number: int = 1
    parent_snapshot_id: Optional[str] = None
    is_immutable: bool = True
    market_price_status: str = "MARKET_PRICE_UNAVAILABLE"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FingerprintMetricDetail(BaseModel):
    name: str
    value: Optional[float] = None
    mathematical_definition: str
    units: str = "ratio_0_1"
    eligible_observation_criteria: str
    observation_count: int = 0
    match_count: int = 1
    coverage: float = 0.0
    confidence: float = 0.0
    model_version: str = "phase43.fingerprint.v1"
    evidence_references: List[str] = Field(default_factory=list)
    abstained_reason: Optional[str] = None


class PhaseMetricBlock(BaseModel):
    phase: Literal["IN_POSSESSION", "OUT_OF_POSSESSION", "ATTACKING_TRANSITION", "DEFENSIVE_TRANSITION"]
    metrics: Dict[str, Optional[float]] = Field(default_factory=dict)
    unsupported_metrics: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class IntendedVsObservedDelta(BaseModel):
    dimension: str
    intended_spec: str
    observed_measure: Optional[float] = None
    expected_range: str
    delta: Optional[float] = None
    alignment_status: Literal["ALIGNED", "DRIFTED", "INSUFFICIENT_TELEMETRY"] = "INSUFFICIENT_TELEMETRY"
    explanation: str


class TacticalFingerprint(BaseModel):
    fingerprint_id: str = Field(default_factory=lambda: f"TFP-{str(uuid4())[:8]}")
    user_id: str
    match_id: str
    snapshot_id: Optional[str] = None
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = "PATCH_1.04"
    nominal_formation: str
    observed_in_possession_shape: str = "UNKNOWN_INSUFFICIENT_SPATIAL_DATA"
    observed_out_of_possession_shape: str = "UNKNOWN_INSUFFICIENT_SPATIAL_DATA"
    provenance: str
    phases: List[PhaseMetricBlock] = Field(default_factory=list)
    metric_details: Dict[str, FingerprintMetricDetail] = Field(default_factory=dict)
    intended_vs_observed_deltas: List[IntendedVsObservedDelta] = Field(default_factory=list)
    coverage_pct: float = 0.0
    calibration_state: str = "UNKNOWN"
    visible_outfield_players: Optional[int] = None
    team_compactness_abstained: bool = False
    abstention_reason: Optional[str] = None
    uncertainty_notes: List[str] = Field(default_factory=list)
    unsupported_metrics: List[str] = Field(default_factory=list)
    evidence_grade: EvidenceGrade = EvidenceGrade.OBSERVED_ASSOCIATION
    model_version: str = "phase43.fingerprint.v1"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TacticalExperimentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=140)
    hypothesis: str = Field(min_length=5, max_length=500)
    experiment_type: ExperimentType
    game_version: Literal["FC26", "FC27"] = "FC27"
    baseline_patch: str = Field(default="PATCH_1.04", max_length=32)
    gameplay_mode: str = Field(default="COMPETITIVE_RIVALS", max_length=40)
    baseline_snapshot_id: str = Field(min_length=3, max_length=64)
    variant_snapshot_id: str = Field(min_length=3, max_length=64)
    primary_metric: str = Field(default="conceded_transition_rate", max_length=64)
    secondary_metrics: List[str] = Field(default_factory=lambda: ["possession_share", "central_progression", "defensive_compactness"], max_length=8)
    target_min_matches_per_arm: int = Field(default=3, ge=1, le=50)
    assignment_design: Literal["MATCH_PAIRED_OR_RANDOMIZED_ABBA", "WITHIN_SESSION_BLOCKS"] = "MATCH_PAIRED_OR_RANDOMIZED_ABBA"
    design_type: DesignType = DesignType.CROSSOVER_ABBA
    minimum_meaningful_improvement: float = Field(default=0.05, ge=0.0, le=1.0)
    planned_observations: int = Field(default=6, ge=2, le=100)
    required_coverage_pct: float = Field(default=35.0, ge=0.0, le=100.0)
    stopping_criteria: Dict[str, Any] = Field(default_factory=dict)
    confounder_controls: Dict[str, Any] = Field(default_factory=dict)
    random_seed: int = Field(default=43, ge=0, le=999999)


class ExperimentStatusUpdate(BaseModel):
    status: ExperimentStatus
    reason: Optional[str] = Field(default=None, max_length=240)


class ExperimentMatchLinkCreate(BaseModel):
    match_id: str = Field(min_length=2, max_length=80)
    arm: ExperimentArm
    snapshot_id: Optional[str] = Field(default=None, max_length=64)
    opponent_archetype: Optional[str] = Field(default=None, max_length=48)
    match_order: int = Field(default=0, ge=0, le=500)


class ConfounderReport(BaseModel):
    comparable: bool = True
    version_mismatch_count: int = 0
    patch_drift_detected: bool = False
    mode_mismatch_detected: bool = False
    synthetic_excluded_count: int = 0
    opponent_imbalance_detected: bool = False
    match_quality_warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class ArmSummary(BaseModel):
    arm: ExperimentArm
    snapshot_id: str
    label: str
    formation: str
    eligible_match_count: int = 0
    total_opportunities: int = 0
    mean_primary_metric: Optional[float] = None
    median_primary_metric: Optional[float] = None
    sd_primary_metric: Optional[float] = None
    iqr_primary_metric: Optional[float] = None
    opportunity_normalized_rate: Optional[float] = None
    secondary_means: Dict[str, Optional[float]] = Field(default_factory=dict)
    match_ids: List[str] = Field(default_factory=list)


class ExperimentStatisticalAnalysis(BaseModel):
    experiment_id: str
    primary_metric: str
    higher_is_better: bool
    unit_of_analysis: Literal["MATCH_CLUSTER_AGGREGATE"] = "MATCH_CLUSTER_AGGREGATE"
    protocol_version: int = 1
    verdict: StatisticalVerdict
    evidence_grade: EvidenceGrade
    arm_a: ArmSummary
    arm_b: ArmSummary
    raw_delta_b_minus_a: Optional[float] = None
    relative_improvement: Optional[float] = None
    effect_size_hedges_g: Optional[float] = None
    frequentist_test_name: str = "NONE"
    p_value: Optional[float] = None
    bootstrap_ci_95: Optional[List[float]] = None
    bayesian_posterior_prob_b_better: Optional[float] = None
    posterior_prob_meaningful: Optional[float] = None
    minimum_meaningful_improvement: float = 0.05
    bayesian_credible_interval_95: Optional[List[float]] = None
    sensitivity_leave_one_out_stable: Optional[bool] = None
    adherence_rate: Optional[float] = None
    adherent_match_count: int = 0
    non_adherent_match_count: int = 0
    uncertainty_decomposition: Dict[str, Any] = Field(default_factory=dict)
    confounders: ConfounderReport = Field(default_factory=ConfounderReport)
    interpretation: str
    limitations: List[str] = Field(default_factory=list)
    model_version: str = "phase43.stats.v1"
    analyzed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TacticalExperimentRecord(BaseModel):
    experiment_id: str = Field(default_factory=lambda: f"EXP-{str(uuid4())[:8]}")
    user_id: str
    title: str
    hypothesis: str
    experiment_type: ExperimentType
    game_version: Literal["FC26", "FC27"] = "FC27"
    baseline_patch: str = "PATCH_1.04"
    gameplay_mode: str = "COMPETITIVE_RIVALS"
    baseline_snapshot_id: str
    variant_snapshot_id: str
    primary_metric: str = "conceded_transition_rate"
    secondary_metrics: List[str] = Field(default_factory=list)
    target_min_matches_per_arm: int = 3
    assignment_design: str = "MATCH_PAIRED_OR_RANDOMIZED_ABBA"
    protocol_version: int = 1
    design_type: str = "CROSSOVER_ABBA"
    minimum_meaningful_improvement: float = 0.05
    planned_observations: int = 6
    required_coverage_pct: float = 35.0
    stopping_criteria: Dict[str, Any] = Field(default_factory=dict)
    confounder_controls: Dict[str, Any] = Field(default_factory=dict)
    random_seed: int = 43
    status: ExperimentStatus = ExperimentStatus.DRAFT
    linked_matches: List[Dict[str, Any]] = Field(default_factory=list)
    assignments: List[Dict[str, Any]] = Field(default_factory=list)
    adherence_rate: Optional[float] = None
    analysis: Optional[ExperimentStatisticalAnalysis] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FormationSuitabilityItem(BaseModel):
    formation: str
    tactical_profile: str
    theoretical_score: float
    theoretical_fit: float = 0.5
    observed_performance: Optional[float] = None
    controlled_experiment_evidence: Optional[float] = None
    observed_match_count: int = 0
    observed_avg_delta: Optional[float] = None
    experiment_wins: int = 0
    confidence: float = 0.4
    recommended_roles: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    signal_notes: Dict[str, str] = Field(default_factory=dict)
    evidence_grade: EvidenceGrade = EvidenceGrade.THEORETICAL_SUITABILITY
    rationale: str


class FormationComparisonReport(BaseModel):
    user_id: str
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = "PATCH_1.04"
    formation_a: FormationSuitabilityItem
    formation_b: FormationSuitabilityItem
    structural_differences: List[str] = Field(default_factory=list)
    preferred_formation: str
    evidence_grade: EvidenceGrade = EvidenceGrade.THEORETICAL_SUITABILITY
    summary: str
    caveat: str


class PersonalFormationRecommendation(BaseModel):
    user_id: str
    game_version: Literal["FC26", "FC27"]
    game_patch: str
    frozen_v321_preserved: bool = True
    eligible_match_count: int = 0
    ranked_formations: List[FormationSuitabilityItem] = Field(default_factory=list)
    caveat: str


class ReplacementTriageReport(BaseModel):
    target_slot: str
    current_player_name: Optional[str] = None
    game_version: Literal["FC26", "FC27"] = "FC27"
    likely_causes: List[Dict[str, Any]] = Field(default_factory=list)
    primary_recommendation: Literal[
        "TACTICAL_OR_ROLE_ADJUSTMENT_FIRST",
        "DECISION_PRACTICE_FIRST",
        "TEST_REPLACEMENT_EXPERIMENT",
        "INSUFFICIENT_MATCH_EVIDENCE",
    ]
    purchase_justified: bool = False
    non_purchase_interventions: List[str] = Field(default_factory=list)
    candidate_upgrades: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_comparisons: List[Dict[str, Any]] = Field(default_factory=list)
    proposed_experiment_design: Optional[Dict[str, Any]] = None
    market_price_status: str = "MARKET_PRICE_UNAVAILABLE"
    frozen_v321_untouched: bool = True
    evidence_grade: EvidenceGrade = EvidenceGrade.THEORETICAL_SUITABILITY


class TacticalCounterfactualComparison(BaseModel):
    baseline_snapshot_id: str
    variant_snapshot_id: str
    deltas: List[Dict[str, Any]] = Field(default_factory=list)
    rest_defense_risk_delta: float = 0.0
    progression_lane_delta: float = 0.0
    cohesion_delta: float = 0.0
    partnership_delta: float = 0.0
    zone_geometry_deltas: Dict[str, Any] = Field(default_factory=dict)
    epistemic_classification: Dict[str, str] = Field(default_factory=dict)
    sensitivity_sweep: List[Dict[str, Any]] = Field(default_factory=list)
    role_familiarity_gaps: List[str] = Field(default_factory=list)
    summary: str
    evidence_grade: EvidenceGrade = EvidenceGrade.THEORETICAL_SUITABILITY
    disclaimer: str = (
        "Counterfactual comparison reflects modeled tactical geometry, role familiarity, and V3.2.1 slot synergy only; "
        "actual match outcomes must be tested via controlled match experiments."
    )


class SquadOptimizationRequest(BaseModel):
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = Field(default="PATCH_1.04", max_length=32)
    formation: str = Field(default="4-3-3", max_length=16)
    objective: Literal[
        "BALANCED",
        "ATTACKING",
        "DEFENSIVE",
        "POSSESSION",
        "COUNTER_ATTACK",
        "PRESSING",
        "PERSONALIZED",
    ] = "PERSONALIZED"
    locked_slots: Dict[int, str] = Field(default_factory=dict)
    owned_entity_ids: List[str] = Field(default_factory=list)
    verified_budget_coins: Optional[int] = Field(default=None, ge=0)
    candidate_pool: List[Dict[str, Any]] = Field(default_factory=list)
    max_alternatives: int = Field(default=3, ge=1, le=5)


class SquadOptimizationResult(BaseModel):
    user_id: str
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = "PATCH_1.04"
    formation: str
    objective: str
    solver_method: str
    exact_parity_checked: bool = False
    exact_optimal_gap: Optional[float] = None
    utility_equation: str
    weights_used: Dict[str, float] = Field(default_factory=dict)
    hard_constraints_verified: Dict[str, bool] = Field(default_factory=dict)
    primary_xi: Dict[str, Any] = Field(default_factory=dict)
    alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    market_price_status: str = "MARKET_PRICE_UNAVAILABLE"
    frozen_v321_weights_altered: bool = False
    evidence_grade: EvidenceGrade = EvidenceGrade.THEORETICAL_SUITABILITY
    disclaimer: str = (
        "Multi-objective squad optimization combines frozen V3.2.1 fit with personal playstyle/cohesion objectives; "
        "budget constraints apply only when verified costs exist and live match uplift requires controlled trials."
    )


class RecommendationFeedbackCreate(BaseModel):
    recommendation_id: str = Field(min_length=2, max_length=80)
    recommendation_type: str = Field(min_length=2, max_length=64)
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = Field(default="PATCH_1.04", max_length=32)
    user_action: Literal["ACCEPTED", "MODIFIED", "REJECTED", "IGNORED", "DEFERRED", "COMPLETED"]
    snapshot_id: Optional[str] = None
    experiment_id: Optional[str] = None
    observation_id: Optional[str] = None
    estimated_effect: Optional[float] = None
    uncertainty_summary: Dict[str, Any] = Field(default_factory=dict)
    model_version: str = "phase43.v1"
    notes: str = Field(default="", max_length=400)


class RecommendationFeedbackRecord(RecommendationFeedbackCreate):
    feedback_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PersonalMetaProfile(BaseModel):
    meta_id: str
    user_id: str
    game_version: Literal["FC26", "FC27"]
    game_patch: str
    eligible_match_count: int = 0
    synthetic_excluded_count: int = 0
    strongest_system: Optional[str] = None
    preferred_formations: List[Dict[str, Any]] = Field(default_factory=list)
    effective_player_role_combinations: List[Dict[str, Any]] = Field(default_factory=list)
    successful_partnerships: List[Dict[str, Any]] = Field(default_factory=list)
    experiment_history: List[Dict[str, Any]] = Field(default_factory=list)
    patch_dependent_behaviour: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_and_evidence_maturity: Dict[str, Any] = Field(default_factory=dict)
    vulnerable_matchups: List[str] = Field(default_factory=list)
    formation_breakdown: List[Dict[str, Any]] = Field(default_factory=list)
    validated_experiments_count: int = 0
    frozen_v321_weights_altered: bool = False
    limitations: List[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
