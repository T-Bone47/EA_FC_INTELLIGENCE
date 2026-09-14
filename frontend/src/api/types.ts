/** Response/request types mirroring the backend API surface.
 *  `null` always means UNKNOWN — never zero, never empty. */

export type GameVersion = 'FC26' | 'FC27'
export type FitStatus = 'KNOWN' | 'UNKNOWN' | 'INSUFFICIENT_EVIDENCE'

export interface FitValue {
  value: number | null
  status: FitStatus
  reason: string | null
  evidence: string[]
}

export interface ComponentScores {
  overall_quality: FitValue
  position_fit: FitValue
  attribute_fit: FitValue
  tactical_fit: FitValue
  playstyle_fit: FitValue
  role_fit: FitValue
  team_fit: FitValue
}

export interface Confidence {
  score: number
  evidence_coverage: number
  known_components: string[]
  unknown_components: string[]
  insufficient_components: string[]
  notes: string[]
}

/** v2.1 (§23): interpretable band for a fit score — never a probability. */
export interface ScoreBand {
  band: string
  meaning: string
  note?: string
  evidence_coverage?: number
}

/** v2.1 (§12/§14/§32): ENGINE-DERIVED analytics for top-ranked candidates. */
export interface IntelligenceBlock {
  dominant_archetype?: { archetype: string; score: number; description?: string } | null
  archetype?: { archetype: string; score: number; description?: string } | null
  gameplay_profile?: {
    labels: { label: string; engine_derived: boolean; evidence?: string }[]
    additional_qualified?: string[]
    skipped_unknown?: string[]
    note?: string
  }
  versatility?: { status?: string; value?: number | null; reason?: string; evidence?: string[] }
  engine_derived?: boolean
}

export interface ConstraintReport {
  satisfied: string[]
  failed: string[]
  unknown: string[]
}

export interface RankedCandidate {
  entity_type: 'game_player' | 'ut_card'
  entity_id: string
  name: string
  components: ComponentScores
  weighted_score: number | null
  confidence: Confidence
  hard_constraint_violation: string | null
  below_tactical_floor: boolean
  budget: { decision: string | null; quote: Record<string, unknown> }
  // ---- v2.1 additive ----
  score_band?: ScoreBand | null
  evidence_coverage?: number
  intelligence?: IntelligenceBlock | null
  constraints?: ConstraintReport | null
  squad_structural_fit?: FitValue | null
}

export interface RecommendationResponse {
  request_id: string
  game_version: string
  best: RankedCandidate | null
  best_score: number
  confidence: Confidence
  ranked: RankedCandidate[]
  pareto: Record<string, unknown>
  excluded_hard: unknown[]
  excluded_by_floor: unknown[]
  budget_status: string
  weights_used: Record<string, number>
  evaluations_total: number
  explanations: {
    summary: string
    why_this: string[]
    why_not_alternatives: { name: string; entity_id: string; reasons: string[] }[]
    strengths: string[]
    weaknesses: string[]
  }
  data_freshness: { game_version: string; last_source_observation: string | null }
  candidate_pool: Record<string, unknown>
  timing_ms: number
  slot?: { slot_index: number; slot_position: string }
  // ---- v2.1 additive (§24/§35/§36/§54/§59) ----
  engine_version?: string
  confidence_v2?: {
    score_v2: number
    level: string
    reasons: string[]
    composition: Record<string, number | null>
  }
  sensitivity?: { status: string; drivers: unknown[]; summary: string }
  counterfactuals?: { if: string; then: string; changes_recommendation: boolean }[]
  replacement_analysis?: Record<string, unknown>[]
  constraints?: ConstraintReport
  telemetry?: Record<string, unknown>
  provenance?: Record<string, unknown>
}

export interface AttributePreferenceIn {
  attribute: string
  min_value?: number | null
  target_value?: number | null
  weight?: number
}

export interface RecommendationRequest {
  game_version: string
  position?: string | null
  formation?: string | null
  tactical_profile?: string
  custom_tactics?: Record<string, number>
  role?: string | null
  attribute_preferences?: AttributePreferenceIn[]
  desired_playstyles?: string[]
  desired_playstyles_plus?: string[]
  budget_coins?: number | null
  min_overall?: number | null
  max_overall?: number | null
  squad_id?: string | null
  entity_scope?: 'auto' | 'game_player' | 'ut_card'
  strict_tactics?: boolean
  limit?: number
  // ---- v2.1 intelligence inputs (all optional; absent = legacy behavior) ----
  archetype?: string | null
  slot?: string | null
  secondary_tactical_profile?: string | null
  attribute_bands?: { attribute: string; band: string }[]
  enable_interactions?: boolean
  enable_saturation?: boolean
  enable_playstyle_context?: boolean
  required_playstyles?: string[]
  required_league?: string | null
  required_club?: string | null
  required_nation?: string | null
  replacement_for?: string | null
  overall_quality_bias?: 'low' | 'normal' | 'high' | null
  complement_hint?: Record<string, unknown> | null
  disable_counterfactuals?: boolean
}

export interface PlayerListItem {
  id: string
  display_name: string
  position_primary: string
  secondary_positions: string[]
  overall_rating: number | null
  nation: string | null
  club: string | null
  league: string | null
  pace: number | null
  shooting: number | null
  passing: number | null
  dribbling: number | null
  defending: number | null
  physicality: number | null
}

