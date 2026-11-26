import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useSession } from '../state/session'
import { useCopilot, useCopilotRouteContext } from '../state/copilot'
import { EpistemicChip } from '../components/ui/StadiumPrimitives'
import { StadiumInput, StadiumSelect } from '../components/StadiumControls'
import { StadiumIcon } from '../components/StadiumIcons'
import './TacticalLab.css'

type LabTab = 'OVERVIEW' | 'SNAPSHOTS' | 'EXPERIMENTS' | 'ADVISORY' | 'META_CV'

const ALL_FORMATIONS = [
  '4-2-3-1',
  '4-3-3',
  '4-4-2',
  '4-3-2-1',
  '4-5-1',
  '4-2-2-2',
  '4-1-2-1-2',
  '3-5-2',
  '3-4-2-1',
  '3-4-3',
  '5-3-2',
  '5-2-1-2',
]

const EXPERIMENT_TYPES = [
  { value: 'FORMATION_COMPARISON', label: 'Formation Comparison (e.g. 4-3-3 vs 4-2-3-1)' },
  { value: 'TACTICAL_PRESET_COMPARISON', label: 'Tactical Preset / Style Comparison' },
  { value: 'PLAYER_ROLE_FOCUS_COMPARISON', label: 'Player Role & Focus Comparison' },
  { value: 'DEFENSIVE_HEIGHT_PRESS_COMPARISON', label: 'Defensive Line Height / Press Comparison' },
  { value: 'BUILD_UP_STYLE_COMPARISON', label: 'Build-Up Style Comparison' },
  { value: 'PLAYER_PARTNERSHIP_COMPARISON', label: 'Player Partnership Synergy Test' },
  { value: 'SINGLE_POSITION_REPLACEMENT', label: 'Single-Position Card Isolation Test' },
  { value: 'PERSONAL_PLAYSTYLE_COMPATIBILITY', label: 'Personal Playstyle Compatibility Test' },
]

const DESIGN_TYPES = [
  { value: 'CROSSOVER_ABBA', label: 'Counterbalanced Crossover (ABBA)' },
  { value: 'RANDOMIZED_BLOCKED', label: 'Seeded Randomized Blocked (A/B)' },
  { value: 'MATCHED_COMPARISON', label: 'Matched Opponent Stratification' },
  { value: 'DESCRIPTIVE_BEFORE_AFTER', label: 'Descriptive Before-After' },
]

const METRIC_OPTIONS = [
  { value: 'conceded_transition_rate', label: 'Conceded Transition Rate (lower is better)' },
  { value: 'risky_central_pass_rate', label: 'Risky Central Pass Rate (lower is better)' },
  { value: 'defensive_compactness', label: 'Defensive Compactness (higher is better)' },
  { value: 'defensive_transition_management', label: 'Transition Management (higher is better)' },
  { value: 'central_progression', label: 'Central Progression Share (higher is better)' },
  { value: 'chance_creation', label: 'Chance Creation xT Proxy (higher is better)' },
  { value: 'possession_share', label: 'Possession Share (higher is better)' },
  { value: 'pressing_intensity', label: 'Pressing Intensity (higher is better)' },
]

const SQUAD_OBJECTIVES = [
  { value: 'PERSONALIZED', label: 'Personalized (DNA + Weakness Coverage)' },
  { value: 'BALANCED', label: 'Balanced All-Around XI' },
  { value: 'POSSESSION', label: 'Possession & Central Triangle Control' },
  { value: 'COUNTER_ATTACK', label: 'Fast Counter-Attack Transitions' },
  { value: 'PRESSING', label: 'High Press & Stamina Sustainability' },
  { value: 'ATTACKING', label: 'Attacking Ceiling' },
  { value: 'DEFENSIVE', label: 'Rest-Defense & Structural Compactness' },
]

function chipKindForGrade(grade?: string) {
  if (grade === 'CONTROLLED_EXPERIMENT_EVIDENCE') return 'observed'
  if (grade === 'OBSERVED_ASSOCIATION') return 'observed'
  if (grade === 'THEORETICAL_SUITABILITY') return 'hypothetical'
  return 'neutral'
}

