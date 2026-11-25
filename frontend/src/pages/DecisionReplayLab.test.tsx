import { MemoryRouter } from 'react-router-dom'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DecisionReplayLab from './DecisionReplayLab'

vi.mock('../state/session', () => ({
  useSession: () => ({
    user: { id: 'user-p41-test', email: 'gamer@example.com', display_name: 'Tactician', role: 'user', preferred_game_version: 'FC27', preferences: null },
    gameVersion: 'FC27',
    notify: vi.fn(),
  }),
}))

const MOCK_IQ = {
  user_id: 'user-p41-test',
  eligible_match_count: 1,
  eligible_decision_windows: 2,
  synthetic_excluded_count: 1,
  overall_football_iq: 78.4,
  confidence: 'LOW',
  dimensions: [
    {
      dimension: 'passing_risk_balance',
      label: 'Passing Risk & Progression Balance',
      score_0_100: 78.4,
      confidence: 'LOW',
      sample_windows: 2,
      cluster_count: 2,
      preference_value: 0.65,
      execution_error_rate: 0.10,
      outcome_success_rate: 0.75,
      mean_regret: 0.042,
      caveat: 'Cluster weighted',
    },
  ],
  calibration_caveat: 'Heuristic Stage 1/2',
}

describe('DecisionReplayLab (Phase 41)', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url: RequestInfo | URL) => {
      const s = String(url)
      if (s.includes('/api/phase41/football-iq')) return new Response(JSON.stringify(MOCK_IQ), { status: 200 })
      if (s.includes('/api/phase41/windows')) {
        return new Response(
          JSON.stringify({
            count: 1,
            blind_review_mode: true,
            windows: [
              {
                window_id: 'WIN-M1-001',
                match_id: 'M-1',
                decision_type: 'ATTACKING_PASS',
                status: 'EVALUATED',
                provenance: 'IMPORTED_MATCH_TRACE',
                action_timestamp_sec: 28.4,
                calibration_state: 'GOOD',
                coverage_pct: 91.0,
                pre_action_state: {
                  pitch_zone: 8,
                  pre_action_ball: { x_m: 61, y_m: 34, possession_team: 'HOME', carrier_track_id: 'H-CM1' },
                  pre_action_players: [
                    { track_id: 'H-CM1', team: 'HOME', player_slot: 'CM', x_m: 61, y_m: 34 },
                    { track_id: 'H-LW', team: 'HOME', player_slot: 'LW', x_m: 76, y_m: 56 },
                    { track_id: 'A-CDM', team: 'AWAY', player_slot: 'CDM', x_m: 65, y_m: 34 },
                  ],
                },
                post_action_outcome: null,
                counterfactual_comparison: {
                  status: 'EVALUATED',
                  observed_action_id: 'CAND-2',
                  best_alternative_id: 'CAND-1',
                  regret_estimate: 0.085,
                  tactical_explanation: 'Switch to LW open.',
                  uncertainty: { q_p10: 0.22, q_p90: 0.34, regret_p10: 0.03, regret_p90: 0.11, rank_stability_rate: 0.88, indistinguishable_from_best: false, monte_carlo_samples: 24 },
                  candidates: [
                    {
                      action_id: 'CAND-1',
                      action_family: 'SWITCH_PLAY',
                      label: 'Switch Play to LW',
                      target_xy_m: [76, 56],
                      feasibility: 'FEASIBLE',
                      epistemic_tag: 'MODELLED',
                      is_observed_choice: false,
                      passing_eval: { distance_m: 26.6, point_to_segment_clearance_m: 14.2, dynamic_interception_margin_sec: 1.45, receiver_space_radius_m: 9.0, xt_delta: 0.045, turnover_exposure: 0.09 },
                      value_breakdown: { valuation_stage: 'STAGE_1_HEURISTIC_UTILITY', is_calibrated_probability: false, reward_component: 0.34, risk_component: 0.05, risk_adjusted_utility: 0.29, valuation_disclaimer: 'Heuristic' },
                    },
                  ],
                },
                regret_estimate: 0.085,
              },
            ],
          }),
          { status: 200 },
        )
      }
      return new Response('{}', { status: 200 })
    })
  })

  it('renders Blind Review mode, 2D SVG pitch, candidate comparison, and Football IQ profile', async () => {
    render(<MemoryRouter><DecisionReplayLab /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText(/Switch Play to LW/i)).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /Blind Review ON/i })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /pre-action pitch/i })).toBeInTheDocument()
    expect(screen.getByText(/Overall IQ: 78.4\/100/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Inspect Model Math/i }))
    expect(screen.getByText(/is_calibrated_probability=false/i)).toBeInTheDocument()
  })
})
