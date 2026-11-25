import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { useSession } from '../state/session'
import { useCopilot, useCopilotRouteContext } from '../state/copilot'
import { EpistemicChip } from '../components/ui/StadiumPrimitives'
import { StadiumIcon } from '../components/StadiumIcons'
import './DecisionReplayLab.css'

interface CandidateAction {
  action_id: string
  action_family: string
  label: string
  target_slot?: string | null
  target_xy_m?: [number, number] | null
  feasibility: string
  epistemic_tag: string
  is_observed_choice: boolean
  passing_eval?: {
    distance_m: number
    point_to_segment_clearance_m: number
    dynamic_interception_margin_sec: number
    receiver_space_radius_m: number
    xt_delta: number
    turnover_exposure: number
    pass_speed_sensitivity?: {
      pass_style: string
      assumed_ball_speed_mps: number
      interception_margin_sec: number
      status: string
    }[]
  } | null
  defensive_eval?: {
    option_family: string
    central_channel_protection_score: number
    displacement_risk: number
    team_shape_framing_note: string
  } | null
  shooting_eval?: {
    is_calibrated_xg: boolean
    shot_distance_m: number
    shot_angle_deg: number
    defenders_in_shot_cone: number
    heuristic_shot_quality: number
    explanation: string
  } | null
  value_breakdown?: {
    valuation_stage: string
    is_calibrated_probability: boolean
    reward_component: number
    risk_component: number
    risk_adjusted_utility: number
    valuation_disclaimer: string
  } | null
}

interface DecisionWindowItem {
  window_id: string
  match_id: string
  decision_type: string
  status: string
  provenance: string
  action_timestamp_sec: number
  calibration_state: string
  coverage_pct: number
  pre_action_state: {
    pitch_zone?: number
    pre_action_ball?: { x_m?: number; y_m?: number; possession_team?: string; carrier_track_id?: string | null }
    pre_action_players?: { track_id: string; team: string; player_slot: string; x_m: number; y_m: number; vx_mps?: number; vy_mps?: number; is_goalkeeper?: boolean }[]
    adequacy?: { status: string; rationale: string }
    off_ball_opportunities?: { runner_slot: string; run_type: string; control_attribution: string; explanation: string }[]
  }
  post_action_outcome?: { outcome_label?: string; xt_realized_after_5s?: number | null } | null
  counterfactual_comparison: {
    status: string
    abstain_reason?: string | null
    observed_action_id?: string | null
    observed_action_label?: string | null
    best_alternative_id?: string | null
    best_alternative_label?: string | null
    observed_utility?: number | null
    best_alternative_utility?: number | null
    regret_estimate?: number | null
    normalized_regret?: number | null
    tactical_explanation?: string
    capability_constraint_note?: string | null
    uncertainty?: {
      q_p10: number
      q_p90: number
      regret_p10: number
      regret_p90: number
      rank_stability_rate: number
      indistinguishable_from_best: boolean
      monte_carlo_samples: number
    } | null
    candidates: CandidateAction[]
  }
  regret_estimate?: number | null
}

interface FootballIQData {
  eligible_match_count: number
  eligible_decision_windows: number
  synthetic_excluded_count: number
  overall_football_iq: number | null
  confidence: string
  dimensions: {
    dimension: string
    label: string
    score_0_100: number | null
    confidence: string
    sample_windows: number
    cluster_count: number
    preference_value: number | null
    execution_error_rate: number | null
    outcome_success_rate: number | null
    mean_regret: number | null
    caveat: string
  }[]
  calibration_caveat: string
}

