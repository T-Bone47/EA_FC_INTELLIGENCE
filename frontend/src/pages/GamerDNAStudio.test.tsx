import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import GamerDNAStudio from './GamerDNAStudio'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockOpenCopilot = vi.fn()
const mockNotify = vi.fn()

let mockUser: { id: string; email: string } | null = { id: 'u-p44-test', email: 'dna@example.com' }

vi.mock('../api/client', () => ({
  api: {
    get: (...args: any[]) => mockGet(...args),
    post: (...args: any[]) => mockPost(...args),
  },
}))

vi.mock('../state/session', () => ({
  useSession: () => ({
    user: mockUser,
    gameVersion: 'FC27',
    notify: mockNotify,
  }),
}))

vi.mock('../state/copilot', () => ({
  useCopilot: () => ({ openCopilot: mockOpenCopilot }),
  useCopilotRouteContext: vi.fn(),
}))

describe('GamerDNAStudio (Phase 44)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUser = { id: 'u-p44-test', email: 'dna@example.com' }
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/api/phase44/profile')) {
        return Promise.resolve({
          profile_version_id: 'DNAV2-1',
          game_version: 'FC27',
          eligible_match_count: 3,
          overall_coverage: 0.48,
          profile_maturity: 'EMERGING',
          archetype: {
            primary_archetype: 'Possession Architect',
            status: 'SINGLE_DOMINANT',
            summary: 'Controls tempo via short triangles.',
            archetypes: [{ archetype: 'Possession Architect', affinity_score: 0.84, rationale: 'High short pass ratio.' }],
          },
          style_features: {
            possession_retention_preference: { feature_id: 'possession_retention_preference', feature_group: 'POSSESSION_BUILDUP', raw_value: 0.68, source_type: 'OBSERVED', match_count: 3, is_proficiency_only: false },
            crossing_preference: { feature_id: 'crossing_preference', feature_group: 'ATTACKING_IDENTITY', raw_value: null, source_type: 'UNKNOWN', match_count: 0, is_proficiency_only: false },
          },
          proficiency_features: {
            pass_success_rate: { feature_id: 'pass_success_rate', feature_group: 'TECHNICAL_EXECUTION', raw_value: 0.87, source_type: 'OBSERVED', match_count: 3, is_proficiency_only: true },
          },
          limitations: ['Group G technical execution/proficiency features are isolated strictly from Groups A-F style matching.'],
        })
      }
      if (url.includes('/api/phase44/similarity')) {
        return Promise.resolve({
          similarity_run_id: 'SIM-1',
          abstained: true,
          abstention_reason: 'Zero rights-verified professional profiles match FC27.',
          fallback_archetype_summary: 'Possession Architect',
          matches: [],
        })
      }
      if (url.includes('/api/phase44/references')) {
        return Promise.resolve({
          manifest: { authorized_profile_count: 0, total_candidates: 1 },
          candidates: [{ reference_id: 'PRO-1', public_alias: 'Tekkz', rights_status: 'METADATA_ONLY', reference_match_count: 0, applicable_editions: ['FC26', 'FC27'] }],
        })
      }
      if (url.includes('/api/phase44/skill-gap')) {
        return Promise.resolve({
          reference_scope: 'INTERNAL_EXECUTION_TARGET_BENCHMARK',
          reference_population_verified: false,
          gaps: [{ dimension: 'defensive_recovery_success', user_value: 0.55, reference_benchmark_value: 0.72, skill_gap_estimate: 0.17, suggested_training_objective: 'PRESSING_TIMING', suggested_tactical_adjustment: 'Use Stay-Back CM.' }],
          strengths: [{ dimension: 'pass_success_rate', user_value: 0.87, status: 'STRENGTH' }],
        })
      }
      if (url.includes('/api/phase44/evolution')) {
        return Promise.resolve({ total_matches_evaluated: 3, shift_detected: false, shift_summary: 'Stable.', windows: [{ window_index: 1, window_label: 'Matches 1-3', match_count: 3, primary_archetype: 'Possession Architect', stability_score: 0.85 }] })
      }
      if (url.includes('/api/phase44/recommendations/players')) {
        return Promise.resolve({ items: [{ entity_id: 'P-1', name: 'Pedri', position: 'CM', overall_rating: 89, frozen_v321_suitability: 92.1, advisory_combined_score: 91.5, style_rationale: 'Matches Possession Architect.' }] })
      }
      if (url.includes('/api/phase44/recommendations/formations')) {
        return Promise.resolve({ ranked_formations: [{ formation: '4-2-3-1', tactical_profile: 'POSSESSION', theoretical_score: 0.88, evidence_grade: 'THEORETICAL_SUITABILITY' }] })
      }
      if (url.includes('/api/phase44/training-pathway')) {
        return Promise.resolve({ linked_exercises: [{ exercise_id: 'EX-1', title: 'Press Restraint', in_game_drill: 'Practice Arena Drill' }] })
      }
      return Promise.resolve({ items: [] })
    })
    mockPost.mockResolvedValue({
      formation: '4-2-3-1',
      objective: 'POSSESSION',
      description: 'Support natural possession',
      preview_xi: { utility: 88.4 },
      market_price_status: 'MARKET_PRICE_UNAVAILABLE',
    })
  })

  it('renders identity, separates Group G from style, and displays honest pro abstention', async () => {
    render(
      <MemoryRouter>
        <GamerDNAStudio />
      </MemoryRouter>
    )
    await waitFor(() => expect(screen.getAllByText('Possession Architect').length).toBeGreaterThanOrEqual(1))

    fireEvent.click(screen.getByRole('button', { name: /Pro Style Matching/i }))
    await waitFor(() => expect(screen.getByText(/Pro Comparison Abstained Honestly/i)).toBeTruthy())
    expect(screen.getByText('Tekkz')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /Squad & Style Sandbox/i }))
    fireEvent.click(screen.getByRole('button', { name: /Preview Sandbox XI/i }))
    await waitFor(() => expect(mockPost).toHaveBeenCalledWith('/api/phase44/sandbox/preview', expect.any(Object)))
  })
})