export default function TacticalLab() {
  const { user, gameVersion, notify } = useSession()
  const { openCopilot } = useCopilot()

  const [tab, setTab] = useState<LabTab>('OVERVIEW')
  const [patch, setPatch] = useState('PATCH_1.04')
  const [loading, setLoading] = useState(false)

  const [snapshots, setSnapshots] = useState<Record<string, any>[]>([])
  const [fingerprints, setFingerprints] = useState<Record<string, any>[]>([])
  const [experiments, setExperiments] = useState<Record<string, any>[]>([])
  const [matches, setMatches] = useState<Record<string, any>[]>([])
  const [formations, setFormations] = useState<Record<string, any> | null>(null)
  const [personalMeta, setPersonalMeta] = useState<Record<string, any> | null>(null)
  const [feedbackList, setFeedbackList] = useState<Record<string, any>[]>([])
  const [cvStatus, setCvStatus] = useState<Record<string, any> | null>(null)
  const [cvCalibration, setCvCalibration] = useState<Record<string, any> | null>(null)

  // Snapshot creation & diff state
  const [snapLabel, setSnapLabel] = useState('Double-Pivot 4-2-3-1 Control')
  const [snapFormation, setSnapFormation] = useState('4-2-3-1')
  const [snapProfile, setSnapProfile] = useState('BALANCED')
  const [snapBuildUp, setSnapBuildUp] = useState('BALANCED')
  const [snapDefense, setSnapDefense] = useState('BALANCED')
  const [snapLineHeight, setSnapLineHeight] = useState('55')
  const [snapWidth, setSnapWidth] = useState('50')
  const [snapshotDiff, setSnapshotDiff] = useState<Record<string, any> | null>(null)

  // Experiment creation, suggestion, preview & sample planner
  const [selectedExpId, setSelectedExpId] = useState<string>('')
  const [expTitle, setExpTitle] = useState('4-2-3-1 Holding vs 4-3-3 Rest Defense')
  const [expHypothesis, setExpHypothesis] = useState('Double pivot lowers transition exposure rate on counters without dropping progression.')
  const [expType, setExpType] = useState('FORMATION_COMPARISON')
  const [expDesignType, setExpDesignType] = useState('CROSSOVER_ABBA')
  const [expMetric, setExpMetric] = useState('conceded_transition_rate')
  const [armASnap, setArmASnap] = useState('')
  const [armBSnap, setArmBSnap] = useState('')
  const [linkMatchId, setLinkMatchId] = useState('')
  const [linkArm, setLinkArm] = useState<'BASELINE_A' | 'VARIANT_B'>('BASELINE_A')
  const [expSuggestion, setExpSuggestion] = useState<Record<string, any> | null>(null)
  const [expPreview, setExpPreview] = useState<Record<string, any> | null>(null)
  const [samplePlan, setSamplePlan] = useState<Record<string, any> | null>(null)
  const [uncertaintyBreakdown, setUncertaintyBreakdown] = useState<Record<string, any> | null>(null)

  // Formation comparator, multi-objective squad optimizer & counterfactuals
  const [cmpFormA, setCmpFormA] = useState('4-3-3')
  const [cmpFormB, setCmpFormB] = useState('4-2-3-1')
  const [formationCmp, setFormationCmp] = useState<Record<string, any> | null>(null)
  const [optFormation, setOptFormation] = useState('4-2-3-1')
  const [optObjective, setOptObjective] = useState('PERSONALIZED')
  const [squadOptResult, setSquadOptResult] = useState<Record<string, any> | null>(null)
  const [counterfactual, setCounterfactual] = useState<Record<string, any> | null>(null)

  // Replacement triage & closed-loop feedback
  const [triageSlot, setTriageSlot] = useState('CDM')
  const [triagePlayer, setTriagePlayer] = useState('')
  const [triageResult, setTriageResult] = useState<Record<string, any> | null>(null)
  const [fbNote, setFbNote] = useState('')

  const selectedExp = experiments.find(e => e.experiment_id === selectedExpId) || experiments[0] || null
  const activeFp = fingerprints[0] || null

  useCopilotRouteContext({
    route_name: 'TACTICAL_LAB',
    game_version: gameVersion === 'FC26' ? 'FC26' : 'FC27',
    active_formation: selectedExp?.analysis?.arm_b?.formation || snapFormation,
    active_tactical_profile: snapProfile,
    tactical_snapshot_id: armBSnap || armASnap || snapshots[0]?.snapshot_id || null,
    experiment_id: selectedExp?.experiment_id || null,
    active_filters: { game_patch: patch },
  })

  async function loadAll() {
    setLoading(true)
    try {
      const cvRes = await api.get<Record<string, any>>('/api/phase43/cv/status').catch(() => null)
      setCvStatus(cvRes)
      if (!user) return
      const [snapsRes, fpsRes, expsRes, matRes, formRes, metaRes, fbRes] = await Promise.all([
        api.get<{ items: Record<string, any>[] }>(`/api/phase43/snapshots?game_version=${gameVersion}`),
        api.get<{ items: Record<string, any>[] }>('/api/phase43/fingerprints?limit=20'),
        api.get<{ items: Record<string, any>[] }>(`/api/phase43/experiments?game_version=${gameVersion}`),
        api.get<{ items: Record<string, any>[] }>(`/api/phase40/matches?game_version=${gameVersion}&exclude_synthetic=true&limit=40`),
        api.get<Record<string, any>>(`/api/phase43/recommendations/formations?game_version=${gameVersion}&game_patch=${encodeURIComponent(patch)}&top_k=12`),
        api.get<Record<string, any>>(`/api/phase43/personal-meta?game_version=${gameVersion}&game_patch=${encodeURIComponent(patch)}`),
        api.get<{ items: Record<string, any>[] }>(`/api/phase43/feedback?game_version=${gameVersion}&limit=15`).catch(() => ({ items: [] })),
      ])
      setSnapshots(snapsRes.items || [])
      if ((snapsRes.items || []).length >= 1 && !armASnap) setArmASnap(snapsRes.items[0].snapshot_id)
      if ((snapsRes.items || []).length >= 2 && !armBSnap) setArmBSnap(snapsRes.items[1].snapshot_id)
      setFingerprints(fpsRes.items || [])
      setExperiments(expsRes.items || [])
      if ((expsRes.items || []).length > 0 && !selectedExpId) setSelectedExpId(expsRes.items[0].experiment_id)
      setMatches(matRes.items || [])
      if ((matRes.items || []).length > 0 && !linkMatchId) setLinkMatchId(matRes.items[0].match_id)
      setFormations(formRes)
      setPersonalMeta(metaRes)
      setFeedbackList(fbRes.items || [])
    } catch {
      notify('bad', 'Unable to load Tactical Lab state.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAll()
  }, [user?.id, gameVersion, patch])

  async function handleCreateSnapshot(e: React.FormEvent) {
    e.preventDefault()
    if (!user) return
    try {
      const created = await api.post<Record<string, any>>('/api/phase43/snapshots', {
        label: snapLabel,
        game_version: gameVersion === 'FC26' ? 'FC26' : 'FC27',
        game_patch: patch,
        formation: snapFormation,
        tactical_profile: snapProfile,
        build_up_style: snapBuildUp || null,
        defensive_approach: snapDefense || null,
        line_height: snapLineHeight ? Number(snapLineHeight) : null,
        width_setting: snapWidth ? Number(snapWidth) : null,
      })
      notify('ok', `Saved immutable snapshot ${created.snapshot_id} (v${created.version_number}).`)
      loadAll()
    } catch (err: any) {
      notify('bad', err?.detail || 'Snapshot creation failed.')
    }
  }

  async function handleBuildFingerprint(mid: string) {
    if (!user || !mid) return
    try {
      await api.post('/api/phase43/fingerprints/build', {
        match_id: mid,
        snapshot_id: armASnap || snapshots[0]?.snapshot_id || null,
      })
      notify('ok', `Built 4-phase Tactical Fingerprint for ${mid}.`)
      loadAll()
    } catch (err: any) {
      notify('bad', err?.detail || 'Fingerprint build failed.')
    }
  }

  async function handleDiffSnapshots() {
    if (!user || !armASnap || !armBSnap) return
    try {
      const res = await api.post<Record<string, any>>('/api/phase43/snapshots/diff', {
        baseline_snapshot_id: armASnap,
        variant_snapshot_id: armBSnap,
      })
      setSnapshotDiff(res)
    } catch (err: any) {
      notify('bad', err?.detail || 'Snapshot diff failed.')
    }
  }

  async function handleSuggestExperiment() {
    if (!user) return
    try {
      const res = await api.get<Record<string, any>>(`/api/phase43/experiments/suggest?game_version=${gameVersion}&game_patch=${encodeURIComponent(patch)}`)
      setExpSuggestion(res)
      if (res.experiment_type) setExpType(res.experiment_type)
      if (res.suggested_primary_metric) setExpMetric(res.suggested_primary_metric)
      if (res.hypothesis) setExpHypothesis(res.hypothesis)
      notify('ok', `Loaded suggestion targeting ${res.detected_focus}.`)
    } catch (err: any) {
      notify('bad', err?.detail || 'Could not generate suggestion.')
    }
  }

  async function handlePreviewExperiment() {
    if (!user || !armASnap || !armBSnap) {
      notify('info', 'Select distinct Arm A and Arm B snapshots first.')
      return
    }
    try {
      const res = await api.post<Record<string, any>>('/api/phase43/experiments/preview', {
        title: expTitle,
        hypothesis: expHypothesis,
        experiment_type: expType,
        design_type: expDesignType,
        game_version: gameVersion === 'FC26' ? 'FC26' : 'FC27',
        baseline_patch: patch,
        baseline_snapshot_id: armASnap,
        variant_snapshot_id: armBSnap,
        primary_metric: expMetric,
      })
      setExpPreview(res)
      const ss = await api.get<Record<string, any>>('/api/phase43/experiments/sample-size?expected_delta=0.08&pooled_sd=0.14').catch(() => null)
      if (ss) setSamplePlan(ss)
    } catch (err: any) {
      notify('bad', err?.detail || 'Preview validation failed.')
    }
  }

  async function handleCreateExperiment(e: React.FormEvent) {
    e.preventDefault()
    if (!user || !armASnap || !armBSnap) {
      notify('info', 'Select distinct Baseline (A) and Variant (B) snapshots first.')
      return
    }
    try {
      const res = await api.post<Record<string, any>>('/api/phase43/experiments', {
        title: expTitle,
        hypothesis: expHypothesis,
        experiment_type: expType,
        design_type: expDesignType,
        game_version: gameVersion === 'FC26' ? 'FC26' : 'FC27',
        baseline_patch: patch,
        baseline_snapshot_id: armASnap,
        variant_snapshot_id: armBSnap,
        primary_metric: expMetric,
      })
      setSelectedExpId(res.experiment_id)
      setExpPreview(null)
      notify('ok', `Created experiment ${res.experiment_id}.`)
      loadAll()
    } catch (err: any) {
      notify('bad', err?.detail || 'Could not create experiment.')
    }
  }

  async function handleUpdateExpStatus(expId: string, status: string) {
    if (!user) return
    try {
      await api.patch(`/api/phase43/experiments/${encodeURIComponent(expId)}/status`, {
        status,
        reason: `User transitioned workflow to ${status}`,
      })
      notify('ok', `Experiment transitioned to ${status}.`)
      loadAll()
    } catch (err: any) {
      notify('bad', err?.detail || 'Status transition failed.')
    }
  }

  async function handleLinkMatch() {
    if (!user || !selectedExp || !linkMatchId) return
    try {
      await api.post(`/api/phase43/experiments/${encodeURIComponent(selectedExp.experiment_id)}/matches`, {
        match_id: linkMatchId,
        arm: linkArm,
        match_order: (selectedExp.linked_matches || []).length + 1,
      })
      notify('ok', `Linked match ${linkMatchId} to ${linkArm}.`)
      loadAll()
    } catch (err: any) {
      notify('bad', err?.detail || 'Could not link match.')
    }
  }

  async function handleAnalyzeExperiment(expId: string) {
    if (!user) return
    try {
      await api.post(`/api/phase43/experiments/${encodeURIComponent(expId)}/analyze`, {})
      const unc = await api.get<Record<string, any>>(`/api/phase43/experiments/${encodeURIComponent(expId)}/uncertainty`).catch(() => null)
      setUncertaintyBreakdown(unc)
      notify('ok', 'Statistical & Bayesian analysis updated.')
      loadAll()
    } catch (err: any) {
      notify('bad', err?.detail || 'Analysis failed.')
    }
  }

  async function handleCompareFormations() {
    if (!user) return
    try {
      const res = await api.get<Record<string, any>>(
        `/api/phase43/formations/compare?formation_a=${encodeURIComponent(cmpFormA)}&formation_b=${encodeURIComponent(cmpFormB)}&game_version=${gameVersion}&game_patch=${encodeURIComponent(patch)}`,
      )
      setFormationCmp(res)
    } catch (err: any) {
      notify('bad', err?.detail || 'Formation comparison failed.')
    }
  }

  async function handleOptimizeSquad() {
    if (!user) return
    try {
      const res = await api.post<Record<string, any>>('/api/phase43/squads/optimize', {
        game_version: gameVersion === 'FC26' ? 'FC26' : 'FC27',
        game_patch: patch,
        formation: optFormation,
        objective: optObjective,
        max_alternatives: 3,
      })
      setSquadOptResult(res)
      notify('ok', `Optimized ${optFormation} XI (${optObjective}).`)
    } catch (err: any) {
      notify('bad', err?.detail || 'Squad optimization failed.')
    }
  }

  async function handleCompareCounterfactual() {
    if (!user || !armASnap || !armBSnap) return
    try {
      const res = await api.post<Record<string, any>>('/api/phase43/counterfactuals/compare', {
        baseline_snapshot_id: armASnap,
        variant_snapshot_id: armBSnap,
      })
      setCounterfactual(res)
    } catch (err: any) {
      notify('bad', err?.detail || 'Counterfactual comparison failed.')
    }
  }

  async function handleReplacementTriage(e: React.FormEvent) {
    e.preventDefault()
    if (!user) return
    try {
      const res = await api.post<Record<string, any>>('/api/phase43/recommendations/replacement-triage', {
        target_slot: triageSlot,
        current_player_name: triagePlayer || null,
        game_version: gameVersion === 'FC26' ? 'FC26' : 'FC27',
      })
      setTriageResult(res)
    } catch (err: any) {
      notify('bad', err?.detail || 'Replacement triage failed.')
    }
  }

  async function handleRecordFeedback(recId: string, recType: string, action: string) {
    if (!user) return
    try {
      await api.post('/api/phase43/feedback', {
        recommendation_id: recId,
        recommendation_type: recType,
        game_version: gameVersion === 'FC26' ? 'FC26' : 'FC27',
        game_patch: patch,
        user_action: action,
        experiment_id: selectedExp?.experiment_id || null,
        snapshot_id: armBSnap || armASnap || null,
        notes: fbNote || `${action} from Tactical Lab`,
      })
      setFbNote('')
      notify('ok', `Logged feedback action (${action}).`)
      loadAll()
    } catch (err: any) {
      notify('bad', err?.detail || 'Feedback recording failed.')
    }
  }

  async function handleCvCalibrationProbe() {
    if (!user) return
    try {
      const res = await api.post<Record<string, any>>('/api/phase43/cv/benchmark-calibration', {})
      setCvCalibration(res)
      notify('ok', 'CV calibration & proxy benchmark completed.')
    } catch (err: any) {
      notify('bad', err?.detail || 'Calibration probe failed.')
    }
  }

  const expAnalysis = selectedExp?.analysis || null

  return (
    <div className="tlab-page" data-testid="tactical-lab-page">
      <header className="tlab-hero">
        <div className="stack gap04">
          <div className="row gap05 align-center flex-wrap">
            <h1 className="mb0">Tactical Experimentation Lab</h1>
            <EpistemicChip kind="frozen" label="V3.2.1 Math Preserved" />
            <EpistemicChip kind="observed" label={`${gameVersion} · ${patch}`} />
          </div>
          <p className="small text-secondary mb0" style={{ maxWidth: '78ch' }}>
            Test formations, FC IQ roles, build-up presets, multi-objective squad shapes, and slot replacements as N-of-1 match-clustered experiments.
            Distinguishes theoretical suitability from observed association and controlled experiment evidence — inconclusive results are reported honestly.
          </p>
        </div>
        <div className="row gap05 align-center flex-wrap">
          <div style={{ minWidth: 150 }}>
            <StadiumSelect
              aria-label="Patch Scope"
              value={patch}
              onChange={val => setPatch(val)}
            >
              <option value="PATCH_1.04">PATCH_1.04</option>
              <option value="PATCH_1.03">PATCH_1.03</option>
              <option value="PATCH_1.02">PATCH_1.02</option>
            </StadiumSelect>
          </div>
          <button
            type="button"
            className="btn ghost sm"
            onClick={() => openCopilot({
              prompt: 'Analyze my active tactical configuration and experiment findings',
              contextOverride: {
                route_name: 'TACTICAL_LAB',
                game_version: gameVersion === 'FC26' ? 'FC26' : 'FC27',
                tactical_snapshot_id: armBSnap || snapshots[0]?.snapshot_id || null,
                experiment_id: selectedExp?.experiment_id || null,
              },
            })}
          >
            <StadiumIcon name="coach" size={14} />
            <span>Ask Co-Pilot</span>
          </button>
          <Link className="btn ghost sm" to="/cards/squad-lab">Squad Lab</Link>
        </div>
      </header>

      {!user && (
        <div className="callout info">
          <strong>Sign in to run empirical Tactical Experiments:</strong> Immutable tactical snapshots, 4-phase fingerprints, statistical match analyses, and patch-isolated Personal Meta are user-scoped. <Link to="/login">Log in</Link> or <Link to="/signup">Sign up</Link>.
        </div>
      )}

      <nav className="tlab-tabs" aria-label="Tactical Lab Modules">
        {([
          ['OVERVIEW', 'Fingerprints & Shapes'],
          ['SNAPSHOTS', `Snapshots (${snapshots.length})`],
          ['EXPERIMENTS', `Experiments (${experiments.length})`],
          ['ADVISORY', 'Formations, Optimizer & Triage'],
          ['META_CV', 'Personal Meta & CV Status'],
        ] as [LabTab, string][]).map(([key, lbl]) => (
          <button
            key={key}
            type="button"
            className={`tlab-tab-btn ${tab === key ? 'active' : ''}`}
            onClick={() => setTab(key)}
          >
            {lbl}
          </button>
        ))}
      </nav>

      {/* TAB 1: OVERVIEW & 4-PHASE FINGERPRINTS */}
      {tab === 'OVERVIEW' && (
        <div className="tlab-grid-2">
          <section className="tlab-card">
            <div className="row space-between align-center">
              <h2 className="section-title mb0">Nominal vs Observed Shape Fingerprint</h2>
              {activeFp && <EpistemicChip kind={chipKindForGrade(activeFp.evidence_grade)} label={activeFp.evidence_grade} />}
            </div>

            {user && matches.length > 0 && (
              <div className="row gap04 align-center flex-wrap">
                <div style={{ minWidth: 230, flex: 1 }}>
                  <StadiumSelect value={linkMatchId} onChange={val => setLinkMatchId(val)} aria-label="Select match for fingerprint">
                    {matches.map(m => <option key={m.match_id} value={m.match_id}>{m.match_id} ({m.formation} · {m.game_patch})</option>)}
                  </StadiumSelect>
                </div>
                <button type="button" className="btn primary sm" onClick={() => handleBuildFingerprint(linkMatchId)}>
                  Build 4-Phase Fingerprint
                </button>
              </div>
            )}

            {activeFp?.team_compactness_abstained && (
              <div className="callout warn tiny mb0">
                <strong>Compactness Abstention Guard Active:</strong> {activeFp.abstention_reason}
              </div>
            )}

            <div className="tlab-pitch">
              <svg viewBox="0 0 420 260" width="100%" aria-label="Tactical shape comparison pitch diagram">
                <rect x="10" y="10" width="400" height="240" rx="6" fill="#0a1d16" stroke="#2d5a45" strokeWidth="2" />
                <line x1="210" y1="10" x2="210" y2="250" stroke="#2d5a45" strokeWidth="1.5" />
                <circle cx="210" cy="130" r="36" fill="none" stroke="#2d5a45" strokeWidth="1.5" />
                <rect x="10" y="75" width="48" height="110" fill="none" stroke="#2d5a45" strokeWidth="1.5" />
                <rect x="362" y="75" width="48" height="110" fill="none" stroke="#2d5a45" strokeWidth="1.5" />
                <circle cx="88" cy="70" r="7" fill="#38bdf8" />
                <circle cx="88" cy="110" r="7" fill="#38bdf8" />
                <circle cx="88" cy="150" r="7" fill="#38bdf8" />
                <circle cx="88" cy="190" r="7" fill="#38bdf8" />
                <circle cx="178" cy="95" r="8" fill="#d0fb50" />
                <circle cx="178" cy="165" r="8" fill="#d0fb50" />
                <circle cx="272" cy="75" r="7" fill="#fbbf24" />
                <circle cx="272" cy="130" r="7" fill="#fbbf24" />
                <circle cx="272" cy="185" r="7" fill="#fbbf24" />
                <circle cx="332" cy="130" r="8" fill="#fb7185" />
                <text x="20" y="28" fill="#94a3b8" fontSize="11">
                  Nominal: {activeFp?.nominal_formation || snapFormation}
                </text>
                <text x="20" y="242" fill="#d0fb50" fontSize="11">
                  Observed In-Poss: {activeFp?.observed_in_possession_shape || 'Awaiting match fingerprint'}
                </text>
              </svg>
            </div>

            {activeFp ? (
              <div className="tlab-grid-2">
                {(activeFp.phases || []).map((ph: any) => (
                  <div className="tlab-phase-box" key={ph.phase}>
                    <strong className="tiny text-lime font-mono">{ph.phase}</strong>
                    {Object.entries(ph.metrics || {}).map(([k, v]) => (
                      <div className="tlab-kv" key={k}>
                        <span className="text-secondary">{k}</span>
                        <span className="tlab-kv-val">{v === null || v === undefined ? 'Not observed' : String(v)}</span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ) : (
              <p className="small text-muted mb0">
                No Tactical Fingerprint persisted yet. Record a non-synthetic match in Gameplay Studio and click Build 4-Phase Fingerprint above.
              </p>
            )}
          </section>

          <section className="tlab-card">
            <h2 className="section-title mb0">Intended vs Observed Configuration Deltas</h2>
            {activeFp?.intended_vs_observed_deltas?.length ? (
              <div className="stack gap05">
                {activeFp.intended_vs_observed_deltas.map((d: any, idx: number) => (
                  <div className="tlab-phase-box" key={idx}>
                    <div className="row space-between align-center">
                      <strong className="small">{d.dimension}</strong>
                      <span className={`badge sm ${d.alignment_status === 'ALIGNED' ? 'lime' : 'warn'}`}>{d.alignment_status}</span>
                    </div>
                    <div className="tiny text-secondary">{d.intended_spec} · Expected {d.expected_range} · Observed {d.observed_measure ?? 'null'}</div>
                    <div className="tiny text-muted">{d.explanation}</div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="small text-muted mb0">
                Link a Tactical Configuration Snapshot with line height / width settings to inspect intended-vs-observed drift.
              </p>
            )}

            <div className="callout info tiny">
              <strong>Coverage & Calibration:</strong> {activeFp ? `${activeFp.coverage_pct}% coverage (${activeFp.calibration_state})` : 'No active telemetry selected'}. Supported metrics only; unmeasured spatial stats stay null rather than assumed 0.
            </div>
          </section>
        </div>
      )}

      {/* TAB 2: IMMUTABLE TACTICAL SNAPSHOTS */}
      {tab === 'SNAPSHOTS' && (
        <div className="tlab-grid-2">
          <section className="tlab-card">
            <h2 className="section-title mb0">Create Immutable Configuration Snapshot</h2>
            <form onSubmit={handleCreateSnapshot} className="stack gap05">
              <div className="stack gap02 tiny">
                <span>Snapshot Label</span>
                <StadiumInput value={snapLabel} onChange={e => setSnapLabel(e.target.value)} required />
              </div>
              <div className="tlab-grid-2">
                <div className="stack gap02 tiny">
                  <span>Formation (All 12 Supported)</span>
                  <StadiumSelect aria-label="Snapshot Formation" value={snapFormation} onChange={val => setSnapFormation(val)}>
                    {ALL_FORMATIONS.map(f => <option key={f} value={f}>{f}</option>)}
                  </StadiumSelect>
                </div>
                <div className="stack gap02 tiny">
                  <span>Tactical Profile / Preset</span>
                  <StadiumSelect aria-label="Snapshot Tactical Profile" value={snapProfile} onChange={val => setSnapProfile(val)}>
                    {['BALANCED', 'POSSESSION', 'COUNTER_ATTACK', 'HIGH_PRESS', 'LOW_BLOCK', 'DIRECT_PLAY'].map(p => <option key={p} value={p}>{p}</option>)}
                  </StadiumSelect>
                </div>
              </div>
              <div className="tlab-grid-2">
                <div className="stack gap02 tiny">
                  <span>Build-Up Style (empty = UNKNOWN)</span>
                  <StadiumSelect aria-label="Build-Up Style" value={snapBuildUp} onChange={val => setSnapBuildUp(val)}>
                    <option value="">UNKNOWN</option>
                    <option value="BALANCED">BALANCED</option>
                    <option value="SHORT_PASSING">SHORT_PASSING</option>
                    <option value="COUNTER">COUNTER</option>
                  </StadiumSelect>
                </div>
                <div className="stack gap02 tiny">
                  <span>Defensive Approach</span>
                  <StadiumSelect aria-label="Defensive Approach" value={snapDefense} onChange={val => setSnapDefense(val)}>
                    <option value="">UNKNOWN</option>
                    <option value="BALANCED">BALANCED</option>
                    <option value="HIGH">HIGH</option>
                    <option value="AGGRESSIVE">AGGRESSIVE</option>
                    <option value="DEEP">DEEP</option>
                  </StadiumSelect>
                </div>
              </div>
              <div className="tlab-grid-2">
                <div className="stack gap02 tiny">
                  <span>Line Height (1-100)</span>
                  <StadiumInput type="number" min={1} max={100} value={snapLineHeight} onChange={e => setSnapLineHeight(e.target.value)} />
                </div>
                <div className="stack gap02 tiny">
                  <span>Width (1-100)</span>
                  <StadiumInput type="number" min={1} max={100} value={snapWidth} onChange={e => setSnapWidth(e.target.value)} />
                </div>
              </div>
              <button type="submit" className="btn primary sm" disabled={!user}>Save Immutable Snapshot</button>
            </form>
          </section>

          <section className="tlab-card">
            <div className="row space-between align-center">
              <h2 className="section-title mb0">Versioned Snapshot Registry ({snapshots.length})</h2>
              <button type="button" className="btn ghost sm" onClick={handleDiffSnapshots} disabled={!user || !armASnap || !armBSnap}>
                Diff A vs B
              </button>
            </div>
            {snapshotDiff && (
              <div className="tlab-phase-box tiny">
                <strong>Snapshot Diff ({snapshotDiff.baseline_snapshot_id} → {snapshotDiff.variant_snapshot_id}):</strong>
                <div className="font-mono text-secondary">
                  {(snapshotDiff.field_changes || []).map((c: any) => `${c.field}: ${c.baseline}→${c.variant}`).join(' · ') || 'No top-level field changes'}
                </div>
              </div>
            )}
            <div className="stack gap04">
              {snapshots.map(s => (
                <div className="tlab-phase-box" key={s.snapshot_id}>
                  <div className="row space-between align-center">
                    <strong className="small">{s.label}</strong>
                    <span className="badge sm lime font-mono">v{s.version_number} · {s.formation}</span>
                  </div>
                  <div className="tiny text-secondary font-mono">
                    {s.snapshot_id} · {s.tactical_profile} · line={s.line_height ?? 'UNKNOWN'} · hash={String(s.config_hash).slice(0, 12)}…
                  </div>
                  <div className="tiny text-muted">
                    Preserved unknowns: {(s.unknown_fields || []).join(', ') || 'None'}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}

      {/* TAB 3: TACTICAL EXPERIMENTS & STATISTICAL LAB */}
      {tab === 'EXPERIMENTS' && (
        <div className="tlab-grid-2">
          <section className="tlab-card">
            <div className="row space-between align-center">
              <h2 className="section-title mb0">Design New Tactical Experiment</h2>
              <button type="button" className="btn ghost sm" onClick={handleSuggestExperiment} disabled={!user}>
                Suggest Trial
              </button>
            </div>
            {expSuggestion && (
              <div className="callout info tiny mb0">
                <strong>Suggested ({expSuggestion.detected_focus}):</strong> {expSuggestion.recommended_variant_change}
              </div>
            )}
            <form onSubmit={handleCreateExperiment} className="stack gap04">
              <div className="stack gap02 tiny">
                <span>Experiment Title</span>
                <StadiumInput value={expTitle} onChange={e => setExpTitle(e.target.value)} required />
              </div>
              <div className="stack gap02 tiny">
                <span>Hypothesis</span>
                <StadiumInput value={expHypothesis} onChange={e => setExpHypothesis(e.target.value)} required />
              </div>
              <div className="tlab-grid-2">
                <div className="stack gap02 tiny">
                  <span>Experiment Type (8 Workflows)</span>
                  <StadiumSelect aria-label="Experiment Type" value={expType} onChange={val => setExpType(val)}>
                    {EXPERIMENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </StadiumSelect>
                </div>
                <div className="stack gap02 tiny">
                  <span>Protocol Design (N-of-1)</span>
                  <StadiumSelect aria-label="Experiment Design Type" value={expDesignType} onChange={val => setExpDesignType(val)}>
                    {DESIGN_TYPES.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
                  </StadiumSelect>
                </div>
              </div>
              <div className="tlab-grid-2">
                <div className="stack gap02 tiny">
                  <span>Baseline Arm A Snapshot</span>
                  <StadiumSelect aria-label="Baseline Arm A Snapshot" value={armASnap} onChange={val => setArmASnap(val)}>
                    <option value="">Select Arm A…</option>
                    {snapshots.map(s => <option key={s.snapshot_id} value={s.snapshot_id}>{s.label} ({s.formation})</option>)}
                  </StadiumSelect>
                </div>
                <div className="stack gap02 tiny">
                  <span>Variant Arm B Snapshot</span>
                  <StadiumSelect aria-label="Variant Arm B Snapshot" value={armBSnap} onChange={val => setArmBSnap(val)}>
                    <option value="">Select Arm B…</option>
                    {snapshots.map(s => <option key={s.snapshot_id} value={s.snapshot_id}>{s.label} ({s.formation})</option>)}
                  </StadiumSelect>
                </div>
              </div>
              <div className="stack gap02 tiny">
                <span>Primary Metric (Match-Clustered)</span>
                <StadiumSelect aria-label="Primary Metric" value={expMetric} onChange={val => setExpMetric(val)}>
                  {METRIC_OPTIONS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                </StadiumSelect>
              </div>
              <div className="row gap04 flex-wrap">
                <button type="button" className="btn ghost sm" onClick={handlePreviewExperiment} disabled={!user}>Preview Protocol</button>
                <button type="submit" className="btn primary sm" disabled={!user}>Create Experiment</button>
              </div>
            </form>

            {(expPreview || samplePlan) && (
              <div className="tlab-phase-box tiny">
                {expPreview && (
                  <div>
                    <strong>Preview ({expPreview.design_type} · {expPreview.planned_observations} slots):</strong>{' '}
                    {(expPreview.schedule_preview || []).map((s: any) => `#${s.sequence_index}:${s.assigned_arm}`).join(' · ')}
                  </div>
                )}
                {samplePlan && (
                  <div className="text-secondary">
                    Sample Planner (power={(samplePlan.target_power * 100).toFixed(0)}%, Δ={samplePlan.expected_delta}): <strong>{samplePlan.recommended_matches_per_arm} matches per arm</strong>
                  </div>
                )}
              </div>
            )}

            <h3 className="small mt05 mb0">Your Experiments</h3>
            <div className="stack gap03">
              {experiments.map(ex => (
                <button
                  key={ex.experiment_id}
                  type="button"
                  className={`tlab-exp-item ${selectedExp?.experiment_id === ex.experiment_id ? 'active' : ''}`}
                  onClick={() => setSelectedExpId(ex.experiment_id)}
                >
                  <div>
                    <div className="small strong">{ex.title}</div>
                    <div className="tiny text-muted">
                      {ex.experiment_type} · {(ex.linked_matches || []).length} match(es)
                      {ex.adherence_rate !== null && ex.adherence_rate !== undefined ? ` · adherence=${(ex.adherence_rate * 100).toFixed(0)}%` : ''}
                    </div>
                  </div>
                  <span className="badge sm outline font-mono">{ex.status}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="tlab-card">
            <div className="row space-between align-center flex-wrap gap04">
              <h2 className="section-title mb0">Empirical Analysis & Bayesian Posterior</h2>
              {selectedExp && (
                <div className="row gap03 flex-wrap">
                  <button type="button" className="btn ghost sm" onClick={() => handleUpdateExpStatus(selectedExp.experiment_id, 'PAUSED')}>Pause</button>
                  <button type="button" className="btn ghost sm" onClick={() => handleUpdateExpStatus(selectedExp.experiment_id, 'ACTIVE')}>Resume</button>
                  <button type="button" className="btn primary sm" onClick={() => handleAnalyzeExperiment(selectedExp.experiment_id)}>
                    Run / Refresh Analysis
                  </button>
                </div>
              )}
            </div>

            {selectedExp && user && matches.length > 0 && (
              <div className="row gap04 align-center flex-wrap">
                <div style={{ minWidth: 190, flex: 1 }}>
                  <StadiumSelect value={linkMatchId} onChange={val => setLinkMatchId(val)} aria-label="Match to link">
                    {matches.map(m => <option key={m.match_id} value={m.match_id}>{m.match_id} ({m.formation})</option>)}
                  </StadiumSelect>
                </div>
                <div style={{ minWidth: 135 }}>
                  <StadiumSelect value={linkArm} onChange={val => setLinkArm(val as 'BASELINE_A' | 'VARIANT_B')} aria-label="Experiment Arm">
                    <option value="BASELINE_A">BASELINE_A</option>
                    <option value="VARIANT_B">VARIANT_B</option>
                  </StadiumSelect>
                </div>
                <button type="button" className="btn ghost sm" onClick={handleLinkMatch}>Link Match</button>
              </div>
            )}

            {expAnalysis ? (
              <div className="stack gap05">
                <div className="row gap05 align-center flex-wrap">
                  <span className={`badge sm ${expAnalysis.verdict === 'SUPPORTED_IMPROVEMENT' ? 'lime' : 'warn'}`}>{expAnalysis.verdict}</span>
                  <EpistemicChip kind={chipKindForGrade(expAnalysis.evidence_grade)} label={expAnalysis.evidence_grade} />
                  <span className="badge sm outline font-mono">{expAnalysis.unit_of_analysis}</span>
                  {expAnalysis.relative_improvement !== null && expAnalysis.relative_improvement !== undefined && (
                    <span className="badge sm cyan font-mono">Rel Δ={(expAnalysis.relative_improvement * 100).toFixed(1)}%</span>
                  )}
                </div>
                <p className="small text-white mb0">{expAnalysis.interpretation}</p>

                <table className="tlab-stat-table">
                  <thead>
                    <tr><th>Metric</th><th>Arm A ({expAnalysis.arm_a?.formation})</th><th>Arm B ({expAnalysis.arm_b?.formation})</th></tr>
                  </thead>
                  <tbody>
                    <tr><td>Eligible Matches</td><td>{expAnalysis.arm_a?.eligible_match_count}</td><td>{expAnalysis.arm_b?.eligible_match_count}</td></tr>
                    <tr><td>Mean ({expAnalysis.primary_metric})</td><td>{expAnalysis.arm_a?.mean_primary_metric ?? '—'}</td><td>{expAnalysis.arm_b?.mean_primary_metric ?? '—'}</td></tr>
                    <tr><td>Median / IQR</td><td>{expAnalysis.arm_a?.median_primary_metric ?? '—'} / {expAnalysis.arm_a?.iqr_primary_metric ?? '—'}</td><td>{expAnalysis.arm_b?.median_primary_metric ?? '—'} / {expAnalysis.arm_b?.iqr_primary_metric ?? '—'}</td></tr>
                    <tr><td>Opportunity Rate</td><td>{expAnalysis.arm_a?.opportunity_normalized_rate ?? '—'}</td><td>{expAnalysis.arm_b?.opportunity_normalized_rate ?? '—'}</td></tr>
                  </tbody>
                </table>

                {expAnalysis.bayesian_posterior_prob_b_better !== null && expAnalysis.bayesian_posterior_prob_b_better !== undefined && (
                  <div className="tlab-phase-box">
                    <div className="tlab-kv">
                      <span>Bayesian P(Variant B improves over A)</span>
                      <strong className="tlab-kv-val">{(expAnalysis.bayesian_posterior_prob_b_better * 100).toFixed(1)}%</strong>
                    </div>
                    <div className="tlab-bayes-bar-track">
                      <div className="tlab-bayes-bar-fill" style={{ width: `${Math.round(expAnalysis.bayesian_posterior_prob_b_better * 100)}%` }} />
                    </div>
                    {expAnalysis.posterior_prob_meaningful !== null && expAnalysis.posterior_prob_meaningful !== undefined && (
                      <div className="tiny text-secondary font-mono">
                        P(improvement ≥ {expAnalysis.minimum_meaningful_improvement}): {(expAnalysis.posterior_prob_meaningful * 100).toFixed(1)}%
                      </div>
                    )}
                    <div className="tiny text-secondary font-mono">
                      Test={expAnalysis.frequentist_test_name} · p={expAnalysis.p_value ?? '—'} · Hedges g={expAnalysis.effect_size_hedges_g ?? '—'} · Boot95={JSON.stringify(expAnalysis.bootstrap_ci_95)} · LOO stable={String(expAnalysis.sensitivity_leave_one_out_stable)}
                    </div>
                  </div>
                )}

                {uncertaintyBreakdown && Array.isArray(uncertaintyBreakdown.reasons) && uncertaintyBreakdown.reasons.length > 0 && (
                  <div className="tlab-phase-box tiny text-secondary">
                    <strong>Uncertainty Decomposition:</strong> {uncertaintyBreakdown.reasons.join(' · ')}
                  </div>
                )}

                {expAnalysis.confounders?.match_quality_warnings?.length > 0 && (
                  <div className="callout warn tiny mb0">
                    <strong>Confounders & Warnings:</strong> {expAnalysis.confounders.match_quality_warnings.join(' · ')}
                  </div>
                )}
              </div>
            ) : (
              <p className="small text-muted mb0">Select an experiment, link 2+ non-synthetic matches per arm, and run statistical analysis.</p>
            )}
          </section>
        </div>
      )}

      {/* TAB 4: FORMATIONS, MULTI-OBJECTIVE OPTIMIZER, COUNTERFACTUALS & TRIAGE */}
      {tab === 'ADVISORY' && (
        <div className="tlab-grid-2">
          <section className="tlab-card">
            <div className="row space-between align-center flex-wrap gap04">
              <h2 className="section-title mb0">Personal Formation Suitability (All 12 Shapes)</h2>
              <button type="button" className="btn ghost sm" onClick={handleCompareCounterfactual} disabled={!user || !armASnap || !armBSnap}>
                Run A vs B Counterfactual
              </button>
            </div>

            <div className="tlab-phase-box">
              <strong className="tiny text-lime">Side-by-Side Formation Comparator</strong>
              <div className="row gap04 align-center flex-wrap">
                <div style={{ minWidth: 110, flex: 1 }}>
                  <StadiumSelect aria-label="Formation A" value={cmpFormA} onChange={val => setCmpFormA(val)}>
                    {ALL_FORMATIONS.map(f => <option key={f} value={f}>{f}</option>)}
                  </StadiumSelect>
                </div>
                <span className="tiny text-muted">vs</span>
                <div style={{ minWidth: 110, flex: 1 }}>
                  <StadiumSelect aria-label="Formation B" value={cmpFormB} onChange={val => setCmpFormB(val)}>
                    {ALL_FORMATIONS.map(f => <option key={f} value={f}>{f}</option>)}
                  </StadiumSelect>
                </div>
                <button type="button" className="btn primary sm" onClick={handleCompareFormations} disabled={!user}>Compare Shapes</button>
              </div>
              {formationCmp && (
                <div className="tiny text-secondary stack gap02">
                  <div><strong>Winner: {formationCmp.preferred_formation}</strong> · {formationCmp.summary}</div>
                  {(formationCmp.structural_differences || []).map((d: string, i: number) => <div key={i}>• {d}</div>)}
                </div>
              )}
            </div>

            {(formations?.ranked_formations || []).slice(0, 6).map((f: any) => (
              <div className="tlab-phase-box" key={f.formation}>
                <div className="row space-between align-center">
                  <strong>{f.formation} <span className="tiny text-muted">({f.tactical_profile})</span></strong>
                  <div className="row gap04 align-center">
                    <EpistemicChip kind={chipKindForGrade(f.evidence_grade)} label={f.evidence_grade} />
                    <span className="badge sm lime font-mono">{(f.theoretical_score * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <div className="tiny font-mono text-secondary">
                  Theo={((f.theoretical_fit ?? f.theoretical_score) * 100).toFixed(0)}% · Obs={f.observed_performance !== null && f.observed_performance !== undefined ? `${(f.observed_performance * 100).toFixed(0)}%` : '—'} · ExpWins={f.experiment_wins || 0}
                </div>
                <div className="tiny text-secondary">{f.rationale}</div>
                <div className="tiny text-muted">Key Roles: {(f.recommended_roles || []).join(' · ')}</div>
              </div>
            ))}

            {counterfactual && (
              <div className="callout info tiny">
                <strong>{counterfactual.evidence_grade}:</strong> {counterfactual.summary}
                {counterfactual.zone_geometry_deltas && (
                  <div className="font-mono mt02">
                    Zone14 Δ={counterfactual.zone_geometry_deltas.zone14_overloads_delta} · Congestion Δ={counterfactual.zone_geometry_deltas.midfield_congestion_delta} · Sensitivity sweeps={counterfactual.sensitivity_sweep?.length || 0}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="tlab-card">
            <h2 className="section-title mb0">Multi-Objective Squad Optimizer (Constrained XI)</h2>
            <div className="row gap04 align-center flex-wrap">
              <div style={{ minWidth: 110 }}>
                <StadiumSelect aria-label="Optimizer Formation" value={optFormation} onChange={val => setOptFormation(val)}>
                  {ALL_FORMATIONS.map(f => <option key={f} value={f}>{f}</option>)}
                </StadiumSelect>
              </div>
              <div style={{ minWidth: 190, flex: 1 }}>
                <StadiumSelect aria-label="Optimizer Objective" value={optObjective} onChange={val => setOptObjective(val)}>
                  {SQUAD_OBJECTIVES.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </StadiumSelect>
              </div>
              <button type="button" className="btn primary sm" onClick={handleOptimizeSquad} disabled={!user}>Optimize XI</button>
            </div>
            {squadOptResult && (
              <div className="tlab-phase-box tiny stack gap03">
                <div className="row space-between align-center flex-wrap">
                  <strong>U(S)={squadOptResult.primary_xi?.utility} · {squadOptResult.solver_method}</strong>
                  <span className="badge sm outline font-mono">{squadOptResult.market_price_status}</span>
                </div>
                <div className="text-secondary font-mono">
                  11 Players={(squadOptResult.primary_xi?.lineup || []).map((p: any) => `${p.slot_label}:${p.player_name}`).join(', ')}
                </div>
                <div className="text-muted">
                  Alternatives: {(squadOptResult.alternatives || []).map((a: any) => `${a.label} (U=${a.utility})`).join(' · ') || 'None'}
                </div>
              </div>
            )}

            <h2 className="section-title mt05 mb0">Player Replacement Triage (Behavior Before Coins)</h2>
            <form onSubmit={handleReplacementTriage} className="row gap04 flex-wrap">
              <div style={{ width: 105 }}>
                <StadiumInput aria-label="Target slot" value={triageSlot} onChange={e => setTriageSlot(e.target.value)} placeholder="Slot (e.g. CDM)" />
              </div>
              <div style={{ flex: 1, minWidth: 150 }}>
                <StadiumInput aria-label="Incumbent player" value={triagePlayer} onChange={e => setTriagePlayer(e.target.value)} placeholder="Incumbent player (optional)" />
              </div>
              <button type="submit" className="btn primary sm" disabled={!user}>Run Triage</button>
            </form>
            {triageResult && (
              <div className="stack gap04">
                <div className="row gap05 align-center flex-wrap">
                  <span className="badge sm cyan font-mono">{triageResult.primary_recommendation}</span>
                  <span className="badge sm outline font-mono">purchase_justified={String(triageResult.purchase_justified)}</span>
                  <span className="badge sm outline font-mono">{triageResult.market_price_status}</span>
                </div>
                <ul className="tiny text-secondary m0 pl1">
                  {(triageResult.non_purchase_interventions || []).map((act: string, i: number) => <li key={i}>{act}</li>)}
                </ul>
                {(triageResult.candidate_comparisons || []).slice(0, 4).map((cmp: any) => (
                  <div className="tlab-phase-box" key={cmp.option}>
                    <div className="row space-between">
                      <strong>{cmp.option}: {cmp.label}</strong>
                      <span className="badge sm outline font-mono">{cmp.market_price_status}</span>
                    </div>
                  </div>
                ))}
                <div className="row gap04">
                  <button type="button" className="btn ghost sm" onClick={() => handleRecordFeedback(`TRIAGE-${triageSlot}`, 'PLAYER_REPLACEMENT', 'ACCEPTED')}>Accept Suggestion</button>
                  <button type="button" className="btn ghost sm" onClick={() => handleRecordFeedback(`TRIAGE-${triageSlot}`, 'PLAYER_REPLACEMENT', 'REJECTED')}>Reject</button>
                </div>
              </div>
            )}
          </section>
        </div>
      )}

      {/* TAB 5: PERSONAL META, CLOSED-LOOP FEEDBACK & CV CALIBRATION */}
      {tab === 'META_CV' && (
        <div className="tlab-grid-2">
          <section className="tlab-card">
            <div className="row space-between align-center">
              <h2 className="section-title mb0">Personal Meta ({gameVersion} · {patch})</h2>
              <EpistemicChip kind="observed" label="Strict Patch Isolation" />
            </div>
            {personalMeta ? (
              <div className="stack gap04">
                <div className="tlab-kv"><span>Eligible Verified Matches</span><strong className="tlab-kv-val">{personalMeta.eligible_match_count}</strong></div>
                <div className="tlab-kv"><span>Strongest System (2+ matches)</span><strong className="tlab-kv-val">{personalMeta.strongest_system || 'INSUFFICIENT_DATA'}</strong></div>
                <div className="tlab-kv"><span>Validated Experiments</span><strong className="tlab-kv-val">{personalMeta.validated_experiments_count}</strong></div>
                <div className="tlab-kv"><span>Evidence Maturity Tier</span><strong className="tlab-kv-val">{personalMeta.confidence_and_evidence_maturity?.maturity_tier || 'PRELIMINARY'}</strong></div>
                <div className="tlab-kv"><span>Frozen V3.2.1 Altered?</span><strong className="tlab-kv-val">{String(personalMeta.frozen_v321_weights_altered)}</strong></div>
                {(personalMeta.formation_breakdown || []).map((fb: any) => (
                  <div className="tlab-phase-box" key={fb.formation}>
                    <strong>{fb.formation}</strong>
                    <div className="tiny font-mono text-secondary">
                      {fb.matches}M ({fb.wins}W-{fb.draws}D-{fb.losses}L) · transition_rate={fb.mean_conceded_transition_rate ?? '—'} · compactness={fb.mean_defensive_compactness ?? '—'}
                    </div>
                  </div>
                ))}
                {(personalMeta.patch_dependent_behaviour || []).length > 0 && (
                  <div className="tlab-phase-box tiny">
                    <strong>Patch Boundaries Observed:</strong>{' '}
                    {(personalMeta.patch_dependent_behaviour || []).map((pb: any) => `${pb.game_patch}:${pb.match_count}M`).join(' · ')}
                  </div>
                )}
              </div>
            ) : (
              <p className="small text-muted mb0">Sign in to inspect your patch-isolated Personal Meta profile.</p>
            )}
          </section>

          <section className="tlab-card">
            <div className="row space-between align-center">
              <h2 className="section-title mb0">CV Runtime & Closed-Loop Feedback</h2>
              <button type="button" className="btn ghost sm" onClick={handleCvCalibrationProbe} disabled={!user}>
                Run Calibration Probe
              </button>
            </div>
            {cvStatus && (
              <div className="stack gap03 tiny">
                <div className="tlab-kv"><span>ONNX Detector Status</span><strong className="tlab-kv-val">{cvStatus.onnx_detector?.status}</strong></div>
                <div className="tlab-kv"><span>Active Fallback</span><strong className="tlab-kv-val">{cvStatus.onnx_detector?.active_runtime_fallback || 'ONNX'}</strong></div>
                <div className="tlab-kv"><span>Broadcast Stream Input</span><strong className="tlab-kv-val">{JSON.stringify(cvStatus.model_streams?.broadcast?.input_size || [640, 640])}</strong></div>
                <div className="tlab-kv"><span>Minimap ROI Stream</span><strong className="tlab-kv-val">{JSON.stringify(cvStatus.model_streams?.minimap_roi?.input_size || [320, 320])}</strong></div>
                <div className="tlab-kv"><span>OpenCL GPU Device</span><strong className="tlab-kv-val">{cvStatus.hardware_env?.opencl_device}</strong></div>
                <div className="tlab-kv"><span>CUDA PyTorch Ready</span><strong className="tlab-kv-val">{String(cvStatus.hardware_env?.training_ready_for_pytorch_gradient_descent)}</strong></div>
                <p className="text-muted mb0">{cvStatus.license_policy}</p>
              </div>
            )}
            {cvCalibration && (
              <div className="tlab-phase-box tiny">
                <strong>Calibration ({cvCalibration.calibration?.evaluation_scope}):</strong>
                <div className="font-mono">
                  ECE={cvCalibration.calibration?.ece} · Brier={cvCalibration.calibration?.brier_score} · mAP50={cvCalibration.synthetic_proxy_metrics?.map50}
                </div>
              </div>
            )}

            <div className="tlab-phase-box tiny stack gap03">
              <strong>Closed-Loop Recommendation Feedback ({feedbackList.length})</strong>
              <div className="row gap04">
                <div style={{ flex: 1 }}>
                  <StadiumInput aria-label="Feedback notes" value={fbNote} onChange={e => setFbNote(e.target.value)} placeholder="Notes on tactical recommendation…" />
                </div>
                <button type="button" className="btn ghost sm" disabled={!user} onClick={() => handleRecordFeedback('REC-LAB-MANUAL', 'TACTICAL_ADJUSTMENT', 'ACCEPTED')}>
                  Log Adopted
                </button>
              </div>
              {feedbackList.slice(0, 3).map(fb => (
                <div className="tlab-kv" key={fb.feedback_id}>
                  <span>{fb.recommendation_type} · {fb.user_action}</span>
                  <span className="tlab-kv-val">{fb.model_version}</span>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}

      {loading && <div className="tiny text-muted">Syncing Tactical Lab workspace…</div>}
    </div>
  )
}
