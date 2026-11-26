"""Phase 44 Domain Contracts: Professional Gamer DNA V2, Reference Governance & Style Similarity.

Enforces strict epistemic and legal guardrails:
- Playing-style similarity does NOT imply equal skill or competitive ability.
- Group G Technical Execution features are strictly separated from Groups A-F Playing Style.
- Reference data defaults fail-closed (`UNKNOWN` / `METADATA_ONLY` / `AWAITING_PERMISSION`)
  and revoking rights invalidates extracted reference profiles immediately.
- Missing observations remain `None` (never defaulted to `0.0`).
- Preserves frozen V3.2.1 suitability weights and strict FC26/FC27 edition walls.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class RightsStatus(str, Enum):
    RIGHTS_VERIFIED = "RIGHTS_VERIFIED"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    METADATA_ONLY = "METADATA_ONLY"
    AWAITING_PERMISSION = "AWAITING_PERMISSION"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"
    REVOKED = "REVOKED"


class UsagePurpose(str, Enum):
    LOCAL_RESEARCH = "LOCAL_RESEARCH"
    FEATURE_EXTRACTION = "FEATURE_EXTRACTION"
    MODEL_TRAINING = "MODEL_TRAINING"
    COMMERCIAL_INFERENCE = "COMMERCIAL_INFERENCE"
    PUBLIC_PROFILE_DISPLAY = "PUBLIC_PROFILE_DISPLAY"
    VIDEO_REDISTRIBUTION = "VIDEO_REDISTRIBUTION"
    DERIVED_DATASET_REDISTRIBUTION = "DERIVED_DATASET_REDISTRIBUTION"


class FeatureSourceType(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    INTERPOLATED = "INTERPOLATED"
    USER_REPORTED = "USER_REPORTED"
    CANDIDATE_MULTIMODAL_OBSERVATION_UNVERIFIED = "CANDIDATE_MULTIMODAL_OBSERVATION_UNVERIFIED"
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
    UNKNOWN = "UNKNOWN"


class FeatureGroup(str, Enum):
    POSSESSION_BUILDUP = "POSSESSION_BUILDUP"
    ATTACKING_IDENTITY = "ATTACKING_IDENTITY"
    DEFENSIVE_IDENTITY = "DEFENSIVE_IDENTITY"
    SPATIAL_TACTICAL = "SPATIAL_TACTICAL"
    DECISION_PREFERENCE = "DECISION_PREFERENCE"
    TACTICAL_ADAPTABILITY = "TACTICAL_ADAPTABILITY"
    TECHNICAL_EXECUTION = "TECHNICAL_EXECUTION"


class ReferenceSourceRecord(BaseModel):
    source_id: str
    title: str
    source_type: Literal[
        "OFFICIAL_RULES",
        "PUBLIC_COMPETITION_METADATA",
        "AUTHORIZED_CREATOR_CONTRIBUTION",
        "AUTHORIZED_PLAYER_CONTRIBUTION",
        "CONTROLLED_RESEARCH_DATASET",
        "UNKNOWN",
    ] = "PUBLIC_COMPETITION_METADATA"
    source_url: Optional[str] = None
    license_or_terms: str = "UNKNOWN"
    attribution_required: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ReferenceRightsRecord(BaseModel):
    rights_id: str = Field(default_factory=lambda: str(uuid4()))
    reference_id: str
    source_id: Optional[str] = None
    rights_status: RightsStatus = RightsStatus.UNKNOWN
    allow_local_research: bool = False
    allow_feature_extraction: bool = False
    allow_model_training: bool = False
    allow_commercial_inference: bool = False
    allow_public_profile_display: bool = False
    allow_video_redistribution: bool = False
    allow_derived_dataset_redistribution: bool = False
    verified_by: Optional[str] = None
    revocation_reason: Optional[str] = None
    verified_at: Optional[str] = None
    revoked_at: Optional[str] = None
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ProfessionalGamerReference(BaseModel):
    reference_id: str
    public_alias: str
    display_name: Optional[str] = None
    competition_affiliations: List[str] = Field(default_factory=list)
    applicable_editions: List[Literal["FC26", "FC27"]] = Field(default_factory=lambda: ["FC26", "FC27"])
    dataset_version: str = "NONE"
    reference_match_count: int = 0
    evidence_quality: Literal["HIGH", "MODERATE", "LOW", "NONE"] = "NONE"
    profile_coverage: float = 0.0
    rights_status: RightsStatus = RightsStatus.METADATA_ONLY
    rights: Optional[ReferenceRightsRecord] = None
    is_independent_unendorsed: bool = True
    metadata_notes: str = ""


class ReferenceMatchRecord(BaseModel):
    ref_match_id: str = Field(default_factory=lambda: f"REFM-{str(uuid4())[:8]}")
    reference_id: str
    source_id: Optional[str] = None
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = "PATCH_1.04"
    competition_name: str = "METADATA_ONLY"
    gameplay_mode: str = "TOURNAMENT"
    formation: Optional[str] = None
    coverage_pct: float = 0.0
    feature_payload: Dict[str, Any] = Field(default_factory=dict)
    provenance: str = "METADATA_ONLY"
    is_invalidated: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class StyleFeatureObservationV2(BaseModel):
    feature_id: str
    feature_group: FeatureGroup
    mathematical_definition: str
    units: str = "ratio_0_1"
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = "ALL"
    gameplay_mode: str = "ALL"
    raw_value: Optional[float] = None
    normalized_value: Optional[float] = None
    eligible_observations: int = 0
    opportunity_denominator: float = 0.0
    match_count: int = 0
    coverage: float = 0.0
    uncertainty: Optional[float] = None
    source_type: FeatureSourceType = FeatureSourceType.UNKNOWN
    is_proficiency_only: bool = False
    model_version: str = "phase44.v2"
    evidence_references: List[str] = Field(default_factory=list)


class ArchetypeAffinityItem(BaseModel):
    archetype: str
    affinity_score: float
    membership_probability: Optional[float] = None
    supporting_features: List[str] = Field(default_factory=list)
    rationale: str


class ArchetypeAssessmentV2(BaseModel):
    layer_used: Literal["LAYER1_INTERPRETABLE_RULE", "LAYER2_UNSUPERVISED_CLUSTERING", "ABSTAINED"] = "LAYER1_INTERPRETABLE_RULE"
    status: Literal["SINGLE_DOMINANT", "MIXED_PROFILE", "OUT_OF_DISTRIBUTION", "COLD_START_HINT", "INSUFFICIENT_EVIDENCE"]
    primary_archetype: str
    secondary_archetype: Optional[str] = None
    archetypes: List[ArchetypeAffinityItem] = Field(default_factory=list)
    cluster_validation: Optional[Dict[str, Any]] = None
    summary: str


class GamerStyleVectorV2(BaseModel):
    profile_version_id: str = Field(default_factory=lambda: f"DNAV2-{str(uuid4())[:8]}")
    user_id: str
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = "ALL"
    gameplay_mode: str = "ALL"
    eligible_match_count: int = 0
    synthetic_excluded_count: int = 0
    profile_maturity: Literal["COLD_START", "PRELIMINARY", "EMERGING", "STABLE"] = "COLD_START"
    overall_coverage: float = 0.0
    style_features: Dict[str, StyleFeatureObservationV2] = Field(default_factory=dict)
    proficiency_features: Dict[str, StyleFeatureObservationV2] = Field(default_factory=dict)
    distributions: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    context_summary: Dict[str, Any] = Field(default_factory=dict)
    scaler_fit_split: str = "NONE"
    archetype: ArchetypeAssessmentV2
    model_version: str = "phase44.v2"
    limitations: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ProStyleProfileVersion(BaseModel):
    pro_profile_id: str = Field(default_factory=lambda: f"PRODNA-{str(uuid4())[:8]}")
    reference_id: str
    public_alias: str
    rights_status: RightsStatus
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = "PATCH_1.04"
    dataset_version: str = "NONE"
    eligible_ref_matches: int = 0
    coverage: float = 0.0
    style_values: Dict[str, Optional[float]] = Field(default_factory=dict)
    proficiency_values: Dict[str, Optional[float]] = Field(default_factory=dict)
    distributions: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    is_invalidated: bool = False
    model_version: str = "phase44.v2"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ProStyleSimilarityItem(BaseModel):
    reference_id: str
    public_alias: str
    rights_status: RightsStatus
    rank_position: int
    raw_distance: float
    interpretable_similarity_index: float
    feature_overlap_ratio: float
    joint_feature_count: int
    confidence_band: List[float] = Field(default_factory=list)
    rank_stability_pct: float = 0.0
    group_similarities: Dict[str, float] = Field(default_factory=dict)
    distributional_distances: Dict[str, float] = Field(default_factory=dict)
    top_similar_behaviors: List[Dict[str, Any]] = Field(default_factory=list)
    top_divergent_behaviors: List[Dict[str, Any]] = Field(default_factory=list)
    indistinguishable_note: Optional[str] = None
    evidence_references: List[str] = Field(default_factory=list)


class ProStyleSimilarityReport(BaseModel):
    similarity_run_id: str = Field(default_factory=lambda: f"SIM-{str(uuid4())[:8]}")
    user_id: str
    profile_version_id: str
    game_version: Literal["FC26", "FC27"]
    game_patch: str
    distance_metric: str = "WEIGHTED_RELIABILITY_EUCLIDEAN"
    abstained: bool = False
    abstention_reason: Optional[str] = None
    fallback_archetype_summary: str = ""
    eligible_references_count: int = 0
    blocked_or_unverified_count: int = 0
    matches: List[ProStyleSimilarityItem] = Field(default_factory=list)
    uncertainty_summary: Dict[str, Any] = Field(default_factory=dict)
    scale_disclosure: str = (
        "Interpretable similarity index (0..100) reflects normalized stylistic alignment across jointly observed "
        "behavioral dimensions only; it is NOT a probability of equal skill, win rate, or competitive equivalence."
    )
    disclaimer: str = "Independent analysis; not affiliated with or endorsed by any professional player or EA."
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EliteSkillGapItem(BaseModel):
    dimension: str
    user_value: Optional[float] = None
    reference_benchmark_value: Optional[float] = None
    skill_gap_estimate: Optional[float] = None
    status: Literal["STRENGTH", "GAP_PRIORITY", "PARITY", "INSUFFICIENT_EVIDENCE"]
    confidence: float = 0.0
    reference_scope: str
    supporting_evidence: List[str] = Field(default_factory=list)
    suggested_training_objective: str
    suggested_tactical_adjustment: str


class EliteSkillGapReport(BaseModel):
    user_id: str
    game_version: Literal["FC26", "FC27"]
    reference_scope: str
    reference_population_verified: bool = False
    strengths: List[EliteSkillGapItem] = Field(default_factory=list)
    gaps: List[EliteSkillGapItem] = Field(default_factory=list)
    caveats: List[str] = Field(default_factory=list)


class StyleEvolutionPoint(BaseModel):
    window_index: int
    window_label: str
    match_count: int
    primary_archetype: str
    ewma_features: Dict[str, float] = Field(default_factory=dict)
    stability_score: float = 0.0
    experiment_linked_id: Optional[str] = None


class StyleEvolutionReport(BaseModel):
    user_id: str
    game_version: Literal["FC26", "FC27"]
    total_matches_evaluated: int
    windows: List[StyleEvolutionPoint] = Field(default_factory=list)
    shift_detected: bool = False
    shift_summary: str
    experiment_attribution_notes: List[str] = Field(default_factory=list)
    archetype_transitions: List[str] = Field(default_factory=list)
    caveat: str


class StyleAwareRecommendationAdjustment(BaseModel):
    entity_id: str
    name: str
    position: str
    overall_rating: Optional[float] = None
    frozen_v321_suitability: float
    style_alignment_score: float
    weakness_compensation_score: float
    advisory_combined_score: float
    role_recommendations: List[str] = Field(default_factory=list)
    style_rationale: str
    market_price_status: str = "MARKET_PRICE_UNAVAILABLE"
    frozen_v321_weights_altered: bool = False


class StyleSandboxRequest(BaseModel):
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = Field(default="PATCH_1.04", max_length=32)
    sandbox_mode: Literal[
        "SUPPORT_NATURAL_POSSESSION",
        "SHIFT_COUNTER_ATTACK",
        "BALANCE_STABILITY_CREATIVITY",
        "PRO_INSPIRED_TEMPLATE",
        "NATURAL_VS_BALANCED",
    ] = "SUPPORT_NATURAL_POSSESSION"
    formation: Optional[str] = Field(default=None, max_length=16)
    locked_slots: Dict[int, str] = Field(default_factory=dict)
    convert_to_experiment: bool = False


class StyleRecommendationFeedbackCreate(BaseModel):
    recommendation_id: str = Field(min_length=2, max_length=80)
    recommendation_type: str = Field(min_length=2, max_length=64)
    game_version: Literal["FC26", "FC27"] = "FC27"
    game_patch: str = Field(default="PATCH_1.04", max_length=32)
    user_action: Literal["ACCEPTED", "MODIFIED", "REJECTED", "IGNORED", "DEFERRED", "COMPLETED", "WITHDRAWN"]
    profile_version_id: Optional[str] = None
    similarity_run_id: Optional[str] = None
    notes: str = Field(default="", max_length=400)


class StyleRecommendationFeedbackRecord(StyleRecommendationFeedbackCreate):
    feedback_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
