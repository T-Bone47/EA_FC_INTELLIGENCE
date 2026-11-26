import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import TacticalLab from './TacticalLab'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPatch = vi.fn()
const mockOpenCopilot = vi.fn()
const mockNotify = vi.fn()

let mockUser: { id: string; email: string } | null = null

vi.mock('../api/client', () => ({
  api: {
    get: (...args: any[]) => mockGet(...args),
    post: (...args: any[]) => mockPost(...args),
    patch: (...args: any[]) => mockPatch(...args),
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
  useCopilot: () => ({
    openCopilot: mockOpenCopilot,
  }),
  useCopilotRouteContext: vi.fn(),
}))

describe('TacticalLab (Phase 43)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUser = { id: 'user-43-test', email: 'tactician@example.com' }
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/api/phase43/cv/status')) {
        return Promise.resolve({
          onnx_detector: { status: 'NO_TRAINED_WEIGHTS_PRESENT', active_runtime_fallback: 'CV_CLASSICAL_HSV_CONTOUR' },
          hardware_env: { opencl_device: 'NVIDIA GeForce RTX 3050', training_ready_for_pytorch_gradient_descent: false },
          license_policy: 'Apache-2.0 / MIT runtime stack',
        })
      }
      if (url.includes('/api/phase43/snapshots')) {
        return Promise.resolve({
          items: [
            { snapshot_id: 'TSNP-A', label: 'Base 4-3-3', formation: '4-3-3', tactical_profile: 'HIGH_PRESS', line_height: 75, config_hash: 'abc123456789', version_number: 1, unknown_fields: ['build_up_style'] },
            { snapshot_id: 'TSNP-B', label: 'Control 4-2-3-1', formation: '4-2-3-1', tactical_profile: 'POSSESSION', line_height: 50, config_hash: 'def123456789', version_number: 2, unknown_fields: [] },
          ],
        })
      }
      if (url.includes('/api/phase43/fingerprints')) {
        return Promise.resolve({
          items: [{
            fingerprint_id: 'TFP-1',
            match_id: 'MATCH-1',
            nominal_formation: '4-3-3',
            observed_in_possession_shape: 'BALANCED_BUILD_UP_SHAPE',
            observed_out_of_possession_shape: 'COMPACT_MID_LOW_BLOCK',
            coverage_pct: 91.2,
            calibration_state: 'GOOD',
            evidence_grade: 'OBSERVED_ASSOCIATION',
            phases: [{ phase: 'IN_POSSESSION', metrics: { possession_share: 0.57, width_proxy_m: 41.0 } }],
            intended_vs_observed_deltas: [],
          }],
        })
      }
      if (url.includes('/api/phase43/experiments')) {
        return Promise.resolve({
          items: [{
            experiment_id: 'EXP-1',
            title: '4-3-3 vs 4-2-3-1',
            experiment_type: 'FORMATION_COMPARISON',
            status: 'COMPLETED',
            linked_matches: [{ match_id: 'M-1' }, { match_id: 'M-2' }],
            analysis: {
              primary_metric: 'conceded_transition_rate',
              verdict: 'SUPPORTED_IMPROVEMENT',
              evidence_grade: 'CONTROLLED_EXPERIMENT_EVIDENCE',
              unit_of_analysis: 'MATCH_CLUSTER_AGGREGATE',
              interpretation: 'Transition rate dropped across match-level replicates.',
              arm_a: { formation: '4-3-3', eligible_match_count: 3, mean_primary_metric: 0.42 },
              arm_b: { formation: '4-2-3-1', eligible_match_count: 3, mean_primary_metric: 0.14 },
              bayesian_posterior_prob_b_better: 0.94,
              frequentist_test_name: 'Paired_ttest_rel',
              p_value: 0.021,
              effect_size_hedges_g: -1.42,
              bootstrap_ci_95: [-0.41, -0.14],
              sensitivity_leave_one_out_stable: true,
              confounders: { match_quality_warnings: [] },
            },
          }],
        })
      }
      if (url.includes('/api/phase40/matches')) {
        return Promise.resolve({ items: [{ match_id: 'MATCH-1', formation: '4-3-3', game_patch: 'PATCH_1.04' }] })
      }
      if (url.includes('/api/phase43/recommendations/formations')) {
        return Promise.resolve({
          ranked_formations: [{
            formation: '4-2-3-1',
            tactical_profile: 'POSSESSION / BALANCED',
            theoretical_score: 0.88,
            evidence_grade: 'CONTROLLED_EXPERIMENT_EVIDENCE',
            rationale: 'Best empirical match fit.',
            recommended_roles: ['LDM Holding'],
          }],
        })
      }
      if (url.includes('/api/phase43/personal-meta')) {
        return Promise.resolve({
          eligible_match_count: 6,
          strongest_system: '4-2-3-1',
          validated_experiments_count: 1,
          frozen_v321_weights_altered: false,
          confidence_and_evidence_maturity: { maturity_tier: 'EMERGING' },
          formation_breakdown: [{ formation: '4-2-3-1', matches: 3, wins: 3, draws: 0, losses: 0, mean_conceded_transition_rate: 0.14, mean_defensive_compactness: 0.72 }],
        })
      }
      if (url.includes('/api/phase43/feedback')) {
        return Promise.resolve({ items: [] })
      }
      if (url.includes('/api/phase43/formations/compare')) {
        return Promise.resolve({ preferred_formation: '4-2-3-1', summary: '4-2-3-1 leads', structural_differences: ['Rest defense 0.88 vs 0.64'] })
      }
      return Promise.resolve({})
    })
    mockPost.mockImplementation((url: string) => {
      if (url.includes('/api/phase43/squads/optimize')) {
        return Promise.resolve({
          solver_method: 'SCIPY_LINEAR_SUM_ASSIGNMENT',
          market_price_status: 'MARKET_PRICE_UNAVAILABLE',
          primary_xi: { utility: 0.84, lineup: [{ slot_label: 'GK', player_name: 'Alisson' }] },
          alternatives: [{ label: 'DEFENSIVE', utility: 0.81 }],
        })
      }
      return Promise.resolve({})
    })
  })

  it('renders Tactical Experimentation Lab, fingerprints, experiment Bayes stats, comparator & Co-Pilot', async () => {
    render(
      <MemoryRouter>
        <TacticalLab />
      </MemoryRouter>,
    )

    expect(screen.getByText('Tactical Experimentation Lab')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('Observed In-Poss: BALANCED_BUILD_UP_SHAPE')).toBeInTheDocument()
    })

    // Switch to Experiments tab & check statistical output
    fireEvent.click(screen.getByRole('button', { name: /Experiments \(1\)/i }))
    expect(screen.getByText('SUPPORTED_IMPROVEMENT')).toBeInTheDocument()
    expect(screen.getByText('94.0%')).toBeInTheDocument()

    // Switch to Formations, Optimizer & Triage tab
    fireEvent.click(screen.getByRole('button', { name: /Formations, Optimizer & Triage/i }))
    fireEvent.click(screen.getByRole('button', { name: /Optimize XI/i }))
    await waitFor(() => {
      expect(screen.getByText(/SCIPY_LINEAR_SUM_ASSIGNMENT/i)).toBeInTheDocument()
    })

    // Switch to Meta & CV tab
    fireEvent.click(screen.getByRole('button', { name: /Personal Meta & CV Status/i }))
    expect(screen.getByText('NO_TRAINED_WEIGHTS_PRESENT')).toBeInTheDocument()

    // Trigger Co-Pilot button
    fireEvent.click(screen.getByRole('button', { name: /Ask Co-Pilot/i }))
    expect(mockOpenCopilot).toHaveBeenCalledTimes(1)
  })
})