const DEMO_SNAPSHOT_PAYLOAD = {
  match_id: 'DEMO-TRACE-41',
  provenance: 'IMPORTED_MATCH_TRACE',
  observed_action_label: 'ST blocked pass',
  snapshot: {
    timestamp_sec: 28.4,
    calibration_state: 'GOOD',
    uncertainty_band: 'LOW',
    observation_coverage_pct: 91.0,
    possession_team: 'HOME',
    ball_carrier_track_id: 'H-CM1',
    ball_xy: [61.0, 34.0],
    home_structure: { rest_defense_count: 3, def_to_mid_gap_m: 11.4 },
    kinematics: [
      { track_id: 'H-GK', team: 'HOME', player_slot: 'GK', is_goalkeeper: true, x_m: 6.0, y_m: 34.0, vx_mps: 0, vy_mps: 0 },
      { track_id: 'H-CM1', team: 'HOME', player_slot: 'CM', x_m: 61.0, y_m: 34.0, vx_mps: 1.5, vy_mps: 0.2 },
      { track_id: 'H-ST', team: 'HOME', player_slot: 'ST', x_m: 81.0, y_m: 35.0, vx_mps: 3.1, vy_mps: 0.0 },
      { track_id: 'H-LW', team: 'HOME', player_slot: 'LW', x_m: 76.0, y_m: 56.0, vx_mps: 4.5, vy_mps: 0.4 },
      { track_id: 'H-RW', team: 'HOME', player_slot: 'RW', x_m: 74.0, y_m: 11.0, vx_mps: 3.8, vy_mps: -0.3 },
      { track_id: 'H-CDM', team: 'HOME', player_slot: 'CDM', x_m: 49.0, y_m: 31.0, vx_mps: 0.5, vy_mps: -0.2 },
      { track_id: 'A-CB1', team: 'AWAY', player_slot: 'CB', x_m: 70.5, y_m: 34.5, vx_mps: -1.8, vy_mps: 0.0 },
      { track_id: 'A-CB2', team: 'AWAY', player_slot: 'CB', x_m: 79.0, y_m: 39.0, vx_mps: -0.8, vy_mps: -0.4 },
      { track_id: 'A-CDM', team: 'AWAY', player_slot: 'CDM', x_m: 65.5, y_m: 33.8, vx_mps: 1.4, vy_mps: 0.1 },
      { track_id: 'A-RB', team: 'AWAY', player_slot: 'RB', x_m: 72.0, y_m: 45.0, vx_mps: -0.5, vy_mps: 0.6 },
      { track_id: 'A-LB', team: 'AWAY', player_slot: 'LB', x_m: 73.0, y_m: 18.0, vx_mps: 0.2, vy_mps: -0.3 },
      { track_id: 'A-GK', team: 'AWAY', player_slot: 'GK', is_goalkeeper: true, x_m: 99.0, y_m: 34.0, vx_mps: 0, vy_mps: 0 },
    ],
  },
}