export interface PlayerPage {
  game_version: string
  game_player: Record<string, any>
  attributes: Record<string, number | null>
  secondary_positions: string[]
  playstyles: { name: string; tier: 'base' | 'plus' }[]
  playstyle_data_published: boolean
  cards: unknown[]
  other_game_versions: Record<string, any>[]
  provenance: Record<string, any>
  freshness: Record<string, any>
}

export interface CompareColumn {
  entity_id: string
  entity_type: string
  name: string
  position: string
  secondary_positions: string[]
  nation: string | null
  club: string | null
  league: string | null
  overall_rating: number | null
  facades: Record<string, number | null>
  details: Record<string, number | null>
  playstyles_base: string[]
  playstyles_plus: string[]
  playstyle_data_published: boolean
  rarity: string | null
  price_coins: number | null
}

export interface CompareResponse {
  game_version: string
  columns: CompareColumn[]
  verdict: {
    user_context: boolean
    ranked_for_user?: { name: string; entity_id: string; weighted_score: number }[]
    per_component?: Record<string, (FitValue | null)[]>
    why?: string[]
  }
}

export interface SquadSummary {
  id: string
  name: string
  formation: string
  game_version: string
  filled_slots: number
}

export interface SquadSlot {
  id: string
  slot_index: number
  slot_position: string
  game_player_id: string | null
  ut_card_id: string | null
  player_name: string | null
  position_primary: string | null
  overall_rating?: number | null
  club: string | null
  league: string | null
}

export interface SquadDetail {
  id: string
  name: string
  formation: string
  game_version_code: string
  game_version_id: string
  tactics: Record<string, unknown>
  slots: SquadSlot[]
  [k: string]: unknown
}

export interface SquadEvaluation {
  squad_id: string
  formation: string
  game_version: string
  links: Record<string, unknown>
  slots: SquadSlot[]
  position_checks: {
    slot_index: number
    expected_position: string | null
    player: string | null
    player_position: string | null
    out_of_position: boolean
  }[]
  chemistry: { status: string; reason: string }
}

export interface ReferenceData {
  game_version: string
  status: 'ACTIVE' | 'NO_DATA' | string
  positions: string[]
  position_types: Record<string, string[]>
  playstyles: { playstyle_name: string; plus_holders: number; total_holders: number }[]
  formations: Record<string, string[]>
  tactical_profiles: string[]
  capabilities: Record<string, boolean | null>
  notes?: string | null
  // ---- v2.1 additive ----
  tactical_dimensions?: string[]
  formation_slots?: Record<string, { slot: string; position: string; side: string; duty: string }[]>
  archetypes?: Record<string, { positions: string[]; description: string }>
  quality_bands?: Record<string, number>
  engine_version?: string
}

/** GET /api/meta/game-versions returns a bare array. */
export interface VersionInfo {
  code: string
  display_name: string
  status: string
  released_on: string | null
  config: Record<string, any> | null
}

export interface Playstyle {
  playstyle_name: string
  plus_holders: number
  total_holders: number
}

// ---------------------------------------------------------------- Phase 3 cards
export interface CardListItem {
  id: string
  card_name: string
  position: string
  overall_rating: number | null
  card_type: string | null
  rarity_code: string | null
  rarity_name: string | null
  rarity_raw: string | null
  release_group: string | null
  identity_status: string
  playstyle_data_published: boolean
  player_name: string | null
  price_coins: number | null
  price_observed_at: string | null
  updated_at: string | null
}

export interface CardListResponse {
  game_version: GameVersion
  total: number
  page: number
  page_size: number
  items: CardListItem[]
}

export interface CardDataStatus {
  game_version: GameVersion
  production_cards: number
  synthetic_cards_firewalled: number
  playstyle_published_cards: number
  identity_resolved_cards: number
  cards_with_price: number
  card_roles_rows: number
  verified_chemistry_rules: number
  evolution_rows: number
  quarantined_rows: number
  last_card_update: string | null
  recent_ingestion_runs: Record<string, unknown>[]
  availability: {
    card_attributes: string
    card_prices: string
    card_roles: string
    chemistry_rules: string
    evolutions: string
  }
}

export interface CardVersionRow {
  version_number: number
  content_hash: string
  overall_rating: number | null
  valid_from: string | null
  is_current: boolean
}

export interface CardPageData {
  card: Record<string, any> & {
    id: string
    card_name: string
    position: string
    overall_rating: number | null
    rarity_code: string | null
    rarity_name: string | null
    card_type: string | null
    rarity_raw: string | null
    release_group: string | null
    identity_status: string
    canonical_card_id: string | null
    playstyle_data_published: boolean
    source_id: string
    source_card_id: string
  }
  attribute_overrides: Record<string, number>
  playstyles: { playstyle_name: string; tier: 'base' | 'plus' }[]
  versions: CardVersionRow[]
  price: { price_coins: number | null; platform: string | null;
           observed_at: string | null; confidence: number | null } | null
  game_player: { id: string; display_name: string; position_primary: string;
                 overall_rating: number | null } | null
}

export interface PriceHistoryResponse {
  ut_card_id: string
  observations: number
  status: 'HAS_HISTORY' | 'NO_PRICE_HISTORY'
  history: {
    price_coins: number | null
    platform: string | null
    observed_at: string | null
    confidence: number | null
    source_id: string | null
    currency: string
  }[]
  note: string | null
}
