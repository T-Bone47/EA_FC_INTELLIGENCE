"""Phase 41 Domain Contracts: Pre-Action Decision State, Candidate Generation,
Counterfactual Valuation, Uncertainty Quantification, Decision Regret, and Football IQ.

Non-negotiable design invariants encoded directly in these contracts:
1. STRICT PRE-ACTION / POST-ACTION SEPARATION: PostActionOutcome NEVER feeds pre-action models.
2. HONEST EPISTEMIC LABELS: Observed vs Modelled vs Hypothetical are never blurred.
3. UNCERTAINTY BEFORE PRECISION: Candidate & counterfactual outputs expose Monte Carlo ranges.
4. HEURISTIC VS CALIBRATED BOUNDARY: Stage 1/2 valuations declare is_calibrated_probability=False.
5. SYNTHETIC ISOLATION: SYNTHETIC_FIXTURE never enters longitudinal Football IQ profiles.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EpistemicTag(str, Enum):
    OBSERVED = "OBSERVED"
    MODELLED = "MODELLED"
    HYPOTHETICAL = "HYPOTHETICAL"


class FieldAdequacyStatus(str, Enum):
    ADEQUATE = "ADEQUATE"
    PARTIAL_WITH_UNCERTAINTY = "PARTIAL_WITH_UNCERTAINTY"
    INSUFFICIENT_ABSTAIN = "INSUFFICIENT_ABSTAIN"


class CandidateFeasibility(str, Enum):
    FEASIBLE = "FEASIBLE"
    POSSIBLY_FEASIBLE = "POSSIBLY_FEASIBLE"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class DecisionCategory(str, Enum):
    ATTACKING_PASS = "ATTACKING_PASS"
    POSSESSION_RETENTION = "POSSESSION_RETENTION"
    THROUGH_BALL = "THROUGH_BALL"
    SWITCH_OR_CROSS = "SWITCH_OR_CROSS"
    SHOT = "SHOT"
    CARRY_OR_DRIBBLE = "CARRY_OR_DRIBBLE"
    DEFENSIVE_ACTION = "DEFENSIVE_ACTION"
    OFF_BALL_RUN = "OFF_BALL_RUN"


class ValuationStage(str, Enum):
    STAGE_1_HEURISTIC_UTILITY = "STAGE_1_HEURISTIC_UTILITY"
    STAGE_2_MARKOV_XT = "STAGE_2_MARKOV_XT"
    STAGE_3_CALIBRATED_EPV_INTERFACE = "STAGE_3_CALIBRATED_EPV_INTERFACE"


class CounterfactualTier(str, Enum):
    TIER_1_GEOMETRIC = "TIER_1_GEOMETRIC"
    TIER_2_HEURISTIC_TACTICAL = "TIER_2_HEURISTIC_TACTICAL"
    TIER_3_CALIBRATED_GATE = "TIER_3_CALIBRATED_GATE"
    TIER_4_SIMULATOR_CONTRACT = "TIER_4_SIMULATOR_CONTRACT"


class ControllerAttribution(str, Enum):
    GAMER_CONTROLLED = "GAMER_CONTROLLED"
    AI_TEAMMATE = "AI_TEAMMATE"
    TACTICAL_INSTRUCTION_HYPOTHESIS = "TACTICAL_INSTRUCTION_HYPOTHESIS"
    UNKNOWN = "UNKNOWN"


class PreActionPlayerState(BaseModel):
    """Kinematic & tactical state observed BEFORE pre_action_cutoff_sec."""
    track_id: str
    team: str  # HOME | AWAY
    player_slot: str = "OUTFIELD"
    is_goalkeeper: bool = False
    x_m: float
    y_m: float
    vx_mps: float = 0.0
    vy_mps: float = 0.0
    speed_mps: float = 0.0
    facing_angle_rad: Optional[float] = None
    observation_status: str = "OBSERVED"
    positional_sigma_m: float = 1.25
    velocity_sigma_mps: float = 0.75
    stamina_estimate: Optional[float] = None


class PreActionBallState(BaseModel):
    x_m: Optional[float] = None
    y_m: Optional[float] = None
    vx_mps: float = 0.0
    vy_mps: float = 0.0
    carrier_track_id: Optional[str] = None
    possession_team: str = "UNKNOWN"
    ball_xt: Optional[float] = None


class PreActionTeamStructure(BaseModel):
    team: str
    observed_outfield_count: int = 0
    defensive_line_x_m: Optional[float] = None
    midfield_line_x_m: Optional[float] = None
    def_to_mid_gap_m: Optional[float] = None
    mid_to_att_gap_m: Optional[float] = None
    team_width_m: Optional[float] = None
    team_length_m: Optional[float] = None
    rest_defense_count: int = 0
    inferred_formation: Optional[str] = None
    central_channel_density: float = 0.0


class PostActionOutcome(BaseModel):
    """Strictly isolated post-action result stored ONLY for blind-review toggle & hindsight audits."""
    outcome_label: str = "UNKNOWN"
    possession_retained_after_3s: Optional[bool] = None
    xt_realized_after_5s: Optional[float] = None
    led_to_shot_within_8s: Optional[bool] = None
    conceded_transition_within_8s: Optional[bool] = None
    end_ball_xy_m: Optional[Tuple[float, float]] = None


class FieldAdequacyReport(BaseModel):
    """Explicit sufficiency verdict tailored to the specific decision type."""
    decision_type: DecisionCategory
    status: FieldAdequacyStatus
    observation_coverage_pct: float
    calibration_state: str
    missing_or_uncertain_fields: List[str] = Field(default_factory=list)
    can_score_short_pass: bool = False
    can_score_long_switch: bool = False
    can_score_defensive_shape: bool = False
    can_score_shot: bool = False
    rationale: str


class FootballDecisionState(BaseModel):
    """Canonical decision state strictly frozen BEFORE the action occurs."""
    window_id: str
    match_id: str
    video_id: Optional[str] = None
    cluster_id: str
    provenance: str
    decision_type: DecisionCategory
    pre_action_cutoff_sec: float
    action_timestamp_sec: float
    post_action_window_sec: float
    calibration_state: str
    uncertainty_band: str
    observation_coverage_pct: float
    pitch_zone: int = 8
    attacking_direction: str = "LEFT_TO_RIGHT"
    game_version: str = "FC27"
    game_patch: str = "PATCH_1.02"
    controller_attribution: ControllerAttribution = ControllerAttribution.UNKNOWN
    pre_action_ball: PreActionBallState
    pre_action_players: List[PreActionPlayerState] = Field(default_factory=list)
    home_structure: PreActionTeamStructure
    away_structure: PreActionTeamStructure
    adequacy: FieldAdequacyReport
    observed_action_label: Optional[str] = None
    observed_target_track_id: Optional[str] = None
    # Hindsight isolation: populated strictly after window extraction; stripped by engine sanitize helpers
    post_action_outcome: Optional[PostActionOutcome] = None


class PassSpeedSensitivity(BaseModel):
    pass_style: str  # GROUND_PASS | DRIVEN_PASS | THROUGH_BALL | LONG_SWITCH
    assumed_ball_speed_mps: float
    ball_arrival_sec: float
    nearest_opp_arrival_sec: float
    interception_margin_sec: float
    status: str  # OPEN | CONTESTED | BLOCKED


class PassingCorridorEval(BaseModel):
    target_track_id: str
    target_slot: str
    target_xy_m: Tuple[float, float]
    distance_m: float
    point_to_segment_clearance_m: float
    intercepting_opponent_id: Optional[str] = None
    dynamic_interception_margin_sec: float
    receiver_space_radius_m: float
    xt_delta: float
    is_progressive: bool
    is_backward_or_lateral: bool
    turnover_exposure: float
    pass_speed_sensitivity: List[PassSpeedSensitivity] = Field(default_factory=list)


class DefensiveDecisionEval(BaseModel):
    option_family: str  # HOLD_LINE | RECOVER_WITH_CM_CDM | CONTAIN_BALL_CARRIER | CLOSE_PASSING_LANE | PRESS_BALL_CARRIER | TRACK_RUNNER | PRESERVE_CENTRAL_COVER
    controlled_player_known: bool = False
    ball_carrier_exposure_score: float
    central_channel_protection_score: float
    line_integrity_delta_m: float
    displacement_risk: float
    team_shape_framing_note: str


class ShootingDecisionEval(BaseModel):
    evaluation_mode: str = "HEURISTIC_CHANCE_UTILITY"
    is_calibrated_xg: bool = False
    shot_distance_m: float
    shot_angle_deg: float
    defenders_in_shot_cone: int
    gk_distance_from_goal_line_m: Optional[float] = None
    heuristic_shot_quality: float
    best_non_shot_alternative_label: Optional[str] = None
    best_non_shot_utility: Optional[float] = None
    shot_advantage_delta: float
    explanation: str


class OffBallOpportunity(BaseModel):
    runner_track_id: str
    runner_slot: str
    team: str
    control_attribution: ControllerAttribution = ControllerAttribution.UNKNOWN
    run_type: str  # DEPTH_STRETCH | HALF_SPACE_POCKET | SUPPORT_ANGLE | OVERLAP | LANE_CLEAR_DRAG
    velocity_mps: float
    space_opened_score: float
    dragged_defender_ids: List[str] = Field(default_factory=list)
    lane_opened_for_carrier: bool = False
    explanation: str


class PossessionValueBreakdown(BaseModel):
    valuation_stage: ValuationStage = ValuationStage.STAGE_1_HEURISTIC_UTILITY
    is_calibrated_probability: bool = False
    markov_xt_origin: Optional[float] = None
    markov_xt_target: Optional[float] = None
    raw_progression_value: float
    lane_control_reward: float
    space_creation_bonus: float
    reward_component: float
    turnover_risk_penalty: float
    defensive_exposure_penalty: float
    risk_component: float
    risk_adjusted_utility: float
    valuation_disclaimer: str = (
        "HEURISTIC_PRE_ACTION_UTILITY (Stage 1/2): Combines corridor reachability, Markov xT delta, "
        "and transition risk exposure. Not a calibrated EA FC match win/goal probability."
    )


class CandidateAction(BaseModel):
    action_id: str
    action_category: DecisionCategory
    action_family: str  # e.g. SHORT_PASS, PROGRESSIVE_PASS, THROUGH_BALL, SWITCH, CROSS, CARRY, RETAIN, SHOT, HOLD_LINE, CLOSE_PASSING_LANE
    label: str
    target_track_id: Optional[str] = None
    target_slot: Optional[str] = None
    target_xy_m: Optional[Tuple[float, float]] = None
    feasibility: CandidateFeasibility = CandidateFeasibility.FEASIBLE
    epistemic_tag: EpistemicTag = EpistemicTag.MODELLED
    controller_assumption: ControllerAttribution = ControllerAttribution.UNKNOWN
    is_observed_choice: bool = False
    capability_requirement: Dict[str, Any] = Field(default_factory=dict)
    telemetry_evidence_refs: List[str] = Field(default_factory=list)
    passing_eval: Optional[PassingCorridorEval] = None
    defensive_eval: Optional[DefensiveDecisionEval] = None
    shooting_eval: Optional[ShootingDecisionEval] = None
    off_ball_eval: Optional[OffBallOpportunity] = None
    value_breakdown: Optional[PossessionValueBreakdown] = None


class UncertaintyRange(BaseModel):
    q_mean: float
    q_std: float
    q_p10: float
    q_p90: float
    regret_mean: float
    regret_p10: float
    regret_p90: float
    rank_stability_rate: float
    indistinguishable_from_best: bool = False
    monte_carlo_samples: int = 32
    perturbation_sources: List[str] = Field(default_factory=list)


class CounterfactualComparison(BaseModel):
    window_id: str
    match_id: str
    decision_type: DecisionCategory
    tier: CounterfactualTier = CounterfactualTier.TIER_2_HEURISTIC_TACTICAL
    status: str  # EVALUATED | ABSTAINED_INSUFFICIENT_CONTEXT
    abstain_reason: Optional[str] = None
    pre_action_only: bool = True
    observed_action_id: Optional[str] = None
    observed_action_label: Optional[str] = None
    best_alternative_id: Optional[str] = None
    best_alternative_label: Optional[str] = None
    candidates: List[CandidateAction] = Field(default_factory=list)
    observed_utility: Optional[float] = None
    best_alternative_utility: Optional[float] = None
    regret_estimate: Optional[float] = None
    normalized_regret: Optional[float] = None
    uncertainty: Optional[UncertaintyRange] = None
    outcome_vs_decision_note: str = (
        "Decision quality is scored strictly on pre-action state; outcome metrics remain hidden from action ranking."
    )
    tactical_explanation: str = ""
    capability_constraint_note: Optional[str] = None
    epistemic_summary: Dict[str, str] = Field(default_factory=dict)


class DecisionRegretRecord(BaseModel):
    window_id: str
    match_id: str
    cluster_id: str
    decision_type: DecisionCategory
    action_timestamp_sec: float
    regret_estimate: float = Field(ge=0.0)
    normalized_regret: float = Field(ge=0.0, le=1.0)
    indistinguishable_from_best: bool = False
    skill_dimension: str
    severity_band: str  # OPTIMAL | MARGINAL | MODERATE_REGRET | HIGH_REGRET


class FootballIQDimensionScore(BaseModel):
    dimension: str
    label: str
    score_0_100: Optional[float] = None
    confidence: str = "INSUFFICIENT"  # INSUFFICIENT | LOW | MODERATE | HIGH
    sample_windows: int = 0
    cluster_count: int = 0
    preference_value: Optional[float] = None  # Gamer tendency
    execution_error_rate: Optional[float] = None
    decision_quality_score: Optional[float] = None
    outcome_success_rate: Optional[float] = None
    mean_regret: Optional[float] = None
    trend_delta: Optional[float] = None
    caveat: str = ""


class FootballIQProfile(BaseModel):
    user_id: str
    eligible_match_count: int = 0
    eligible_decision_windows: int = 0
    synthetic_excluded_count: int = 0
    overall_football_iq: Optional[float] = None
    confidence: str = "INSUFFICIENT"
    dimensions: List[FootballIQDimensionScore] = Field(default_factory=list)
    top_regret_clusters: List[Dict[str, Any]] = Field(default_factory=list)
    calibration_caveat: str = (
        "Heuristic pre-action utility & Markov xT decision profiling. "
        "Separates gamer tendency, technical execution error, pre-action decision quality, and outcome results."
    )
    updated_at: str = Field(default_factory=_utc_iso)


class DecisionTrainingScenario(BaseModel):
    scenario_id: str
    match_id: str
    window_id: str
    action_timestamp_sec: float
    skill_dimension: str
    provenance: str
    hide_outcome_by_default: bool = True
    pre_action_snapshot: Dict[str, Any] = Field(default_factory=dict)
    prompt: str
    candidate_options: List[Dict[str, Any]] = Field(default_factory=list)
    defensible_option_ids: List[str] = Field(default_factory=list)
    best_option_id: Optional[str] = None
    utility_margins: Dict[str, float] = Field(default_factory=dict)
    explanation_by_option: Dict[str, str] = Field(default_factory=dict)
    difficulty_level: str = "INTERMEDIATE"


class DecisionAnnotationRequest(BaseModel):
    window_id: str
    match_id: str
    annotator_role: str = "PLAYER_SELF"
    best_option_id: Optional[str] = None
    defensible_option_ids: List[str] = Field(default_factory=list)
    disagreement_note: str = Field(default="", max_length=600)
    blind_review_completed: bool = True