export default function DecisionReplayLab() {
  const { user, notify } = useSession()
  const { openCopilot } = useCopilot()
  const [params] = useSearchParams()
  const initialMatch = params.get('match_id') || ''

  const [windows, setWindows] = useState<DecisionWindowItem[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [hideOutcome, setHideOutcome] = useState<boolean>(true)
  const [blindPickId, setBlindPickId] = useState<string>('')
  const [adHocWindow, setAdHocWindow] = useState<DecisionWindowItem | null>(null)
  const [footballIq, setFootballIq] = useState<FootballIQData | null>(null)
  const [showMath, setShowMath] = useState<boolean>(false)
  const [loading, setLoading] = useState<boolean>(false)
  const [savingScenario, setSavingScenario] = useState<boolean>(false)

  async function refreshLab(revealOutcomeFlag = !hideOutcome) {
    if (!user) return
    setLoading(true)
    try {
      const q = new URLSearchParams()
      if (initialMatch) q.set('match_id', initialMatch)
      q.set('reveal_outcome', String(revealOutcomeFlag))
      q.set('limit', '40')
      const [winRes, iqRes] = await Promise.all([
        api.get<{ windows: DecisionWindowItem[] }>(`/api/phase41/windows?${q.toString()}`),
        api.get<FootballIQData>('/api/phase41/football-iq'),
      ])
      setWindows(winRes.windows || [])
      setFootballIq(iqRes)
      if (!selectedId && winRes.windows?.length) {
        setSelectedId(winRes.windows[0].window_id)
      }
    } catch {
      // Allow graceful snapshot preview even if no windows persisted yet
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refreshLab(!hideOutcome)
  }, [user, hideOutcome])

  async function runQuickSnapshotDemo() {
    if (!user) {
      const demoWin: DecisionWindowItem = {
        window_id: 'DEMO-SAMPLE-WINDOW',
        match_id: 'SYNTHETIC-DEMO-01',
        decision_type: 'ATTACKING_PASS',
        status: 'EVALUATED',
        provenance: 'SYNTHETIC_FIXTURE',
        action_timestamp_sec: 28.4,
        calibration_state: 'GOOD',
        coverage_pct: 91.0,
        pre_action_state: {
          pitch_zone: 14,
          pre_action_ball: { x_m: 61.0, y_m: 34.0, possession_team: 'HOME', carrier_track_id: 'H-CM1' },
          pre_action_players: DEMO_SNAPSHOT_PAYLOAD.snapshot.kinematics,
          adequacy: { status: 'SUFFICIENT', rationale: '12 outfield/GK tracks calibrated.' },
        },
        post_action_outcome: null,
        counterfactual_comparison: {
          status: 'EVALUATED',
          observed_action_id: 'ACT-ST-BLOCKED',
          observed_action_label: 'Vertical Pass to Marked ST',
          best_alternative_id: 'ACT-LW-SWITCH',
          best_alternative_label: 'Switch Left Wide to Unmarked LW',
          observed_utility: 0.214,
          best_alternative_utility: 0.486,
          regret_estimate: 0.272,
          normalized_regret: 0.56,
          tactical_explanation: 'Sample Demo Fixture: Central lane to ST is screened by A-CDM (negative clearance margin -0.18s); LW half-space receives +0.62s uncontested reception window.',
          capability_constraint_note: 'SYNTHETIC_FIXTURE demo sample — sign in to evaluate uploaded match recordings.',
          uncertainty: { q_p10: 0.421, q_p90: 0.542, regret_p10: 0.195, regret_p90: 0.341, rank_stability_rate: 0.89, indistinguishable_from_best: false, monte_carlo_samples: 200 },
          candidates: [
            {
              action_id: 'ACT-LW-SWITCH',
              action_family: 'PASS',
              label: 'Switch to Unmarked LW',
              target_slot: 'LW',
              target_xy_m: [76.0, 56.0],
              feasibility: 'OPEN',
              epistemic_tag: 'SYNTHETIC_FIXTURE',
              is_observed_choice: false,
              passing_eval: { distance_m: 26.6, point_to_segment_clearance_m: 5.4, dynamic_interception_margin_sec: 0.62, receiver_space_radius_m: 7.2, xt_delta: 0.145, turnover_exposure: 0.08 },
              value_breakdown: { valuation_stage: 'HEURISTIC', is_calibrated_probability: false, reward_component: 0.542, risk_component: 0.056, risk_adjusted_utility: 0.486, valuation_disclaimer: 'Heuristic sample valuation' },
            },
            {
              action_id: 'ACT-RW-DIAG',
              action_family: 'PASS',
              label: 'Diagonal Switch to RW',
              target_slot: 'RW',
              target_xy_m: [74.0, 11.0],
              feasibility: 'OPEN',
              epistemic_tag: 'SYNTHETIC_FIXTURE',
              is_observed_choice: false,
              passing_eval: { distance_m: 26.4, point_to_segment_clearance_m: 4.1, dynamic_interception_margin_sec: 0.41, receiver_space_radius_m: 5.8, xt_delta: 0.118, turnover_exposure: 0.14 },
              value_breakdown: { valuation_stage: 'HEURISTIC', is_calibrated_probability: false, reward_component: 0.448, risk_component: 0.089, risk_adjusted_utility: 0.359, valuation_disclaimer: 'Heuristic sample valuation' },
            },
            {
              action_id: 'ACT-ST-BLOCKED',
              action_family: 'PASS',
              label: 'Vertical Pass to Marked ST',
              target_slot: 'ST',
              target_xy_m: [81.0, 35.0],
              feasibility: 'CONTESTED',
              epistemic_tag: 'SYNTHETIC_FIXTURE',
              is_observed_choice: true,
              passing_eval: { distance_m: 20.0, point_to_segment_clearance_m: 0.4, dynamic_interception_margin_sec: -0.18, receiver_space_radius_m: 1.9, xt_delta: 0.162, turnover_exposure: 0.52 },
              value_breakdown: { valuation_stage: 'HEURISTIC', is_calibrated_probability: false, reward_component: 0.491, risk_component: 0.277, risk_adjusted_utility: 0.214, valuation_disclaimer: 'Heuristic sample valuation' },
            },
          ],
        },
        regret_estimate: 0.272,
      }
      setAdHocWindow(demoWin)
      setSelectedId('DEMO-SAMPLE-WINDOW')
      setBlindPickId('')
      notify('info', 'Loaded read-only SYNTHETIC_FIXTURE decision demo window.')
      return
    }
    setLoading(true)
    try {
      const res = await api.post<{
        pre_action_state: DecisionWindowItem['pre_action_state']
        counterfactual_comparison: DecisionWindowItem['counterfactual_comparison']
      }>('/api/phase41/evaluate-snapshot', {
        ...DEMO_SNAPSHOT_PAYLOAD,
        reveal_outcome: !hideOutcome,
      })
      const synthWin: DecisionWindowItem = {
        window_id: 'SNAPSHOT-PREVIEW',
        match_id: DEMO_SNAPSHOT_PAYLOAD.match_id,
        decision_type: 'ATTACKING_PASS',
        status: res.counterfactual_comparison.status,
        provenance: 'IMPORTED_MATCH_TRACE',
        action_timestamp_sec: 28.4,
        calibration_state: 'GOOD',
        coverage_pct: 91.0,
        pre_action_state: res.pre_action_state,
        post_action_outcome: null,
        counterfactual_comparison: res.counterfactual_comparison,
        regret_estimate: res.counterfactual_comparison.regret_estimate,
      }
      setAdHocWindow(synthWin)
      setSelectedId('SNAPSHOT-PREVIEW')
      setBlindPickId('')
      notify('ok', 'Evaluated pre-action decision snapshot strictly before post-action outcomes.')
    } catch (e: any) {
      notify('bad', e?.detail || 'Failed to evaluate snapshot.')
    } finally {
      setLoading(false)
    }
  }

  async function handleExportScenario(windowId: string) {
    if (!user || windowId === 'SNAPSHOT-PREVIEW' || windowId === 'DEMO-SAMPLE-WINDOW') {
      notify('info', 'Sign in with an evaluated real match window to export training scenarios.')
      return
    }
    setSavingScenario(true)
    try {
      await api.post(`/api/phase41/windows/${windowId}/to-scenario`, {})
      notify('ok', 'Saved as multi-answer blind-review Decision Training Scenario in Academy.')
    } catch (e: any) {
      notify('bad', e?.detail || 'Could not convert decision window to training scenario.')
    } finally {
      setSavingScenario(false)
    }
  }

  async function handleSaveAnnotation(win: DecisionWindowItem) {
    if (!user || !blindPickId) return
    try {
      await api.post('/api/phase41/annotations', {
        window_id: win.window_id,
        match_id: win.match_id,
        annotator_role: 'PLAYER_SELF',
        best_option_id: blindPickId,
        defensible_option_ids: [blindPickId],
        blind_review_completed: hideOutcome,
      })
      notify('ok', `Saved blind-review preference for ${blindPickId}.`)
    } catch (e: any) {
      notify('bad', e?.detail || 'Failed to save annotation.')
    }
  }

  const allItems = useMemo(() => (adHocWindow ? [adHocWindow, ...windows] : windows), [adHocWindow, windows])
  const activeWin = useMemo(() => allItems.find(w => w.window_id === selectedId) || allItems[0] || null, [allItems, selectedId])

  const ball = activeWin?.pre_action_state?.pre_action_ball
  const players = activeWin?.pre_action_state?.pre_action_players || []
  const comp = activeWin?.counterfactual_comparison
  const candidates = comp?.candidates || []

  useCopilotRouteContext({
    route_name: 'DECISION_LAB',
    game_version: 'FC27',
    match_id: activeWin?.match_id || null,
    decision_id: activeWin?.window_id || null,
    visible_timestamp_sec: activeWin?.action_timestamp_sec ?? null,
  })

  return (
    <div className="dlab-page">
      <header className="dlab-hero">
        <div className="row space-between align-center flex-wrap gap05">
          <div>
            <EpistemicChip kind="modelled" label="Pre-Action Counterfactual Engine" />
            <h1 className="mt03 mb02">Decision Replay Lab &amp; Counterfactual Review</h1>
            <p className="text-secondary tiny mb0" style={{ maxWidth: '70ch' }}>
              Decision quality is scored strictly BEFORE the action happens — zero hindsight leakage, bounded kinematic uncertainty, and explicit separation of outcomes vs choices.
            </p>
          </div>
          <div className="row gap05 flex-wrap align-center">
            <button
              type="button"
              className="btn ghost sm"
              onClick={() => openCopilot({
                prompt: activeWin
                  ? `Explain why ${comp?.best_alternative_label || 'the top counterfactual option'} outperforms the observed choice in window ${activeWin.window_id} (${activeWin.action_timestamp_sec}s).`
                  : 'How does Decision Replay Lab separate pre-action decision quality from outcomes?',
              })}
            >
              <StadiumIcon name="coach" size={14} />
              <span>Ask Co-Pilot</span>
            </button>
            <button
              type="button"
              className={`btn sm ${hideOutcome ? '' : 'ghost'}`}
              onClick={() => setHideOutcome(prev => !prev)}
            >
              {hideOutcome ? 'Blind Review ON (Outcome Hidden)' : 'Outcome Visible (Blind Review OFF)'}
            </button>
            <button type="button" className="btn ghost sm" onClick={runQuickSnapshotDemo} disabled={loading}>
              Evaluate Pre-Action Snapshot
            </button>
            <Link className="btn ghost sm" to="/coach">Open Personal Coach →</Link>
          </div>
        </div>
      </header>

      {!user && (
        <div className="callout info">
          <div className="row space-between align-center flex-wrap gap05">
            <span>
              <strong>Guest Preview Mode:</strong> <Link to="/login">Log in</Link> or <Link to="/signup">create an account</Link> to inspect uploaded match windows, or preview an interactive read-only decision fixture now.
            </span>
            <button type="button" className="btn sm primary" onClick={runQuickSnapshotDemo}>
              Load Sample Decision Fixture
            </button>
          </div>
        </div>
      )}

      <div className="dlab-grid">
        {/* LEFT COLUMN: 2D PITCH + PASSING LANES / COUNTERFACTUAL ARROWS */}
        <section className="dlab-card" aria-label="Pre-Action Tactical Pitch Radar">
          <div className="row space-between align-center flex-wrap gap05">
            <div>
              <strong>Pre-Action Spatial Geometry ({activeWin ? `${activeWin.action_timestamp_sec}s · Zone ${activeWin.pre_action_state?.pitch_zone ?? '?'}` : 'No Window Loaded'})</strong>
              <div className="tiny text-muted">
                Tags: <span className="badge sm outline font-mono">OBSERVED Coords</span>{' '}
                <span className="badge sm cyan font-mono">MODELLED Utility</span>{' '}
                <span className="badge sm warn font-mono">HYPOTHETICAL Alternatives</span>
              </div>
            </div>
            {activeWin && (
              <span className="badge sm lime font-mono">
                Cov {activeWin.coverage_pct.toFixed(0)}% · {activeWin.calibration_state}
              </span>
            )}
          </div>

          <div className="dlab-pitch-wrap">
            <svg viewBox="0 0 105 68" className="w-full" style={{ display: 'block', borderRadius: 6, background: '#0e241b' }} role="img" aria-label="105x68 meter pre-action pitch">
              <defs>
                <marker id="dlab-arrow-best" markerWidth="4" markerHeight="4" refX="3.2" refY="2" orient="auto">
                  <path d="M0,0 L4,2 L0,4 Z" fill="#b8f57a" />
                </marker>
                <marker id="dlab-arrow-obs" markerWidth="4" markerHeight="4" refX="3.2" refY="2" orient="auto">
                  <path d="M0,0 L4,2 L0,4 Z" fill="#fbbf24" />
                </marker>
                <marker id="dlab-arrow-alt" markerWidth="3.5" markerHeight="3.5" refX="2.8" refY="1.75" orient="auto">
                  <path d="M0,0 L3.5,1.75 L0,3.5 Z" fill="#38bdf8" />
                </marker>
              </defs>
              {/* Pitch markings */}
              <rect x={0} y={0} width={105} height={68} fill="#0e241b" stroke="#2d5a42" strokeWidth={0.5} />
              <line x1={52.5} y1={0} x2={52.5} y2={68} stroke="#2d5a42" strokeWidth={0.4} />
              <circle cx={52.5} cy={34} r={9.15} fill="none" stroke="#2d5a42" strokeWidth={0.4} />
              <rect x={0} y={13.84} width={16.5} height={40.32} fill="none" stroke="#2d5a42" strokeWidth={0.4} />
              <rect x={88.5} y={13.84} width={16.5} height={40.32} fill="none" stroke="#2d5a42" strokeWidth={0.4} />

              {/* Candidate passing / carry / shot directional arrows */}
              {ball?.x_m != null && ball?.y_m != null && candidates.slice(0, 6).map(cand => {
                if (!cand.target_xy_m) return null
                const segLen = Math.hypot(cand.target_xy_m[0] - ball.x_m!, cand.target_xy_m[1] - ball.y_m!)
                const isBest = cand.action_id === comp?.best_alternative_id
                const isObs = cand.action_id === comp?.observed_action_id
                if (segLen < 1.2) {
                  return isBest || isObs ? (
                    <circle
                      key={cand.action_id}
                      cx={ball.x_m}
                      cy={68 - (ball.y_m ?? 34)}
                      r={3.2}
                      fill="none"
                      stroke={isBest ? '#b8f57a' : '#fbbf24'}
                      strokeWidth={0.5}
                      strokeDasharray="1.2 1.0"
                      opacity={0.85}
                    />
                  ) : null
                }
                const stroke = isBest ? '#b8f57a' : isObs ? '#fbbf24' : '#38bdf8'
                const markerEnd = isBest ? 'url(#dlab-arrow-best)' : isObs ? 'url(#dlab-arrow-obs)' : 'url(#dlab-arrow-alt)'
                const op = isBest || isObs ? 0.92 : 0.48
                return (
                  <line
                    key={cand.action_id}
                    x1={ball.x_m}
                    y1={68 - (ball.y_m ?? 34)}
                    x2={cand.target_xy_m[0]}
                    y2={68 - cand.target_xy_m[1]}
                    stroke={stroke}
                    strokeWidth={isBest ? 0.8 : isObs ? 0.65 : 0.42}
                    strokeDasharray={isObs && !isBest ? '1.8 1.2' : undefined}
                    markerEnd={markerEnd}
                    opacity={op}
                  />
                )
              })}

              {/* Pre-action players with team-separated label offsets to avoid collisions */}
              {players.map(p => {
                const isHome = p.team === 'HOME'
                const isCarrier = p.track_id === ball?.carrier_track_id
                const labelY = isHome ? 68 - p.y_m - 2.3 : 68 - p.y_m + 3.6
                return (
                  <g key={p.track_id}>
                    <circle
                      cx={p.x_m}
                      cy={68 - p.y_m}
                      r={isCarrier ? 2.0 : 1.5}
                      fill={isHome ? '#b8f57a' : '#f87171'}
                      stroke={isCarrier ? '#ffffff' : '#0b141e'}
                      strokeWidth={isCarrier ? 0.55 : 0.35}
                    />
                    <text
                      x={p.x_m}
                      y={labelY}
                      fontSize="2.1"
                      fill="#e2e8f0"
                      textAnchor="middle"
                    >
                      {p.player_slot}
                    </text>
                  </g>
                )
              })}

              {/* Ball */}
              {ball?.x_m != null && ball?.y_m != null && (
                <circle cx={ball.x_m} cy={68 - ball.y_m} r={1.0} fill="#ffffff" stroke="#38bdf8" strokeWidth={0.4} />
              )}
            </svg>
          </div>

          <div className="row space-between align-center flex-wrap gap05 tiny">
            <span className="row align-center gap05 flex-wrap">
              <span>Legend:</span>
              <span className="row align-center gap02">
                <svg width="18" height="6" aria-hidden="true"><line x1="0" y1="3" x2="18" y2="3" stroke="#b8f57a" strokeWidth="2.2" /></svg>
                <strong className="text-lime">Green solid</strong> = Best Counterfactual
              </span>
              <span className="row align-center gap02">
                <svg width="18" height="6" aria-hidden="true"><line x1="0" y1="3" x2="18" y2="3" stroke="#fbbf24" strokeWidth="2.2" strokeDasharray="4 2" /></svg>
                <strong style={{ color: '#fbbf24' }}>Amber dashed</strong> = Observed Choice
              </span>
            </span>
            {activeWin && activeWin.window_id !== 'SNAPSHOT-PREVIEW' && (
              <div className="row gap05">
                {blindPickId && (
                  <button type="button" className="btn ghost sm" onClick={() => handleSaveAnnotation(activeWin)}>
                    Save Blind Pick ({blindPickId})
                  </button>
                )}
                <button
                  type="button"
                  className="btn sm"
                  onClick={() => handleExportScenario(activeWin.window_id)}
                  disabled={savingScenario || activeWin.status !== 'EVALUATED'}
                >
                  {savingScenario ? 'Saving…' : 'Save as Training Exercise'}
                </button>
              </div>
            )}
          </div>
        </section>

        {/* RIGHT COLUMN: DECISION WINDOWS + BLIND PICK + CANDIDATE TABLE */}
        <section className="dlab-card" aria-label="Decision Windows & Counterfactual Table">
          <div className="row space-between align-center">
            <strong>Detected Pre-Action Windows ({allItems.length})</strong>
            <button type="button" className="btn ghost sm" onClick={() => refreshLab(!hideOutcome)} disabled={loading}>
              Refresh
            </button>
          </div>

          <div className="dlab-window-list">
            {allItems.length === 0 ? (
              <p className="tiny text-muted mb0">
                No match decision windows persisted yet. Click <strong>Evaluate Pre-Action Snapshot</strong> above or analyze an imported match trace via Gameplay Studio.
              </p>
            ) : (
              allItems.map(w => (
                <button
                  key={w.window_id}
                  type="button"
                  className={`dlab-window-item ${activeWin?.window_id === w.window_id ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedId(w.window_id)
                    setBlindPickId('')
                  }}
                >
                  <div>
                    <div className="strong tiny">{w.window_id} · {w.decision_type}</div>
                    <div className="tiny text-muted">{w.action_timestamp_sec}s · {w.provenance}</div>
                  </div>
                  <span className={`badge sm font-mono ${(w.regret_estimate ?? 0) >= 0.08 ? 'warn' : 'lime'}`}>
                    {w.status === 'EVALUATED' ? `Regret ${(w.regret_estimate ?? 0).toFixed(3)}` : 'ABSTAINED'}
                  </span>
                </button>
              ))
            )}
          </div>

          {activeWin && comp && (
            <>
              <div className="callout info small">
                {comp.status === 'EVALUATED' ? (
                  <>
                    <strong>Decision Quality vs Outcome:</strong>{' '}
                    {hideOutcome
                      ? 'Outcome hidden during Blind Review. Select what YOU would play before revealing outcome.'
                      : activeWin.post_action_outcome?.outcome_label
                        ? `Observed Post-Action Outcome: ${activeWin.post_action_outcome.outcome_label} (scoring remains strictly independent of outcome).`
                        : 'Post-action outcome tracking frame unavailable for this isolated frame.'}
                    <div className="mt02 tiny text-secondary">{comp.tactical_explanation}</div>
                    {comp.capability_constraint_note && (
                      <div className="mt02 tiny text-cyan">{comp.capability_constraint_note}</div>
                    )}
                  </>
                ) : (
                  <>
                    <strong>Abstained Safely:</strong> {comp.abstain_reason}
                  </>
                )}
              </div>

              {comp.status === 'EVALUATED' && (
                <div style={{ overflowX: 'auto' }}>
                  <table className="dlab-cand-table">
                    <thead>
                      <tr>
                        <th>Pick</th>
                        <th>Action Option</th>
                        <th>Reward</th>
                        <th>Risk</th>
                        <th>Q Utility</th>
                        <th>Margin (M)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {candidates.slice(0, 7).map(c => {
                        const isBest = c.action_id === comp.best_alternative_id
                        const isObs = c.action_id === comp.observed_action_id
                        const margin = c.passing_eval?.dynamic_interception_margin_sec
                        return (
                          <tr key={c.action_id} className={`dlab-cand-row ${isBest ? 'best' : isObs ? 'observed' : ''}`}>
                            <td>
                              <input
                                type="radio"
                                name="blind-pick"
                                checked={blindPickId === c.action_id}
                                onChange={() => setBlindPickId(c.action_id)}
                                aria-label={`Pick ${c.label}`}
                              />
                            </td>
                            <td>
                              <div className="strong">{c.label}</div>
                              <div className="tiny text-muted">
                                {c.epistemic_tag}
                                {isBest ? ' · Best Counterfactual' : ''}
                                {isObs ? ' · Observed Choice' : ''}
                              </div>
                            </td>
                            <td className="font-mono">{c.value_breakdown?.reward_component?.toFixed(3) ?? '—'}</td>
                            <td className="font-mono">{c.value_breakdown?.risk_component?.toFixed(3) ?? '—'}</td>
                            <td className="font-mono strong">{c.value_breakdown?.risk_adjusted_utility?.toFixed(3) ?? '—'}</td>
                            <td className="font-mono">{margin != null ? `${margin >= 0 ? '+' : ''}${margin.toFixed(2)}s` : '—'}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {comp.uncertainty && (
                <div className="row space-between align-center flex-wrap gap05 tiny">
                  <span>
                    MC Perturbation Bounds ({comp.uncertainty.monte_carlo_samples} draws):{' '}
                    <strong className="font-mono">[{comp.uncertainty.q_p10.toFixed(3)}, {comp.uncertainty.q_p90.toFixed(3)}]</strong>{' '}
                    · Rank Stability <strong className="font-mono">{(comp.uncertainty.rank_stability_rate * 100).toFixed(0)}%</strong>
                    {comp.uncertainty.indistinguishable_from_best ? ' · Indistinguishable within sensor noise' : ''}
                  </span>
                  <button type="button" className="btn ghost sm" onClick={() => setShowMath(m => !m)}>
                    {showMath ? 'Hide Math' : 'Inspect Model Math'}
                  </button>
                </div>
              )}

              {showMath && (
                <div className="dlab-math-box">
                  <div>Q_heuristic(s, a) = Reward(xT_delta, M_interception, Receiver_Space) - Risk(Turnover_Exposure, Rest_Defense)</div>
                  <div>R(s, a) = max_a&apos; Q(s, a&apos;) - Q(s, a) &ge; 0 (Pre-Action Only; is_calibrated_probability=false)</div>
                </div>
              )}
            </>
          )}
        </section>
      </div>

      {/* FOOTBALL IQ 10-DIMENSION PANEL */}
      <section className="dlab-card" aria-label="10-Dimension Football IQ Profile">
        <div className="row space-between align-center flex-wrap gap05">
          <div>
            <strong>10-Dimension Football IQ Profile</strong>
            <p className="tiny text-muted mb0">
              Strictly excludes SYNTHETIC_FIXTURE windows ({footballIq?.synthetic_excluded_count ?? 0} excluded). Separates tendency, technical execution error, and pre-action decision quality.
            </p>
          </div>
          <span className="badge sm cyan font-mono">
            {footballIq?.overall_football_iq != null
              ? `Overall IQ: ${footballIq.overall_football_iq}/100 (${footballIq.confidence})`
              : 'Cold Start (0 real decision windows)'}
          </span>
        </div>

        <div className="dlab-iq-grid">
          {(footballIq?.dimensions || []).map(dim => (
            <div key={dim.dimension} className="dlab-iq-cell">
              <div className="row space-between align-center">
                <strong className="tiny">{dim.label}</strong>
                <span className={`badge sm font-mono ${dim.score_0_100 != null ? 'lime' : 'outline'}`}>
                  {dim.score_0_100 != null ? `${dim.score_0_100}` : 'N/A'}
                </span>
              </div>
              <div className="tiny text-muted mt02">
                Conf: {dim.confidence} · Clusters: {dim.cluster_count} ({dim.sample_windows} win)
              </div>
              {dim.score_0_100 != null && (
                <div className="tiny text-secondary mt02">
                  Regret: {dim.mean_regret?.toFixed(3) ?? '—'} · Exec Err: {dim.execution_error_rate != null ? `${(dim.execution_error_rate * 100).toFixed(0)}%` : 'N/A'}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
