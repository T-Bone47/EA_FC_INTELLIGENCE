import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type {
  ComponentScores, Confidence, FitValue, RankedCandidate, RecommendationResponse,
} from '../api/types'
import { Results } from './Recommend'

const fit = (value: number | null, status = 'KNOWN'): FitValue => ({
  value, status: status as FitValue['status'], reason: null, evidence: [],
})

const components: ComponentScores = {
  overall_quality: fit(0.85), position_fit: fit(1.0), attribute_fit: fit(0.8),
  tactical_fit: fit(0.7), playstyle_fit: fit(null, 'UNKNOWN'),
  role_fit: fit(null, 'UNKNOWN'), team_fit: fit(null, 'UNKNOWN'),
}

const confidence: Confidence = {
  score: 0.72, evidence_coverage: 0.6,
  known_components: ['overall_quality'], unknown_components: ['playstyle_fit'],
  insufficient_components: [], notes: [],
}

const ranked: RankedCandidate = {
  entity_type: 'game_player', entity_id: 'aaaa-bbbb', name: 'Test Winner',
  components, weighted_score: 0.87, confidence,
  hard_constraint_violation: null, below_tactical_floor: false,
  budget: { decision: null, quote: {} },
}

function makeRes(over: Partial<RecommendationResponse> = {}): RecommendationResponse {
  return {
    request_id: 'req-12345678', game_version: 'FC26',
    best: ranked, best_score: 0.87, confidence, ranked: [ranked],
    pareto: {}, excluded_hard: [], excluded_by_floor: [],
    budget_status: 'NO_BUDGET_CONSTRAINT',
    weights_used: { overall_quality: 0.15, attribute_fit: 0.3 },
    evaluations_total: 42,
    explanations: { summary: 'Summary text.', why_this: ['because'],
                    why_not_alternatives: [], strengths: [], weaknesses: [] },
    data_freshness: { game_version: 'FC26', last_source_observation: null },
    candidate_pool: {}, timing_ms: 12,
    ...over,
  }
}

const noop = vi.fn()

function renderResults(res: RecommendationResponse) {
  return render(
    <MemoryRouter>
      <Results res={res} expanded={null} setExpanded={noop}
               onFeedback={noop} authed={false} />
    </MemoryRouter>,
  )
}

describe('Results v2.1 additive surfaces', () => {
  it('renders legacy response without v2.1 fields (backward compatible)', () => {
    renderResults(makeRes())
    expect(screen.getByText('Summary text.')).toBeInTheDocument()
    expect(screen.queryByText(/confidence v2/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Decision intelligence/)).not.toBeInTheDocument()
  })

  it('shows engine version and confidence v2 when present', () => {
    renderResults(makeRes({
      engine_version: '2.1.0',
      confidence_v2: { score_v2: 0.756, level: 'MEDIUM', reasons: ['legacy 0.72'],
                       composition: { legacy_confidence: 0.72 } },
    }))
    expect(screen.getByText(/engine v2\.1\.0/)).toBeInTheDocument()
    expect(screen.getByText(/confidence v2: 0\.76/)).toBeInTheDocument()
  })

  it('shows the score band and flags INSUFFICIENT_EVIDENCE honestly', () => {
    const { unmount } = renderResults(makeRes({
      best: { ...ranked, score_band: { band: 'STRONG_FIT', meaning: 'strong',
                                       note: 'not a probability' } },
    }))
    expect(screen.getByText(/Strong Fit/)).toBeInTheDocument()
    unmount()
    renderResults(makeRes({
      best: { ...ranked, score_band: { band: 'INSUFFICIENT_EVIDENCE',
                                       meaning: 'thin', evidence_coverage: 0.3 } },
    }))
    expect(screen.getByText(/Insufficient Evidence/)).toBeInTheDocument()
  })

  it('shows engine-derived intelligence chips with the not-official disclaimer', () => {
    renderResults(makeRes({
      best: { ...ranked, intelligence: {
        dominant_archetype: { archetype: 'BOX_TO_BOX', score: 0.78,
                              description: 'engine' },
        gameplay_profile: { labels: [{ label: 'TECHNICAL', engine_derived: true,
                                       evidence: 'ball_control=84' }] },
        versatility: { value: 0.2 },
        engine_derived: true,
      } },
    }))
    expect(screen.getByText(/Box To Box · derived/)).toBeInTheDocument()
    expect(screen.getByText('Technical')).toBeInTheDocument()
    expect(screen.getByText(/versatility 20%/)).toBeInTheDocument()
    expect(screen.getByText(/not official EA attributes/i)).toBeInTheDocument()
  })

  it('shows constraints, sensitivity and counterfactuals', () => {
    renderResults(makeRes({
      constraints: { satisfied: ['game_version FC26 matches the request'],
                     failed: [], unknown: ['budget: no verified price'] },
      sensitivity: { status: 'OK', drivers: [], summary: 'multi-factor margin' },
      counterfactuals: [
        { if: 'tactical profile changed to POSSESSION', then: 'the top fit becomes X',
          changes_recommendation: true },
        { if: 'budget removed', then: 'the same player wins',
          changes_recommendation: false },
      ],
    }))
    expect(screen.getByText(/Decision intelligence/)).toBeInTheDocument()
    expect(screen.getByText('game_version FC26 matches the request')).toBeInTheDocument()
    expect(screen.getByText(/budget: no verified price/)).toBeInTheDocument()
    expect(screen.getByText(/multi-factor margin/)).toBeInTheDocument()
    expect(screen.getByText(/changes the pick/)).toBeInTheDocument()
    expect(screen.getByText(/pick holds/)).toBeInTheDocument()
  })
})
