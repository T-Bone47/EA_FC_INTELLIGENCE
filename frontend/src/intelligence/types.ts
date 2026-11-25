/** Mirrors docs/API_V3.md field-for-field. The UI renders these; it never derives scores or ranks. */
export type Division = "Men's Football" | "Women's Football"

export interface StatedSquadPreferences {
  formation?:string|null; preferred_slot?:string|null; playstyle_plus?:string|null; continuity?:boolean; upgrade?:string|null
}

export interface StatedFootballStyle {
  position: string | null
  tactical_profile: string | null
}

export interface FormationSlot {
  slot: string
  position: string
  side: string
  duty: string
}

export interface RecommendationOptions {
  formations: Record<string, FormationSlot[]>
}

export interface RecommendRequest {
  game_version: 'FC26' | 'FC27'
  position: string
  formation?: string
  slot?: string
  tactical_profile: string
  secondary_tactical_profile?: string
  lam?: number
  division?: Division
  include_research_data?: boolean
  attribute_preferences?: { attribute: string; weight: number }[]
  desired_playstyles_plus?: string[]
  limit: number
  explain_top_n?: number
}

export interface AttrRow { attribute: string; value: number | null; weight: number; contribution: number }
export interface DecisionEvidence {
  status: 'NEAR_TIE' | 'EVIDENCE_SENSITIVE' | 'CLEAR_SEPARATION'
  margin_low: number
  margin_high: number
  noise_threshold: number
}
export interface LeadingPair extends DecisionEvidence { higher: string; lower: string }
export interface NearTie {
  next_entity_id: string; score_gap: number; within_noise_threshold: boolean
  intervals_overlap: boolean; why_ahead: string[]
  decision_evidence?: DecisionEvidence
}
export interface Confidence {
  level: string; score: number; reasons: string[]; composition: Record<string, unknown>; reporting_only: boolean
}
export interface TacticalFit {
  position: string; tactical_profile: string; secondary_tactical_profile: string | null; lambda: number
  demand_stages: { stage: string; inputs: Record<string, unknown> }[]
  top_demanded: AttrRow[]; capability: { low: number; high: number }
}
export interface Evidence {
  coverage: number; demanded_attributes: number; published_attributes: number; missing_attributes: string[]
  interval: { low: number; high: number; width: number }
  playstyle: { published: boolean | null; modifier_applied: number | null; reason: string | null }
}
export interface Player {
  overall_rating: number | null; overall_rating_note?: string; position_primary: string; secondary_positions: string[]
  club?: string | null; league?: string | null; nation?: string | null; division?: string | null
  preferred_foot?: string | null; weak_foot_stars?: number | null; skill_moves_stars?: number | null
  face_stats?: Record<string, number>; data_status?: string
  playstyles: { published: boolean; base: string[]; plus: string[] }
}
export interface Entry {
  rank: number; entity_id: string; entity_type: string; name: string
  score: number; score_upper_bound: number
  score_interval: { low: number; high: number; ranked_on: string }
  coverage: number; confidence: Confidence | null; confidence_note: string
  position_eligibility: number; playstyle_contribution: number
  key_strengths: AttrRow[]; key_weaknesses: AttrRow[]
  explanation: { reasons: string[]; trade_offs: string[]; unknowns: string[]; reconstructed_score_matches_ranking: boolean }
  tactical_fit: TacticalFit; evidence: Evidence
  near_tie_with_next?: NearTie
  scoring_context: Record<string, unknown>
  player: Player
}
export interface DivisionInfo {
  requested: Division | null; scope: 'FILTERED' | 'ALL_DIVISIONS'; candidate_counts: Record<string, number>
}
export interface RecommendResponse {
  feedback_receipt?: string
  request_id: string; latency_ms: number; engine_version: string; config_version: string
  dataset: Record<string, unknown>; request: Record<string, unknown>
  counts: { candidates: number; excluded: number; not_evaluable: number; ranked_returned: number }
  division: DivisionInfo; demand_vector: Record<string, number>
  ranked: Entry[]; excluded: unknown[]; not_evaluable: unknown[]
  leading_pair?: LeadingPair | null
}
export interface PairwiseItem {
  higher: string; lower: string; score_gap: number
  within_noise_threshold: boolean; intervals_overlap: boolean; why: string[]
  decision_evidence?: DecisionEvidence
}
export interface CompareResponse {
  request_id: string; request: Record<string, unknown>; dataset: Record<string, unknown>
  players: Entry[]; pairwise: PairwiseItem[]; excluded: unknown[]; not_found: string[]; note: string
}
export interface WhatIfVariant {
  label: string; position?: string; formation?: string; slot?: string; tactical_profile?: string
  secondary_tactical_profile?: string; lam?: number; division?: Division
}
export interface RankRow { rank: number; entity_id: string; name: string; score: number }
export interface TrackedRow {
  item_label?: string
  entity_id: string; name: string; base_rank: number | null; base_score: number | null
  new_rank: number | null; new_score: number | null; score_delta: number | null
}
export interface WhatIfVariantResult {
  candidate_count?: number; parent_request_id?: string; request_id?: string
  label: string; changes: Record<string, unknown>
  demand_shift?: { attribute: string; weight_delta: number }[]
  entered_top?: string[]; top?: RankRow[]; tracked_from_base?: TrackedRow[]
  leading_pair?: LeadingPair | null
  error?: string; detail?: string
}
export interface WhatIfResponse {
  candidate_count?: number
  request_id: string; request: Record<string, unknown>; dataset: Record<string, unknown>
  base_top: RankRow[]; variants: WhatIfVariantResult[]; ranking_depth: number; note: string
}
