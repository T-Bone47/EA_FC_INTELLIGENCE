"""Domain contracts for Phase 40: Personal AI Coach, Persistent Gamer DNA & Unified Squad Intelligence.

All models enforce strict epistemic provenance separation, explicit confidence bounds,
and preserve the frozen V3.2.1 baseline intact.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class EpistemicClaimType(str, Enum):
    OFFICIAL_FACT = "OFFICIAL_FACT"
    OBSERVED_USER_EVIDENCE = "OBSERVED_USER_EVIDENCE"
    STATISTICAL_ESTIMATE = "STATISTICAL_ESTIMATE"
    TACTICAL_HYPOTHESIS = "TACTICAL_HYPOTHESIS"
    RESEARCH_METHODOLOGY = "RESEARCH_METHODOLOGY"
    COMMUNITY_OBSERVATION = "COMMUNITY_OBSERVATION"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"


class InterventionCategory(str, Enum):
    NO_SQUAD_CHANGE_NEEDED = "NO_SQUAD_CHANGE_NEEDED"
    GAMEPLAY_PRACTICE = "GAMEPLAY_PRACTICE"
    TACTICAL_INSTRUCTION_ADJUSTMENT = "TACTICAL_INSTRUCTION_ADJUSTMENT"
    FORMATION_ADJUSTMENT = "FORMATION_ADJUSTMENT"
    ROLE_ADJUSTMENT = "ROLE_ADJUSTMENT"
    PLAYER_REPLACEMENT = "PLAYER_REPLACEMENT"
    MULTI_CHANGE = "MULTI_CHANGE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class RootCauseDimension(str, Enum):
    GAMER_DECISION = "GAMER_DECISION"
    FORMATION = "FORMATION"
    TACTICAL_INSTRUCTIONS = "TACTICAL_INSTRUCTIONS"
    SQUAD_STRUCTURE = "SQUAD_STRUCTURE"
    PLAYER_ROLE_SUITABILITY = "PLAYER_ROLE_SUITABILITY"
    PLAYER_CAPABILITY = "PLAYER_CAPABILITY"
    OPPONENT_BEHAVIOUR = "OPPONENT_BEHAVIOUR"
    OBSERVATION_UNCERTAINTY = "OBSERVATION_UNCERTAINTY"


class SquadSlotSnapshot(BaseModel):
    slot_index: int
    slot_position: str
    entity_id: Optional[str] = None
    entity_type: str = "ut_card"  # ut_card | game_player | custom
    player_name: str
    overall_rating: Optional[int] = None
    assigned_role: Optional[str] = None
    role_focus: Optional[str] = None
    role_familiarity: str = "BASE"  # BASE | ROLE_PLUS | ROLE_PLUS_PLUS
    playstyles: List[str] = Field(default_factory=list)
    attributes: Dict[str, float] = Field(default_factory=dict)


class MatchSquadSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    game_version: Literal["FC26", "FC27"] = "FC27"
    formation: str = "4-3-3"
    tactical_profile: str = "BALANCED"
    tactical_instructions: Dict[str, Any] = Field(default_factory=dict)
    slots: List[SquadSlotSnapshot] = Field(default_factory=list)
    snapshot_sha256: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MatchResultSummary(BaseModel):
    goals_for: Optional[int] = None
    goals_against: Optional[int] = None
    outcome: Optional[Literal["WIN", "DRAW", "LOSS"]] = None
    match_minute_coverage: Optional[str] = None


class EvidenceClipRef(BaseModel):
    clip_id: str = Field(default_factory=lambda: f"CLIP-{str(uuid4())[:8]}")
    match_id: str
    video_id: Optional[str] = None
    timestamp_start: float
    timestamp_end: float
    title: str
    diagnostic_code: Optional[str] = None
    provenance: str
    confidence: str = "MODERATE"
    deep_link: str = ""


class MatchRecordCreate(BaseModel):
    match_id: Optional[str] = None
    video_id: Optional[str] = None
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = "PATCH_1.02"
    gameplay_mode: str = "COMPETITIVE_RIVALS"
    platform: str = "PC"
    match_result: MatchResultSummary = Field(default_factory=MatchResultSummary)
    duration_seconds: float = Field(ge=0.0, default=0.0)
    is_partial_match: bool = False
    formation: str = "4-3-3"
    tactical_profile: str = "BALANCED"
    tactical_instructions: Dict[str, Any] = Field(default_factory=dict)
    player_roles: List[Dict[str, Any]] = Field(default_factory=list)
    squad_slots: List[SquadSlotSnapshot] = Field(default_factory=list)
    opponent_context: Dict[str, Any] = Field(default_factory=dict)
    provenance: Literal[
        "REAL_VIDEO_DECODED",
        "IMPORTED_MATCH_TRACE",
        "MANUAL_ANNOTATION",
        "SYNTHETIC_FIXTURE",
    ] = "IMPORTED_MATCH_TRACE"
    observation_quality: Literal["HIGH", "MODERATE", "LOW", "INSUFFICIENT"] = "MODERATE"
    tracking_coverage_pct: float = Field(ge=0.0, le=100.0, default=80.0)
    telemetry_summary: Dict[str, Any] = Field(default_factory=dict)
    feature_metrics: Dict[str, Any] = Field(default_factory=dict)
    tactical_events: List[Dict[str, Any]] = Field(default_factory=list)
    coaching_findings: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_clips: List[EvidenceClipRef] = Field(default_factory=list)
    analysis_version: str = "phase40.v1"
    allow_duplicate_reanalysis: bool = False


class MatchIntelligenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    match_id: str
    user_id: str
    video_id: Optional[str] = None
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = "PATCH_1.02"
    gameplay_mode: str = "COMPETITIVE_RIVALS"
    platform: str = "PC"
    match_result: MatchResultSummary = Field(default_factory=MatchResultSummary)
    duration_seconds: float = 0.0
    is_partial_match: bool = False
    formation: str = "4-3-3"
    tactical_instructions: Dict[str, Any] = Field(default_factory=dict)
    player_roles: List[Dict[str, Any]] = Field(default_factory=list)
    squad_snapshot_id: Optional[str] = None
    squad_snapshot: Optional[MatchSquadSnapshot] = None
    opponent_context: Dict[str, Any] = Field(default_factory=dict)
    provenance: str
    observation_quality: str
    tracking_coverage_pct: float
    telemetry_summary: Dict[str, Any] = Field(default_factory=dict)
    feature_metrics: Dict[str, Any] = Field(default_factory=dict)
    tactical_events: List[Dict[str, Any]] = Field(default_factory=list)
    coaching_findings: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_clips: List[EvidenceClipRef] = Field(default_factory=list)
    analysis_version: str = "phase40.v1"
    content_sha256: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ColdStartPreferences(BaseModel):
    preferred_tempo: Literal["SLOW_POSSESSION", "BALANCED", "FAST_DIRECT"] = "BALANCED"
    pressing_comfort: Literal["LOW_BLOCK", "MID_BLOCK", "HIGH_PRESS"] = "MID_BLOCK"
    width_preference: Literal["NARROW_CENTRAL", "BALANCED", "WIDE_WINGPLAY"] = "BALANCED"
    preferred_formation: str = "4-3-3"
    preferred_build_up: Literal["SHORT_COMBINATION", "BALANCED", "COUNTER_VERTICAL"] = "BALANCED"
    self_reported_weakness: Optional[str] = None
    game_version: Literal["FC26", "FC27"] = "FC27"


class DimensionEstimate(BaseModel):
    dimension: str
    axis_category: Literal["STYLE", "PROFICIENCY"]
    status: Literal["OBSERVED", "LOW_SAMPLE_PROVISIONAL", "INSUFFICIENT_EVIDENCE"]
    estimated_value: Optional[float] = None  # [0, 1] when observable, None when suppressed
    measurement_definition: str
    sample_count: int = 0
    effective_sample_size: float = 0.0  # Kish effective sample size after recency + correlation adjustment
    relevant_match_count: int = 0
    observation_coverage: float = 0.0
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    uncertainty_width: Optional[float] = None
    evidence_references: List[str] = Field(default_factory=list)
    model_version: str = "gamer_dna.v1"
    applicable_editions_patches: List[str] = Field(default_factory=list)
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ArchetypeWeight(BaseModel):
    archetype: str
    affinity_score: float
    rationale: str


class ArchetypeAssessment(BaseModel):
    status: Literal["MIXED_PROFILE", "SINGLE_DOMINANT", "UNCERTAIN_COLD_START", "INSUFFICIENT_EVIDENCE"]
    primary_archetype: str
    secondary_archetype: Optional[str] = None
    weights: List[ArchetypeWeight] = Field(default_factory=list)
    summary: str


class TacticalSuitabilityOption(BaseModel):
    formation: str
    tactical_profile: str
    suitability_score: float
    rationale: str
    recommended_roles: List[str] = Field(default_factory=list)


class ImprovementPotentialItem(BaseModel):
    dimension: str
    priority_score: float
    current_estimate: Optional[float] = None
    reason: str
    recommended_focus: str


class GamerDNAProfile(BaseModel):
    user_id: str
    model_version: str = "gamer_dna.v1"
    eligible_match_count: int = 0
    synthetic_excluded_count: int = 0
    recency_lambda_per_day: float = 0.035
    patch_scope: str = "ALL"
    has_cold_start_preferences: bool = False
    cold_start_preferences: Optional[ColdStartPreferences] = None
    cold_start_style_hints: List[str] = Field(default_factory=list)
    style_dimensions: List[DimensionEstimate] = Field(default_factory=list)
    proficiency_dimensions: List[DimensionEstimate] = Field(default_factory=list)
    tactical_suitability: List[TacticalSuitabilityOption] = Field(default_factory=list)
    improvement_potential: List[ImprovementPotentialItem] = Field(default_factory=list)
    archetype: ArchetypeAssessment
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RootCauseHypothesis(BaseModel):
    dimension: RootCauseDimension
    plausibility_score: float
    epistemic_label: Literal["HYPOTHESIS", "CORROBORATED_PATTERN"] = "HYPOTHESIS"
    rationale: str


class RecurringMistakePattern(BaseModel):
    mistake_id: str
    diagnostic_code: str
    title: str
    formal_definition: str
    required_evidence: str
    applicable_contexts: List[str] = Field(default_factory=list)
    confidence_requirement: str = "MODERATE"
    total_occurrences: int = 0
    total_opportunities: int = 0
    normalized_rate: float = 0.0  # occurrences / opportunities
    severity_estimate: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    confidence_level: Literal["HIGH", "MODERATE", "LOW", "INSUFFICIENT_EVIDENCE"] = "MODERATE"
    supporting_clips: List[EvidenceClipRef] = Field(default_factory=list)
    root_cause_hypotheses: List[RootCauseHypothesis] = Field(default_factory=list)
    suggested_interventions: List[str] = Field(default_factory=list)
    non_card_blame_note: str = "Card identity alone is never treated as proof of tactical fault without role/decision isolation."


class CoachContextEnvelope(BaseModel):
    """Typed cross-route co-pilot context payload validated independently on the server."""
    source_route: str = Field(default="/coach", max_length=120)
    route_name: Optional[str] = Field(default=None, max_length=120)
    game_version: Optional[Literal["FC26", "FC27"]] = None
    game_patch: Optional[str] = Field(default=None, max_length=32)
    selected_card_ids: List[str] = Field(default_factory=list, max_length=25)
    selected_player_names: List[str] = Field(default_factory=list, max_length=25)
    active_filters: Dict[str, Any] = Field(default_factory=dict)
    active_formation: Optional[str] = Field(default=None, max_length=16)
    active_tactical_profile: Optional[str] = Field(default=None, max_length=32)
    squad_id: Optional[str] = Field(default=None, max_length=64)
    match_id: Optional[str] = Field(default=None, max_length=80)
    decision_id: Optional[str] = Field(default=None, max_length=80)
    event_id: Optional[str] = Field(default=None, max_length=80)
    tactical_snapshot_id: Optional[str] = Field(default=None, max_length=64)
    experiment_id: Optional[str] = Field(default=None, max_length=64)
    video_timestamp_sec: Optional[float] = Field(default=None, ge=0.0)
    visible_timestamp_sec: Optional[float] = Field(default=None, ge=0.0)
    evidence_refs: List[str] = Field(default_factory=list, max_length=8)
    squad_snapshot_hint: Optional[Dict[str, Any]] = None

    def normalized_route(self) -> str:
        return (self.route_name or self.source_route or "/coach").strip()


class UserCoachPreferences(BaseModel):
    preferred_formation: Optional[str] = Field(default=None, max_length=16)
    preferred_tactical_profile: Optional[str] = Field(default=None, max_length=32)
    preferred_provider: Literal["AUTO", "GEMINI", "OPENROUTER", "OPENROUTER_FREE", "DETERMINISTIC"] = "AUTO"
    coach_style: Literal["CONCISE_TACTICAL", "DEEP_ANALYST", "DRILL_FOCUSED"] = "CONCISE_TACTICAL"
    consent_saved_default: bool = False


class CoachQuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1200)
    session_id: Optional[str] = None
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: Optional[str] = None
    squad_id: Optional[str] = None
    active_match_id: Optional[str] = None
    context_envelope: Optional[CoachContextEnvelope] = None
    include_research_data: bool = True
    consent_external_llm: bool = False
    preferred_provider: Literal[
        "AUTO",
        "GEMINI",
        "OPENROUTER",
        "OPENROUTER_FREE",
        "DETERMINISTIC",
        "OLLAMA_LOCAL",
        "OPENAI_COMPATIBLE",
    ] = "AUTO"
    model_override: Optional[str] = Field(default=None, max_length=120)
    privacy_strict: bool = False
    user_consent_media: bool = False
    redaction_confirmed: bool = False
    screenshot_use_case: Optional[Literal[
        "FORMATION_SCREENSHOT",
        "SQUAD_SCREENSHOT",
        "MATCH_STATS",
        "TACTICAL_FREEZE",
        "GAMEPLAY_SITUATION",
    ]] = None
    image_b64: Optional[str] = Field(default=None, max_length=6_000_000)
    image_mime: Optional[str] = Field(default=None, max_length=40)
    request_id: Optional[str] = Field(default=None, max_length=80)


class StructuredCoachResponse(BaseModel):
    session_id: str
    message_id: str
    provider: str = "deterministic"
    model: str = "deterministic-coach"
    response_mode: str = "DETERMINISTIC_COACH"
    provider_mode: str = "DETERMINISTIC_COACH"
    intent: str = "GENERAL_FOOTBALL"
    answer: str
    key_findings: List[str] = Field(default_factory=list)
    evidence_references: List[EvidenceClipRef] = Field(default_factory=list)
    relevant_match_ids: List[str] = Field(default_factory=list)
    relevant_timestamps: List[float] = Field(default_factory=list)
    possible_root_causes: List[RootCauseHypothesis] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    tactical_suggestions: List[str] = Field(default_factory=list)
    player_recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    player_cards: List[Dict[str, Any]] = Field(default_factory=list)
    squad_proposal: Optional[Dict[str, Any]] = None
    knowledge_sources: List[Dict[str, Any]] = Field(default_factory=list)
    training_objective: Optional[str] = None
    confidence: str = "LOW"
    limitations: List[str] = Field(default_factory=list)
    provider_notes: List[str] = Field(default_factory=list)
    claim_classifications: Dict[str, str] = Field(default_factory=dict)
    tool_trace: List[Dict[str, Any]] = Field(default_factory=list)
    security_notices: List[str] = Field(default_factory=list)
    abstained: bool = False
    latency_ms: float = 0.0
    ttft_ms: float = 0.0
    tools_sent_count: int = 0
    fallback_used: bool = False
    context_summary: str = ""
    context_freshness_note: str = ""
    multimodal_candidate_notes: List[str] = Field(default_factory=list)
    prompt_version: str = "42.v1"
    token_usage: Dict[str, int] = Field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0})
    usage_metadata: Dict[str, Any] = Field(default_factory=dict)


class FootballKnowledgeEntry(BaseModel):
    entry_id: str
    source_title: str
    source_url: str
    game_version: str  # FC26 | FC27 | BOTH | GENERAL
    patch_version: str
    topic: str
    mechanic: str
    publication_date: str
    verification_status: EpistemicClaimType
    applicability: str
    factual_summary: str
    tags: List[str] = Field(default_factory=list)


class DecisionOption(BaseModel):
    option_id: str
    action_label: str
    action_type: Literal[
        "PASS_OPTION", "RECYCLE_POSSESSION", "SWITCH_PLAY",
        "THROUGH_BALL", "SHOOT", "HOLD_SHAPE", "ENGAGE_PRESS",
    ]
    target_track_id: Optional[str] = None
    target_zone: Optional[int] = None
    lane_openness: Optional[float] = None
    receiver_clearance_m: Optional[float] = None
    xt_delta_estimate: float = 0.0
    turnover_exposure_risk: float = 0.0
    heuristic_q_value: float = 0.0
    is_observed_choice: bool = False
    is_defensible: bool = False
    reasoning: str


class DecisionReviewFrame(BaseModel):
    review_id: str = Field(default_factory=lambda: f"DEC-{str(uuid4())[:8]}")
    match_id: str
    video_id: Optional[str] = None
    timestamp_sec: float
    pre_action_only: bool = True  # Explicitly enforces zero hindsight leakage
    status: Literal["EVALUATED", "ABSTAINED_INSUFFICIENT_CONTEXT"] = "EVALUATED"
    abstain_reason: Optional[str] = None
    model_disclaimer: str = (
        "HEURISTIC_ACTION_VALUE: Scores reflect spatial geometry before the action "
        "(lane clearance, Karun Singh xT delta, defensive coverage), not calibrated EA FC probabilities."
    )
    observed_action: Optional[str] = None
    observed_q_heuristic: Optional[float] = None
    best_alternative_q_heuristic: Optional[float] = None
    regret_estimate: Optional[float] = None  # max Q(s,a') - Q(s,a)
    candidate_options: List[DecisionOption] = Field(default_factory=list)


class ExperimentalBKTState(BaseModel):
    skill_code: str
    p_mastery: float = 0.25
    p_init: float = 0.25
    p_transit: float = 0.14
    p_slip: float = 0.10
    p_guess: float = 0.20
    attempts_count: int = 0
    correct_count: int = 0
    practice_only: bool = True
    status: str = "EXPERIMENTAL_UNVALIDATED_MASTERY"
    brier_calibration_note: str = (
        "Tracks structured freeze-frame practice mastery only; kept strictly separate from live in-match Skill Rating."
    )


class TrainingExercise(BaseModel):
    exercise_id: str
    title: str
    category: str = "GENERAL"
    difficulty: str = "INTERMEDIATE"
    skill_code: str
    diagnostic_code: str
    linked_window_id: Optional[str] = None
    hide_outcome_by_default: bool = True
    source_clip: Optional[EvidenceClipRef] = None
    freeze_timestamp_sec: float
    scenario_summary: str
    options: List[DecisionOption] = Field(default_factory=list)
    defensible_option_ids: List[str] = Field(default_factory=list)
    tactical_reasoning: str
    original_outcome: str
    in_game_drill: str


class TrainingPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: f"PLAN-{str(uuid4())[:8]}")
    user_id: str
    game_version: Literal["FC26", "FC27"] = "FC27"
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    next_match_objectives: List[str] = Field(default_factory=list)
    categories_covered: List[str] = Field(default_factory=list)
    decision_windows_linked: int = 0
    bkt_calibration: Optional[Dict[str, Any]] = None
    exercises: List[TrainingExercise] = Field(default_factory=list)
    bkt_states: Dict[str, ExperimentalBKTState] = Field(default_factory=dict)
    caveat: str = (
        "Training exercises and mastery estimates track structured practice completion; "
        "actual in-match transfer requires subsequent match validation."
    )


class ProgressionWindowSummary(BaseModel):
    window_label: str
    match_count: int
    avg_mistake_rate: Optional[float] = None
    avg_defensive_compactness: Optional[float] = None
    avg_central_progression: Optional[float] = None
    avg_transition_exposure_rate: Optional[float] = None
    training_accuracy: Optional[float] = None
    patches_present: List[str] = Field(default_factory=list)
    formations_present: List[str] = Field(default_factory=list)
    modes_present: List[str] = Field(default_factory=list)


class ProgressionReport(BaseModel):
    user_id: str
    total_eligible_matches: int
    windows: List[ProgressionWindowSummary] = Field(default_factory=list)
    comparability_warnings: List[str] = Field(default_factory=list)
    trend_notes: List[str] = Field(default_factory=list)
    weakness_loop_tracking: List[Dict[str, Any]] = Field(default_factory=list)
    covariate_summary: Dict[str, Any] = Field(default_factory=dict)
    causal_disclaimer: str = (
        "Within-person observational shifts only; EA FC patch tuning, formation shifts, squad upgrades, "
        "and opponent strength prevent causal attribution."
    )
    within_person_experiment_contract: Dict[str, Any] = Field(default_factory=dict)
