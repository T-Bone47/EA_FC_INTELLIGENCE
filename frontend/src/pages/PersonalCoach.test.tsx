import { MemoryRouter } from 'react-router-dom'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PersonalCoach from './PersonalCoach'

vi.mock('../state/session', () => ({
  useSession: () => ({
    user: { id: 'user-test-1', email: 'gamer@example.com', display_name: 'ProGamer', role: 'user', preferred_game_version: 'FC27', preferences: null },
    gameVersion: 'FC27',
    notify: vi.fn(),
  }),
}))

const MOCK_DNA = {
  user_id: 'user-test-1',
  eligible_match_count: 2,
  synthetic_excluded_count: 1,
  has_cold_start_preferences: false,
  cold_start_style_hints: [],
  style_dimensions: [
    { dimension: 'possession_preference', axis_category: 'STYLE', status: 'OBSERVED', estimated_value: 0.62, measurement_definition: 'Possession share', sample_count: 18, effective_sample_size: 8.4, relevant_match_count: 2, ci_low: 0.45, ci_high: 0.77 },
  ],
  proficiency_dimensions: [
    { dimension: 'defensive_compactness', axis_category: 'PROFICIENCY', status: 'OBSERVED', estimated_value: 0.78, measurement_definition: 'Compactness', sample_count: 18, effective_sample_size: 8.4, relevant_match_count: 2, ci_low: 0.60, ci_high: 0.91 },
    { dimension: 'match_to_match_consistency', axis_category: 'PROFICIENCY', status: 'INSUFFICIENT_EVIDENCE', estimated_value: null, measurement_definition: 'Consistency', sample_count: 2, effective_sample_size: 2.0, relevant_match_count: 2, ci_low: null, ci_high: null },
  ],
  tactical_suitability: [
    { formation: '4-2-3-1', tactical_profile: 'BALANCED', suitability_score: 0.84, rationale: 'Double pivot covers counter channels.', recommended_roles: ['CDM: Holding'] },
  ],
  improvement_potential: [],
  archetype: { status: 'MIXED_PROFILE', primary_archetype: 'Possession Controller', secondary_archetype: 'Defensive Organizer', summary: 'Mixed Possession Controller / Defensive Organizer (n=2 matches)' },
  pro_comparison: { feature_enabled: false, status: 'FEATURE_GATED_AWAITING_VERIFIED_PRO_DATASET', policy: 'Generic tactical archetype similarity only.' },
}

describe('PersonalCoach Workspace (Phase 40 & Phase 41.5 Hybrid Agentic)', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url: RequestInfo | URL) => {
      const s = String(url)
      if (s.includes('/api/phase40/gamer-dna')) return new Response(JSON.stringify(MOCK_DNA), { status: 200 })
      if (s.includes('/api/phase40/matches')) return new Response(JSON.stringify({ count: 1, items: [{ match_id: 'MATCH-1', game_version: 'FC27', game_patch: 'PATCH_1.02', formation: '4-3-3', provenance: 'IMPORTED_MATCH_TRACE', tracking_coverage_pct: 92, coaching_findings: [{}] }] }), { status: 200 })
      if (s.includes('/api/phase40/progression')) return new Response(JSON.stringify({ user_id: 'user-test-1', total_eligible_matches: 2, comparability_warnings: [], trend_notes: [] }), { status: 200 })
      if (s.includes('/api/phase40/training/plan')) return new Response(JSON.stringify({ plan_id: 'PLAN-1', next_match_objectives: ['Cut passing lanes with CDM first'], exercises: [{ exercise_id: 'EX-1', title: 'Close Zone 8 Pocket', skill_code: 'pivot_screening', freeze_timestamp_sec: 14.0, scenario_summary: 'Opponent CAM open', options: [{ option_id: 'CUT', action_label: 'Screen Zone 8 with CDM', is_defensible: true }], defensible_option_ids: ['CUT'], in_game_drill: 'Practice Arena' }] }), { status: 200 })
      if (s.includes('/api/phase40/coach/conversations')) return new Response(JSON.stringify({ count: 1, conversations: [{ session_id: 'S-OLD', title: 'Previous Midfield Review' }] }), { status: 200 })
      if (s.includes('/api/phase40/coach/providers/health')) return new Response(JSON.stringify({ config: { gemini_configured: true, gemini_model: 'gemini-4-hydrogen', openrouter_configured: true, openrouter_model: 'openrouter/free', free_only: true }, free_models: [{ model_id: 'gemini-4-hydrogen' }], quota: { reported_cost_usd_today: 0 } }), { status: 200 })
      if (s.includes('/api/squads')) return new Response(JSON.stringify([{ id: 'SQ-1', name: 'Main 4-2-3-1', formation: '4-2-3-1' }]), { status: 200 })
      if (s.includes('/api/phase40/coach/ask')) {
        return new Response(
          JSON.stringify({
            session_id: 'S-1',
            message_id: 'M-1',
            provider: 'gemini',
            model: 'gemini-4-hydrogen',
            response_mode: 'GEMINI_FREE',
            provider_mode: 'GEMINI_FREE',
            answer: 'Counter vulnerability spotted in Match MATCH-1.',
            key_findings: ['Exposed Central Channel rate 25%'],
            evidence_references: [{ clip_id: 'C-1', match_id: 'MATCH-1', video_id: 'VID-012', timestamp_start: 14.2, timestamp_end: 18.0, title: 'EXPOSED CENTRAL CHANNEL', provenance: 'IMPORTED_MATCH_TRACE', confidence: 'HIGH', deep_link: '/research/gameplay-studio?video_id=VID-012&t=14.2&tab=RADAR_REPLAY' }],
            relevant_match_ids: ['MATCH-1'],
            relevant_timestamps: [14.2],
            possible_root_causes: [],
            recommended_actions: ['Anchor CDM Holding'],
            tactical_suggestions: [],
            player_recommendations: [],
            player_cards: [{ entity_id: 'P-100', name: 'N. Kante', position: 'CDM', overall_rating: 87, score: 0.89, market_price_status: 'MARKET_PRICE_UNAVAILABLE', detail_route: '/players/P-100?game_version=FC27', squad_lab_route: '/cards/squad-lab?item=P-100' }],
            squad_proposal: { proposal_id: 'PROP-1', formation: '4-2-3-1', tactical_profile: 'BALANCED', status: 'PENDING_CONFIRMATION', slots: [{ slot: 'CDM1', position: 'CDM', player: { name: 'N. Kante' } }] },
            knowledge_sources: [{ entry_id: 'KB-1', source_title: 'EA FC27 Pitch Notes', verification_status: 'OFFICIAL_FACT' }],
            confidence: 'MODERATE',
            limitations: ['Experimental telemetry caveats apply'],
            tool_trace: [{ tool: 'get_gamer_dna', status: 'OK', elapsed_ms: 4.1, summary: 'Loaded DNA' }],
            security_notices: [],
            abstained: false,
            usage_metadata: { reported_cost_usd: 0 },
          }),
          { status: 200 }
        )
      }
      if (s.includes('/api/phase40/squad-proposals/PROP-1/confirm')) return new Response(JSON.stringify({ status: 'CONFIRMED_APPLIED' }), { status: 200 })
      if (s.includes('/api/phase40/knowledge')) return new Response(JSON.stringify({ entries: [{ entry_id: 'KB-1', source_title: 'EA FC 27 Pitch Notes — FC IQ', source_url: 'https://ea.com', game_version: 'FC27', patch_version: 'PATCH_1.02', topic: 'Player Roles', publication_date: '2026-09-18', verification_status: 'OFFICIAL_FACT', factual_summary: 'FC IQ covers 37 outfield roles.' }] }), { status: 200 })
      if (s.includes('/api/phase40/training/attempt')) return new Response(JSON.stringify({ attempt: { feedback_summary: 'Defensible tactical read (CUT).', is_optimal_or_defensible: true }, bkt_state: { skill_code: 'pivot_screening', p_mastery: 0.45 } }), { status: 200 })
      return new Response('{}', { status: 200 })
    })
  })

  it('renders Coach workspace, executes grounded query with player cards, squad confirm gate & evidence clips cleanly', async () => {
    render(<MemoryRouter><PersonalCoach /></MemoryRouter>)
    await waitFor(() => expect(screen.getAllByText(/Possession Controller/i).length).toBeGreaterThanOrEqual(1))
    expect(screen.getByText('Previous Midfield Review')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Why do I keep conceding counter-attacks?' }))
    await waitFor(() => expect(screen.getByText(/Counter vulnerability spotted in Match MATCH-1/i)).toBeInTheDocument())
    expect(screen.getAllByText(/N\. Kante/i).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/GEMINI_FREE/i)).toBeInTheDocument()
    const clipLink = screen.getByRole('link', { name: /EXPOSED CENTRAL CHANNEL @ 14\.2s/i })
    expect(clipLink).toHaveAttribute('href', '/research/gameplay-studio?video_id=VID-012&t=14.2&tab=RADAR_REPLAY')

    fireEvent.click(screen.getByRole('button', { name: /Confirm & Apply Squad Change/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Undo \/ Rollback Squad Change/i })).toBeInTheDocument())
  })

  it('renders separate Style vs Proficiency dimensions in Gamer DNA tab', async () => {
    render(<MemoryRouter><PersonalCoach /></MemoryRouter>)
    fireEvent.click(screen.getByRole('button', { name: /Gamer DNA & Progression/i }))
    await waitFor(() => expect(screen.getByText(/1\. Playing Style Profile/i)).toBeInTheDocument())
    expect(screen.getByText(/2\. Playing Proficiency Profile/i)).toBeInTheDocument()
    expect(screen.getByText(/FEATURE_GATED_AWAITING_VERIFIED_PRO_DATASET/i)).toBeInTheDocument()
  })

  it('renders Knowledge Base official fact badges cleanly', async () => {
    render(<MemoryRouter><PersonalCoach /></MemoryRouter>)
    fireEvent.click(screen.getByRole('button', { name: /Official Knowledge Base/i }))
    await waitFor(() => expect(screen.getByText(/EA FC 27 Pitch Notes — FC IQ/i)).toBeInTheDocument())
    expect(screen.getByText('OFFICIAL_FACT')).toBeInTheDocument()
  })

  it('renders Training Academy freeze-frame exercises and records BKT attempt', async () => {
    render(<MemoryRouter><PersonalCoach /></MemoryRouter>)
    fireEvent.click(screen.getByRole('button', { name: /Training Academy/i }))
    await waitFor(() => expect(screen.getByText(/Close Zone 8 Pocket/i)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Screen Zone 8 with CDM/i }))
    await waitFor(() => expect(screen.getByText(/Defensible tactical read/i)).toBeInTheDocument())
  })
})
