import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, getToken } from '../api/client'
import { useSession } from '../state/session'
import { useCopilotRouteContext } from '../state/copilot'
import { ScreenshotRedactorModal, type RedactedScreenshotPayload } from '../components/ScreenshotRedactorModal'
import { StadiumSelect } from '../components/StadiumControls'
import './PersonalCoach.css'

type CoachTab = 'COACH' | 'DNA' | 'TRAINING' | 'KNOWLEDGE'
type ProviderPref = 'AUTO' | 'GEMINI' | 'OPENROUTER_FREE' | 'DETERMINISTIC'

interface ClipRef {
  clip_id: string
  match_id: string
  video_id?: string | null
  timestamp_start: number
  timestamp_end: number
  title: string
  diagnostic_code?: string | null
  provenance: string
  confidence: string
  deep_link: string
}

interface RootCause {
  dimension: string
  plausibility_score: number
  epistemic_label: string
  rationale: string
}

interface CoachResponseData {
  session_id: string
  message_id: string
  provider?: string
  model?: string
  response_mode?: string
  provider_mode: string
  intent?: string
  answer: string
  key_findings: string[]
  evidence_references: ClipRef[]
  relevant_match_ids: string[]
  relevant_timestamps: number[]
  possible_root_causes: RootCause[]
  recommended_actions: string[]
  tactical_suggestions: string[]
  player_recommendations: Record<string, any>[]
  player_cards?: Record<string, any>[]
  squad_proposal?: Record<string, any> | null
  knowledge_sources?: Record<string, any>[]
  training_objective?: string | null
  confidence: string
  limitations: string[]
  provider_notes?: string[]
  tool_trace: { tool: string; status: string; elapsed_ms: number; summary: string }[]
  security_notices: string[]
  abstained: boolean
  latency_ms?: number
  token_usage?: { prompt_tokens: number; completion_tokens: number }
  usage_metadata?: Record<string, any>
}

interface DimensionEstimate {
  dimension: string
  axis_category: 'STYLE' | 'PROFICIENCY'
  status: string
  estimated_value: number | null
  measurement_definition: string
  sample_count: number
  effective_sample_size: number
  relevant_match_count: number
  ci_low: number | null
  ci_high: number | null
}

interface GamerDNAData {
  eligible_match_count: number
  synthetic_excluded_count: number
  has_cold_start_preferences: boolean
  cold_start_style_hints: string[]
  style_dimensions: DimensionEstimate[]
  proficiency_dimensions: DimensionEstimate[]
  tactical_suitability: { formation: string; tactical_profile: string; suitability_score: number; rationale: string; recommended_roles: string[] }[]
  improvement_potential: { dimension: string; priority_score: number; recommended_focus: string; reason: string }[]
  archetype: { status: string; primary_archetype: string; secondary_archetype?: string | null; summary: string }
  pro_comparison?: { feature_enabled: boolean; status: string; policy: string }
}

const STARTER_PROMPTS = [
  'Why am I losing matches?',
  'Why do I keep conceding counter-attacks?',
  'Find me a CDM with strong defensive positioning',
  'Which formation suits my playing style?',
  'Should I change tactics instead of spending coins?',
  'Show me the clips where I made this mistake',
]

const ACTIVITY_LABELS: Record<string, string> = {
  INTENT_CLASSIFIED: 'Routing intent across platform engines…',
  MODEL_ROUND_1: 'Evaluating evidence with free AI Coach…',
  MODEL_ROUND_2: 'Synthesizing tool results…',
  MODEL_ROUND_3: 'Verifying grounding constraints…',
}

const DEMO_COACH_DNA: GamerDNAData = {
  eligible_match_count: 3,
  synthetic_excluded_count: 1,
  has_cold_start_preferences: true,
  cold_start_style_hints: ['SYNTHETIC_FIXTURE sample preview'],
  archetype: {
    status: 'SYNTHETIC_FIXTURE',
    primary_archetype: 'Possession Controller',
    secondary_archetype: 'Counter-Press Transitionist',
    summary: 'Sample Preview Fixture (n=3 demo traces) — High central buildup with exposed fullback recovery lanes.',
  },
  style_dimensions: [
    { dimension: 'possession_tempo', axis_category: 'STYLE', status: 'OBSERVED', estimated_value: 0.74, measurement_definition: 'Sample buildup share', sample_count: 3, effective_sample_size: 2.6, relevant_match_count: 3, ci_low: 0.61, ci_high: 0.85 },
    { dimension: 'press_intensity', axis_category: 'STYLE', status: 'OBSERVED', estimated_value: 0.68, measurement_definition: 'Sample high-press trigger rate', sample_count: 3, effective_sample_size: 2.4, relevant_match_count: 3, ci_low: 0.54, ci_high: 0.80 },
  ],
  proficiency_dimensions: [
    { dimension: 'central_pass_security', axis_category: 'PROFICIENCY', status: 'OBSERVED', estimated_value: 0.81, measurement_definition: 'Sample completed forward passes', sample_count: 3, effective_sample_size: 2.7, relevant_match_count: 3, ci_low: 0.69, ci_high: 0.90 },
    { dimension: 'counter_transition_defense', axis_category: 'PROFICIENCY', status: 'OBSERVED', estimated_value: 0.52, measurement_definition: 'Sample transition prevention rate', sample_count: 3, effective_sample_size: 2.3, relevant_match_count: 3, ci_low: 0.39, ci_high: 0.65 },
  ],
  tactical_suitability: [
    { formation: '4-2-3-1', tactical_profile: 'BALANCED', suitability_score: 0.84, rationale: 'Double pivot screens transition channels behind attacking fullbacks.', recommended_roles: ['CDM: Holding', 'CAM: Playmaker'] },
  ],
  improvement_potential: [],
}

const DEMO_TRAINING_PLAN = {
  plan_id: 'DEMO-PLAN-SYNTHETIC',
  next_match_objectives: ['Use double pivot shielding before triggering RB overlap.', 'Switch play to weak-side LW when central lane interception margin < 0.2s.'],
  exercises: [
    {
      exercise_id: 'DEMO-EX-1',
      title: 'Central Progression Under High Press (Sample)',
      skill_code: 'PASS_SELECTION',
      freeze_timestamp_sec: 28.4,
      scenario_summary: 'Opposing CDM screens vertical lane to ST (-0.18s clearance margin); weak-side LW has +0.62s time to control.',
      defensible_option_ids: ['OPT-LW'],
      in_game_drill: 'Arena 11v11 buildup drill with 4-2-3-1 Hold CDM.',
      options: [
        { option_id: 'OPT-LW', action_label: 'Switch Left Wide to Unmarked LW (Optimal Margin)', is_defensible: true },
        { option_id: 'OPT-ST', action_label: 'Force Vertical Pass into Marked ST', is_defensible: false },
      ],
    },
  ],
}

export default function PersonalCoach() {
  const { user, gameVersion, notify } = useSession()
  const [activeTab, setActiveTab] = useState<CoachTab>('COACH')
  const [demoMode, setDemoMode] = useState(false)

  // Multi-conversation & context state
  const [conversations, setConversations] = useState<Record<string, any>[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [savedSquads, setSavedSquads] = useState<Record<string, any>[]>([])
  const [selectedSquadId, setSelectedSquadId] = useState<string>('')
  const [selectedMatchId, setSelectedMatchId] = useState<string>('')

  // Provider selection, streaming & error state
  const [providerPref, setProviderPref] = useState<ProviderPref>('AUTO')
  const [consentExternal, setConsentExternal] = useState(false)
  const [providerHealth, setProviderHealth] = useState<Record<string, any> | null>(null)
  const [activityStatus, setActivityStatus] = useState<string>('')
  const [streamingText, setStreamingText] = useState<string>('')
  const [lastFailedQuestion, setLastFailedQuestion] = useState<string | null>(null)
  const [proposalStates, setProposalStates] = useState<Record<string, string>>({})
  const [showRedactor, setShowRedactor] = useState(false)
  const [attachedScreenshot, setAttachedScreenshot] = useState<RedactedScreenshotPayload | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const activeReqIdRef = useRef<string | null>(null)

  useCopilotRouteContext({
    route_name: 'GAMER_DNA',
    game_version: gameVersion === 'FC26' ? 'FC26' : 'FC27',
    squad_id: selectedSquadId || null,
    match_id: selectedMatchId || null,
  })

  // Coach Q&A state
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [responses, setResponses] = useState<{ q: string; r: CoachResponseData }[]>([])

  // Gamer DNA, Matches & Progression state
  const [dna, setDna] = useState<GamerDNAData | null>(null)
  const [matches, setMatches] = useState<Record<string, any>[]>([])
  const [progression, setProgression] = useState<Record<string, any> | null>(null)
  const [coldTempo, setColdTempo] = useState<'SLOW_POSSESSION' | 'BALANCED' | 'FAST_DIRECT'>('BALANCED')
  const [coldPress, setColdPress] = useState<'LOW_BLOCK' | 'MID_BLOCK' | 'HIGH_PRESS'>('MID_BLOCK')
  const [coldWidth, setColdWidth] = useState<'NARROW_CENTRAL' | 'BALANCED' | 'WIDE_WINGPLAY'>('BALANCED')
  const [coldFormation, setColdFormation] = useState('4-2-3-1')

  // Training Academy state
  const [trainingPlan, setTrainingPlan] = useState<Record<string, any> | null>(null)
  const [attemptResults, setAttemptResults] = useState<Record<string, { feedback: string; defensible: boolean; mastery: number; revealedOutcome?: string; reasoning?: string }>>({})

  // Knowledge Explorer state
  const [kbQuery, setKbQuery] = useState('FC IQ role defending playstyle')
  const [kbEntries, setKbEntries] = useState<Record<string, any>[]>([])

  async function refreshUserIntelligence() {
    if (!user) return
    try {
      const [d, m, p, tp, convs, ph, sqs] = await Promise.all([
        api.get<GamerDNAData>('/api/phase40/gamer-dna'),
        api.get<{ items: Record<string, any>[] }>('/api/phase40/matches'),
        api.get<Record<string, any>>('/api/phase40/progression'),
        api.get<Record<string, any>>(`/api/phase40/training/plan?game_version=${gameVersion}`),
        api.get<{ conversations: Record<string, any>[] }>('/api/phase40/coach/conversations').catch(() => ({ conversations: [] })),
        api.get<Record<string, any>>('/api/phase40/coach/providers/health').catch(() => null),
        api.get<{ items?: Record<string, any>[] } | Record<string, any>[]>('/api/squads').catch(() => []),
      ])
      setDna(d)
      setMatches(m.items || [])
      setProgression(p)
      setTrainingPlan(tp)
      setConversations(convs.conversations || [])
      if (ph && Object.keys(ph).length > 0) setProviderHealth(ph)
      const sqList = Array.isArray(sqs) ? sqs : (sqs?.items || [])
      setSavedSquads(sqList)
    } catch {
      /* gracefully handled by UI states */
    }
  }

  async function searchKnowledge(qText: string) {
    try {
      const res = await api.get<{ entries: Record<string, any>[] }>(
        `/api/phase40/knowledge?q=${encodeURIComponent(qText)}&game_version=${gameVersion}`
      )
      setKbEntries(res.entries || [])
    } catch {
      setKbEntries([])
    }
  }

  useEffect(() => {
    refreshUserIntelligence()
  }, [user?.id, gameVersion])

  useEffect(() => {
    searchKnowledge(kbQuery)
  }, [gameVersion])

  async function loadConversation(sid: string) {
    setSessionId(sid)
    try {
      const res = await api.get<{ messages: Record<string, any>[] }>(`/api/phase40/coach/messages?session_id=${encodeURIComponent(sid)}`)
      const msgs = res.messages || []
      const pairs: { q: string; r: CoachResponseData }[] = []
      let pendingQ = ''
      for (const m of msgs) {
        if (m.role === 'user') {
          pendingQ = m.content || ''
        } else if (m.role === 'assistant' && m.structured_payload && Object.keys(m.structured_payload).length > 0) {
          pairs.unshift({ q: pendingQ || 'Previous question', r: m.structured_payload as CoachResponseData })
          pendingQ = ''
        }
      }
      setResponses(pairs)
    } catch {
      notify('bad', 'Failed to load conversation history.')
    }
  }

  async function handleDeleteConversation(sid: string) {
    try {
      await api.del(`/api/phase40/coach/conversations/${encodeURIComponent(sid)}`)
      if (sessionId === sid) {
        setSessionId(null)
        setResponses([])
      }
      setConversations(prev => prev.filter(c => c.session_id !== sid))
      notify('ok', 'Conversation deleted.')
    } catch {
      notify('bad', 'Could not delete conversation.')
    }
  }

  function startNewConversation() {
    setSessionId(null)
    setResponses([])
    setLastFailedQuestion(null)
  }

  function enableDemoMode() {
    setDemoMode(true)
    setDna(DEMO_COACH_DNA)
    setTrainingPlan(DEMO_TRAINING_PLAN)
    setResponses([
      {
        q: 'Why do I keep conceding counter-attacks?',
        r: {
          session_id: 'DEMO-SESSION',
          message_id: 'DEMO-MSG-1',
          provider: 'deterministic',
          model: 'synthetic-fixture-preview',
          response_mode: 'SYNTHETIC_FIXTURE_PREVIEW',
          provider_mode: 'SYNTHETIC_FIXTURE_PREVIEW',
          answer: 'In the sample 4-2-3-1 fixture matches, 2 of 3 transition turnovers occurred when the RB pushed high while the single pivot pushed beyond midfield without cover.',
          key_findings: [
            'SYNTHETIC_FIXTURE sample: Transition defense rating (52%) lags behind possession tempo (74%).',
            'Central half-space gap widened past 18m when RCM overlapped simultaneously.',
          ],
          evidence_references: [
            {
              clip_id: 'DEMO-CLIP-1',
              match_id: 'SYNTHETIC-DEMO-01',
              video_id: 'VID-012',
              timestamp_start: 45.2,
              timestamp_end: 47.8,
              title: 'Right-Channel Transition Exposure',
              provenance: 'SYNTHETIC_FIXTURE',
              confidence: 'SAMPLE',
              deep_link: '/research/gameplay-studio?video_id=VID-012&t=45.2&tab=RADAR_REPLAY',
            },
          ],
          relevant_match_ids: ['SYNTHETIC-DEMO-01'],
          relevant_timestamps: [45.2],
          possible_root_causes: [],
          recommended_actions: [
            'Switch one CM/CDM duty to Holding / Deep-Lying Playmaker.',
            'Test a faster recovery RB candidate in Squad Lab.',
          ],
          tactical_suggestions: [],
          player_recommendations: [],
          confidence: 'SAMPLE',
          limitations: ['Read-only demo fixture. Sign in and import real matches for empirical Gamer DNA.'],
          tool_trace: [{ tool: 'demo_fixture_sampler', status: 'OK', elapsed_ms: 1, summary: 'Client-side synthetic demo preview' }],
          security_notices: [],
          abstained: false,
        },
      },
    ])
  }

  async function stopGeneration() {
    abortRef.current?.abort()
    if (activeReqIdRef.current) {
      try {
        await api.post(`/api/phase40/coach/cancel/${encodeURIComponent(activeReqIdRef.current)}`)
      } catch {
        /* ignore */
      }
    }
    setAsking(false)
    setActivityStatus('Generation stopped.')
  }

  async function submitCoachQuestion(textToAsk: string) {
    const trimmed = textToAsk.trim()
    if (!trimmed) return
    if (!user) {
      if (!demoMode) return
      setResponses(prev => [
        {
          q: trimmed,
          r: {
            session_id: 'DEMO-SESSION',
            message_id: `DEMO-MSG-${Date.now()}`,
            provider: 'deterministic',
            model: 'synthetic-fixture-preview',
            provider_mode: 'SYNTHETIC_FIXTURE_PREVIEW',
            answer: `Demo Preview Response for "${trimmed}": Sign in and upload match telemetry in Gameplay Studio to run all grounded diagnostic, V3.2.1 player discovery, Squad Lab preview, and training tools on your own matches.`,
            key_findings: ['Sample Gamer DNA remains isolated as SYNTHETIC_FIXTURE telemetry.'],
            evidence_references: [],
            relevant_match_ids: [],
            relevant_timestamps: [],
            possible_root_causes: [],
            recommended_actions: ['Explore DNA & Training tabs in demo mode, or sign in to connect your account.'],
            tactical_suggestions: [],
            player_recommendations: [],
            confidence: 'SAMPLE',
            limitations: ['Client-side read-only sample mode active while logged out.'],
            tool_trace: [],
            security_notices: [],
            abstained: false,
          },
        },
        ...prev,
      ])
      setQuestion('')
      return
    }

    const reqId = `req-${Date.now()}`
    activeReqIdRef.current = reqId
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setAsking(true)
    setLastFailedQuestion(null)
    setStreamingText('')
    setActivityStatus('Connecting to EA FC Intelligence Coach…')

    const payload: Record<string, any> = {
      question: trimmed,
      session_id: sessionId,
      game_version: gameVersion === 'FC26' ? 'FC26' : 'FC27',
      squad_id: selectedSquadId || null,
      active_match_id: selectedMatchId || null,
      context_envelope: {
        route_name: 'GAMER_DNA',
        game_version: gameVersion === 'FC26' ? 'FC26' : 'FC27',
        squad_id: selectedSquadId || null,
        match_id: selectedMatchId || null,
      },
      consent_external_llm: consentExternal,
      preferred_provider: providerPref,
      request_id: reqId,
    }
    if (attachedScreenshot) {
      payload.user_consent_media = attachedScreenshot.consentMedia
      payload.redaction_confirmed = attachedScreenshot.redactionConfirmed
      payload.screenshot_use_case = attachedScreenshot.useCase
      payload.image_b64 = attachedScreenshot.imageB64
      payload.image_mime = attachedScreenshot.mime
    }

    try {
      const token = getToken()
      const headers: Record<string, string> = { 'Content-Type': 'application/json', Accept: 'text/event-stream' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      const streamRes = await fetch('/api/phase40/coach/ask/stream', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
        signal: ctrl.signal,
      })

      if (streamRes.ok && streamRes.body && streamRes.headers.get('content-type')?.includes('text/event-stream')) {
        const reader = streamRes.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let finalResp: CoachResponseData | null = null
        while (true) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const blocks = buffer.split('\n\n')
          buffer = blocks.pop() || ''
          for (const blk of blocks) {
            const lines = blk.split('\n')
            const evLine = lines.find(l => l.startsWith('event:'))
            const dataLine = lines.find(l => l.startsWith('data:'))
            if (!dataLine) continue
            const evName = evLine ? evLine.slice(6).trim() : 'message'
            const parsed = JSON.parse(dataLine.slice(5).trim())
            if (evName === 'stage') {
              setActivityStatus(ACTIVITY_LABELS[parsed.stage] || `Stage: ${parsed.stage}`)
            } else if (evName === 'tool_start') {
              setActivityStatus(`Running platform tools: ${(parsed.tools || []).slice(0, 3).join(', ')}…`)
            } else if (evName === 'delta') {
              setStreamingText(prev => prev + (parsed.text || ''))
            } else if (evName === 'done') {
              finalResp = parsed as CoachResponseData
            }
          }
        }
        if (finalResp) {
          setSessionId(finalResp.session_id)
          setResponses(prev => [{ q: trimmed, r: finalResp! }, ...prev])
          setQuestion('')
          setAttachedScreenshot(null)
          refreshUserIntelligence()
          return
        }
      }

      // Fallback cleanly to standard JSON endpoint (used in unit tests or non-SSE proxies)
      const res = await api.post<CoachResponseData>('/api/phase40/coach/ask', payload)
      setSessionId(res.session_id)
      setResponses(prev => [{ q: trimmed, r: res }, ...prev])
      setQuestion('')
      refreshUserIntelligence()
    } catch (err: any) {
      if (err?.name === 'AbortError') return
      setLastFailedQuestion(trimmed)
      notify('bad', err?.detail || 'Failed to reach Personal AI Coach.')
    } finally {
      setAsking(false)
      setActivityStatus('')
      setStreamingText('')
      activeReqIdRef.current = null
    }
  }

  async function handleConfirmProposal(proposalId: string) {
    try {
      await api.post(`/api/phase40/squad-proposals/${encodeURIComponent(proposalId)}/confirm`)
      setProposalStates(prev => ({ ...prev, [proposalId]: 'CONFIRMED_APPLIED' }))
      notify('ok', 'Squad proposal confirmed & applied. Undo remains available.')
      refreshUserIntelligence()
    } catch (err: any) {
      notify('bad', err?.detail || 'Could not confirm squad proposal.')
    }
  }

  async function handleRollbackProposal(proposalId: string) {
    try {
      await api.post(`/api/phase40/squad-proposals/${encodeURIComponent(proposalId)}/rollback`)
      setProposalStates(prev => ({ ...prev, [proposalId]: 'ROLLED_BACK' }))
      notify('ok', 'Squad change rolled back to previous snapshot.')
      refreshUserIntelligence()
    } catch (err: any) {
      notify('bad', err?.detail || 'Rollback failed.')
    }
  }

  async function saveColdStart(e: React.FormEvent) {
    e.preventDefault()
    if (!user) {
      notify('info', 'Sample preview mode is read-only. Sign in to persist preferences.')
      return
    }
    try {
      const updated = await api.post<GamerDNAData>('/api/phase40/gamer-dna/cold-start', {
        preferred_tempo: coldTempo,
        pressing_comfort: coldPress,
        width_preference: coldWidth,
        preferred_formation: coldFormation,
        preferred_build_up: coldTempo === 'FAST_DIRECT' ? 'COUNTER_VERTICAL' : coldTempo === 'SLOW_POSSESSION' ? 'SHORT_COMBINATION' : 'BALANCED',
        game_version: gameVersion === 'FC26' ? 'FC26' : 'FC27',
      })
      setDna(updated)
      notify('ok', 'Self-reported cold-start preferences saved (clearly marked separate from gameplay evidence).')
    } catch (err: any) {
      notify('bad', err?.detail || 'Could not save cold-start preferences.')
    }
  }

  async function submitTrainingChoice(ex: any, optId: string) {
    if (!trainingPlan) return
    if (!user) {
      const isDef = Array.isArray(ex.defensible_option_ids) && ex.defensible_option_ids.includes(optId)
      setAttemptResults(prev => ({
        ...prev,
        [ex.exercise_id]: {
          feedback: isDef
            ? 'Sample Feedback: Optimal space-preserving decision (+0.62s clearance).'
            : 'Sample Feedback: Risky forced lane — consider wide switch option.',
          defensible: isDef,
          mastery: isDef ? 0.72 : 0.45,
        },
      }))
      return
    }
    try {
      const res = await api.post<{ attempt: any; bkt_state: any; revealed_outcome?: string; tactical_reasoning?: string }>('/api/phase40/training/attempt', {
        plan_id: trainingPlan.plan_id,
        exercise_id: ex.exercise_id,
        skill_code: ex.skill_code,
        selected_option_id: optId,
        defensible_option_ids: ex.defensible_option_ids,
      })
      setAttemptResults(prev => ({
        ...prev,
        [ex.exercise_id]: {
          feedback: res.attempt.feedback_summary,
          defensible: res.attempt.is_optimal_or_defensible,
          mastery: res.bkt_state.p_mastery,
          revealedOutcome: res.revealed_outcome,
          reasoning: res.tactical_reasoning,
        },
      }))
      refreshUserIntelligence()
    } catch (err: any) {
      notify('bad', err?.detail || 'Failed to record training attempt.')
    }
  }

  async function handlePrivacyReset() {
    if (!user) return
    try {
      await api.del('/api/phase40/privacy/reset')
      setResponses([])
      setConversations([])
      setSessionId(null)
      notify('ok', 'All personal match records, Gamer DNA, and coaching history deleted.')
      refreshUserIntelligence()
    } catch (err: any) {
      notify('bad', err?.detail || 'Reset failed.')
    }
  }

  async function handleDeleteMatch(matchId: string) {
    try {
      await api.del(`/api/phase40/matches/${matchId}`)
      notify('ok', `Deleted match ${matchId}.`)
      refreshUserIntelligence()
    } catch (err: any) {
      notify('bad', err?.detail || 'Delete failed.')
    }
  }

  return (
    <div className="coach-container" data-testid="personal-coach-page">
      <header className="coach-header">
        <div className="coach-header-top">
          <div>
            <h1>Personal AI Football Coach &amp; Gamer DNA</h1>
            <p className="tiny text-secondary mb0" style={{ maxWidth: '72ch' }}>
              Hybrid Agentic Football Intelligence combining Gemini Free &amp; OpenRouter Free reasoning with frozen V3.2.1 suitability, Squad Lab, Decision Regret, Gamer DNA, and BM25 official rules.
            </p>
          </div>
          <div className="row align-center gap05 flex-wrap">
            <span className="badge sm cyan font-mono">Free-Only Guarded</span>
            <span className="badge sm outline lime font-mono">V3.2.1 Baseline Frozen</span>
            <Link className="btn ghost sm" to="/tactical-lab">Tactical Lab →</Link>
            <Link className="btn ghost sm" to="/research/decision-lab">Decision Replay Lab →</Link>
          </div>
        </div>

        <nav className="coach-tabs" aria-label="Coach Workspaces">
          <button type="button" className={`coach-tab-btn ${activeTab === 'COACH' ? 'active' : ''}`} onClick={() => setActiveTab('COACH')}>
            AI Football Coach
          </button>
          <button type="button" className={`coach-tab-btn ${activeTab === 'DNA' ? 'active' : ''}`} onClick={() => setActiveTab('DNA')}>
            Gamer DNA & Progression {dna ? `(${dna.eligible_match_count})` : ''}
          </button>
          <button type="button" className={`coach-tab-btn ${activeTab === 'TRAINING' ? 'active' : ''}`} onClick={() => setActiveTab('TRAINING')}>
            Training Academy
          </button>
          <button type="button" className={`coach-tab-btn ${activeTab === 'KNOWLEDGE' ? 'active' : ''}`} onClick={() => setActiveTab('KNOWLEDGE')}>
            Official Knowledge Base
          </button>
        </nav>
      </header>

      {!user && !demoMode && activeTab !== 'KNOWLEDGE' && (
        <div className="callout info">
          <div className="row space-between align-center flex-wrap gap05">
            <div>
              <strong>Sign in to unlock your isolated Personal Coach Workspace:</strong> Your match repository, historical squad snapshots, Gamer DNA, and conversations are strictly user-scoped. You can also explore the <button type="button" className="btn ghost sm" onClick={() => setActiveTab('KNOWLEDGE')}>Official Knowledge Base</button> or preview sample coaching fixtures now.
            </div>
            <div className="row gap05 flex-wrap">
              <button type="button" className="btn primary sm" onClick={enableDemoMode}>
                Preview Sample Coaching &amp; DNA
              </button>
              <Link className="btn ghost sm" to="/login">Log in</Link>
              <Link className="btn ghost sm" to="/signup">Create account</Link>
            </div>
          </div>
        </div>
      )}

      {!user && demoMode && (
        <div className="callout warn" role="status">
          <div className="row space-between align-center flex-wrap gap05">
            <span>
              <strong>SYNTHETIC_FIXTURE Sample Preview:</strong> Exploring read-only sample Gamer DNA, coach findings, and BKT drills. <Link to="/login">Sign in</Link> to analyze your real matches.
            </span>
            <button type="button" className="btn ghost sm" onClick={() => { setDemoMode(false); setDna(null); setTrainingPlan(null); setResponses([]) }}>
              Exit Sample Preview
            </button>
          </div>
        </div>
      )}

      {/* TAB 1: PERSONAL AI COACH */}
      {activeTab === 'COACH' && (user || demoMode) && (
        <div className="coach-workspace-grid">
          {/* Left Rail: Multi-Conversation Persistence */}
          <aside className="coach-panel coach-history-rail" aria-label="Coaching Conversations">
            <div className="row space-between align-center">
              <h2 className="section-title mb0">Sessions</h2>
              <button type="button" className="btn ghost sm" onClick={startNewConversation}>+ New</button>
            </div>
            <div className="coach-conv-list">
              {conversations.length === 0 ? (
                <p className="tiny text-muted mb0">Current session active. Conversations persist per account.</p>
              ) : conversations.map(c => (
                <div key={c.session_id} className="coach-conv-row">
                  <button
                    type="button"
                    className={`coach-conv-btn ${sessionId === c.session_id ? 'active' : ''}`}
                    onClick={() => loadConversation(c.session_id)}
                    title={c.title || 'Coaching Session'}
                  >
                    {c.title || 'Personal Session'}
                  </button>
                  <button
                    type="button"
                    className="btn ghost sm"
                    style={{ minWidth: 28, minHeight: 28, padding: '0 0.35rem' }}
                    aria-label={`Delete conversation ${c.title || c.session_id}`}
                    onClick={() => handleDeleteConversation(c.session_id)}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </aside>

          {/* Center Column: Conversational Agent & Evidence Cards */}
          <section className="coach-panel" aria-label="Coaching Conversation">
            <form
              onSubmit={e => {
                e.preventDefault()
                submitCoachQuestion(question)
              }}
              className="stack gap05"
            >
              <label htmlFor="coach-question-input" className="tiny text-secondary strong">
                Ask your coach (questions run user-scoped diagnostic, V3.2.1 player, Squad Lab &amp; knowledge tools):
              </label>
              <div className="row gap05 flex-wrap">
                <input
                  id="coach-question-input"
                  type="text"
                  style={{ flex: 1, minWidth: 220 }}
                  value={question}
                  onChange={e => setQuestion(e.target.value)}
                  placeholder="Ask about players, squad upgrades, counter-attacks, or FC IQ…"
                />
                {asking ? (
                  <button type="button" className="btn-secondary-action" onClick={stopGeneration}>Stop</button>
                ) : (
                  <button type="submit" className="btn-primary-action" disabled={!question.trim()}>Ask Coach</button>
                )}
              </div>

              <div className="coach-controls-strip tiny">
                <div className="stack gap02">
                  <span className="text-muted">Engine / AI Mode</span>
                  <StadiumSelect
                    aria-label="Engine / AI Mode"
                    value={providerPref}
                    onChange={val => setProviderPref(val as ProviderPref)}
                  >
                    <option value="AUTO">Auto (Gemini → Det.)</option>
                    <option value="GEMINI">Gemini Free API</option>
                    <option value="OPENROUTER_FREE">OpenRouter Free Only</option>
                    <option value="DETERMINISTIC">Deterministic Offline Only</option>
                  </StadiumSelect>
                </div>

                <div className="stack gap02">
                  <span className="text-muted">Active Squad Context</span>
                  <StadiumSelect
                    aria-label="Active Squad Context"
                    value={selectedSquadId}
                    onChange={val => setSelectedSquadId(val)}
                  >
                    <option value="">All / Auto Saved Squad</option>
                    {savedSquads.map((s: any) => (
                      <option key={s.id} value={s.id}>{s.name} ({s.formation})</option>
                    ))}
                  </StadiumSelect>
                </div>

                <div className="stack gap02">
                  <span className="text-muted">Active Match Focus</span>
                  <StadiumSelect
                    aria-label="Active Match Focus"
                    value={selectedMatchId}
                    onChange={val => setSelectedMatchId(val)}
                  >
                    <option value="">All Verified Matches ({matches.length})</option>
                    {matches.map((m: any) => (
                      <option key={m.match_id} value={m.match_id}>{m.match_id} ({m.formation})</option>
                    ))}
                  </StadiumSelect>
                </div>
              </div>

              <label className="row align-center gap05 tiny text-muted">
                <input
                  type="checkbox"
                  checked={consentExternal}
                  onChange={e => setConsentExternal(e.target.checked)}
                />
                Enable free-tier Gemini / OpenRouter external synthesis (sends minimized context only, never raw videos or credentials; unpaid APIs may retain de-identified prompts)
              </label>
              {providerPref !== 'DETERMINISTIC' && !consentExternal && (
                <div className="tiny text-muted" role="note">
                  Consent separation active: external provider {providerPref} will not receive data until External AI opt-in is checked.
                </div>
              )}

              <div className="row gap05 align-center flex-wrap">
                <button
                  type="button"
                  className="btn ghost sm"
                  disabled={!user}
                  onClick={() => setShowRedactor(true)}
                >
                  {attachedScreenshot
                    ? `Redacted Screenshot Attached (${attachedScreenshot.useCase})`
                    : 'Attach Redacted Screenshot'}
                </button>
                {attachedScreenshot && (
                  <button type="button" className="btn ghost sm" onClick={() => setAttachedScreenshot(null)}>
                    Remove Screenshot
                  </button>
                )}
              </div>
            </form>

            {asking && (
              <div className="coach-activity-banner" role="status" aria-live="polite">
                <span>{activityStatus || 'Running grounded coach intelligence…'}</span>
                <span className="font-mono tabular">Free-only guard active</span>
              </div>
            )}

            {streamingText && (
              <div className="coach-response-card">
                <span className="tiny text-cyan font-mono">Streaming draft…</span>
                <p className="mb0 text-white" style={{ lineHeight: 1.5 }}>{streamingText}</p>
              </div>
            )}

            {lastFailedQuestion && !asking && (
              <div className="callout warn row space-between align-center">
                <span className="tiny">Last request encountered an error before completion.</span>
                <button type="button" className="btn ghost sm" onClick={() => submitCoachQuestion(lastFailedQuestion)}>Retry</button>
              </div>
            )}

            <div className="coach-prompt-chips">
              {STARTER_PROMPTS.map(p => (
                <button key={p} type="button" className="coach-prompt-chip" onClick={() => submitCoachQuestion(p)}>
                  {p}
                </button>
              ))}
            </div>

            {responses.length === 0 ? (
              <div className="p1 text-secondary tiny" style={{ background: 'rgba(13,23,34,0.65)', borderRadius: 8 }}>
                Ask any football coaching, player scouting, or Squad Lab question above or pick a starter prompt. If verified match footage is absent on a match-diagnosis query, the coach honestly abstains.
              </div>
            ) : (
              <div className="stack gap05">
                {responses.map(({ q, r }) => {
                  const recCards = (r.player_cards && r.player_cards.length > 0 ? r.player_cards : r.player_recommendations) || []
                  const prop = r.squad_proposal
                  const propStatus = prop?.proposal_id ? (proposalStates[prop.proposal_id] || prop.status || 'PENDING_CONFIRMATION') : ''
                  return (
                    <article key={r.message_id} className={`coach-response-card ${r.abstained ? 'abstained' : ''}`}>
                      <div className="row space-between align-center flex-wrap gap05">
                        <strong className="text-cyan">Q: {q}</strong>
                        <div className="row gap05 flex-wrap">
                          <span className={`badge sm ${r.abstained ? 'warning' : r.confidence === 'HIGH' ? 'lime' : 'cyan'}`}>
                            {r.abstained ? 'ABSTAINED (MISSING EVIDENCE)' : `Confidence: ${r.confidence}`}
                          </span>
                          <span className="badge sm outline font-mono">
                            {r.response_mode || r.provider_mode}{r.model && r.model !== 'deterministic-coach' ? ` (${r.model})` : ''}
                          </span>
                        </div>
                      </div>

                      <p className="mb0 text-white" style={{ lineHeight: 1.55 }}>{r.answer}</p>

                      {r.key_findings.length > 0 && (
                        <div className="tiny">
                          <strong className="text-lime">Key Findings:</strong>
                          <ul className="m0 pl1 text-secondary">
                            {r.key_findings.map((f, idx) => <li key={idx}>{f}</li>)}
                          </ul>
                        </div>
                      )}

                      {recCards.length > 0 && (
                        <div className="stack gap03">
                          <strong className="tiny text-white">Verified Player Cards (V3.2.1 / PostgreSQL Catalogue):</strong>
                          <div className="coach-player-cards-grid">
                            {recCards.slice(0, 4).map((p: any, idx: number) => (
                              <div key={p.entity_id || idx} className="coach-player-rec tiny">
                                <div className="row space-between align-center">
                                  <strong className="text-white">{p.name}</strong>
                                  <span className="badge tiny lime tabular">OVR {p.overall_rating ?? '—'}</span>
                                </div>
                                <div className="text-muted font-mono tabular">
                                  {p.position || '—'} · Fit {(p.score ?? p.personal_gameplay_fit ?? p.v321_suitability) ?? '—'} · {p.market_price_status || 'MARKET_PRICE_UNAVAILABLE'}
                                </div>
                                <div className="row gap05 flex-wrap mt01">
                                  {p.detail_route && <Link className="text-cyan" to={p.detail_route}>Details</Link>}
                                  <Link className="text-cyan" to="/compare">Compare</Link>
                                  <Link className="text-lime" to={p.squad_lab_route || `/cards/squad-lab?item=${p.entity_id || ''}`}>Test in Squad Lab</Link>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {prop && prop.proposal_id && (
                        <div className="coach-proposal-panel tiny">
                          <div className="row space-between align-center flex-wrap gap05">
                            <strong className="text-lime">Squad Change Preview ({prop.formation} · {prop.tactical_profile})</strong>
                            <span className="badge tiny outline font-mono">{propStatus}</span>
                          </div>
                          {Array.isArray(prop.slots) && (
                            <div className="row flex-wrap gap05 font-mono text-secondary">
                              {prop.slots.filter((s: any) => s.player).slice(0, 6).map((s: any) => (
                                <span key={s.slot}>{s.slot}: {s.player.name}</span>
                              ))}
                            </div>
                          )}
                          <div className="row gap05 flex-wrap">
                            {propStatus !== 'CONFIRMED_APPLIED' && (
                              <button type="button" className="btn primary sm" onClick={() => handleConfirmProposal(prop.proposal_id)}>
                                Confirm &amp; Apply Squad Change
                              </button>
                            )}
                            {propStatus === 'CONFIRMED_APPLIED' && (
                              <button type="button" className="btn ghost sm" onClick={() => handleRollbackProposal(prop.proposal_id)}>
                                Undo / Rollback Squad Change
                              </button>
                            )}
                          </div>
                        </div>
                      )}

                      {r.evidence_references.length > 0 && (
                        <div className="row flex-wrap gap05 align-center">
                          <span className="tiny text-muted strong">Supporting Video Clips:</span>
                          {r.evidence_references.map(clip => (
                            <Link
                              key={clip.clip_id}
                              className="coach-clip-link"
                              to={clip.deep_link || `/research/gameplay-studio?video_id=${clip.video_id ?? 'VID-012'}&t=${clip.timestamp_start}&tab=RADAR_REPLAY`}
                            >
                              {clip.title} @ {clip.timestamp_start.toFixed(1)}s ({clip.provenance})
                            </Link>
                          ))}
                        </div>
                      )}

                      {r.recommended_actions.length > 0 && (
                        <div className="tiny">
                          <strong className="text-white">Recommended Next Actions:</strong>
                          <ul className="m0 pl1 text-secondary">
                            {r.recommended_actions.map((a, idx) => <li key={idx}>{a}</li>)}
                          </ul>
                        </div>
                      )}

                      {r.knowledge_sources && r.knowledge_sources.length > 0 && (
                        <div className="tiny text-muted">
                          <strong className="text-secondary">Knowledge Sources: </strong>
                          {r.knowledge_sources.map((k: any) => `${k.source_title} [${k.verification_status}]`).join(' · ')}
                        </div>
                      )}

                      {r.limitations.length > 0 && (
                        <div className="tiny text-muted font-mono">
                          Limitations: {r.limitations.join(' · ')}
                        </div>
                      )}

                      <details className="tiny text-muted">
                        <summary>Inspect Response Details &amp; Tool Trace ({r.tool_trace.length} tool calls)</summary>
                        <div className="font-mono mt02">
                          Provider: {r.provider || 'deterministic'} · Model: {r.model || 'deterministic-coach'} · Latency: {r.latency_ms ?? 0}ms · Cost: ${(r.usage_metadata?.reported_cost_usd ?? 0).toFixed(4)}
                        </div>
                        {r.provider_notes && r.provider_notes.length > 0 && (
                          <div className="text-warning font-mono mt01">Routing notes: {r.provider_notes.join(' | ')}</div>
                        )}
                        <ul className="m0 pl1 mt02 font-mono">
                          {r.tool_trace.map((t, idx) => (
                            <li key={idx}>{t.tool} [{t.status}] · {t.elapsed_ms}ms — {t.summary}</li>
                          ))}
                        </ul>
                      </details>
                    </article>
                  )
                })}
              </div>
            )}
          </section>

          {/* Right Rail: Gamer DNA Snapshot + Provider Health */}
          <aside className="coach-panel" aria-label="Gamer Summary Rail">
            <h2 className="section-title mb0">Gamer DNA Snapshot</h2>
            {dna ? (
              <>
                <div className="metric-box">
                  <span className="metric-box-label">Archetype Classification</span>
                  <strong className="text-lime">{dna.archetype.primary_archetype}</strong>
                  <span className="tiny text-secondary">{dna.archetype.summary}</span>
                  <div className="row gap05 mt02 tabular tiny font-mono">
                    <span>Real matches: <strong>{dna.eligible_match_count}</strong></span>
                    <span>·</span>
                    <span>Synthetic excluded: <strong>{dna.synthetic_excluded_count}</strong></span>
                  </div>
                </div>

                {dna.tactical_suitability.length > 0 && (
                  <div className="metric-box">
                    <span className="metric-box-label">Top Tactical Setup</span>
                    <strong className="text-cyan">
                      {dna.tactical_suitability[0].formation} ({dna.tactical_suitability[0].tactical_profile})
                    </strong>
                    <span className="tiny text-secondary">{dna.tactical_suitability[0].rationale}</span>
                  </div>
                )}

                {providerHealth && (
                  <details className="tiny text-muted">
                    <summary>AI Provider Status ($0 Free-Only)</summary>
                    <div className="font-mono mt01">
                      <div>Gemini Free: {providerHealth.config?.gemini_configured ? providerHealth.config?.gemini_model : 'Unavailable'}</div>
                      <div>OpenRouter Free: {providerHealth.config?.openrouter_configured ? providerHealth.config?.openrouter_model : 'Unavailable'}</div>
                      <div>Free models discovered: {(providerHealth.free_models || []).length}</div>
                      <div>Reported spend today: ${(providerHealth.quota?.reported_cost_usd_today ?? 0).toFixed(4)}</div>
                    </div>
                  </details>
                )}

                <div className="row gap05 flex-wrap">
                  <Link className="btn ghost sm" to="/cards/squad-lab">Open Squad Lab Personal Fit</Link>
                  <Link className="btn ghost sm" to="/research/gameplay-studio">Open Gameplay Studio</Link>
                </div>
              </>
            ) : (
              <p className="tiny text-muted">Loading Gamer DNA summary…</p>
            )}
          </aside>
        </div>
      )}

      {/* TAB 2: GAMER DNA & PROGRESSION */}
      {activeTab === 'DNA' && (user || demoMode) && dna && (
        <section className="coach-panel" aria-label="Gamer DNA and Longitudinal History">
          <div className="row space-between align-center flex-wrap gap05">
            <div>
              <h2 className="section-title mb0">Persistent Gamer DNA — {dna.archetype.primary_archetype}</h2>
              <p className="tiny text-secondary mb0">
                Explicitly separates Style Preferences from Execution Proficiency with Kish effective sample size and 95% Bayesian credible intervals. {dna.synthetic_excluded_count} SYNTHETIC_FIXTURE item(s) strictly excluded.
              </p>
            </div>
            <button type="button" className="btn-secondary-action sm" onClick={handlePrivacyReset}>
              Privacy Reset (Delete All Personal History)
            </button>
          </div>

          {dna.pro_comparison && (
            <div className="callout info tiny">
              <strong>Pro Gamer DNA Schema:</strong> {dna.pro_comparison.status} — {dna.pro_comparison.policy}
            </div>
          )}

          <div>
            <h3 className="section-title mb02">1. Playing Style Profile (Preferences)</h3>
            <div className="dna-dimension-grid">
              {dna.style_dimensions.map(dim => (
                <div key={dim.dimension} className="dna-dim-card">
                  <div className="row space-between align-center">
                    <strong className="tiny text-white">{dim.dimension.replace(/_/g, ' ').toUpperCase()}</strong>
                    <span className={`badge tiny ${dim.status === 'OBSERVED' ? 'cyan' : 'outline'} tabular`}>
                      {dim.estimated_value != null ? `${(dim.estimated_value * 100).toFixed(0)}%` : 'INSUFFICIENT'}
                    </span>
                  </div>
                  <div className="dna-bar-track">
                    <div className="dna-bar-fill" style={{ width: `${(dim.estimated_value ?? 0) * 100}%` }} />
                  </div>
                  <div className="tiny text-muted font-mono tabular">
                    Matches: {dim.relevant_match_count} · n_eff: {dim.effective_sample_size}
                    {dim.ci_low != null && dim.ci_high != null ? ` · 95% CI [${(dim.ci_low * 100).toFixed(0)}%, ${(dim.ci_high * 100).toFixed(0)}%]` : ''}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 className="section-title mb02">2. Playing Proficiency Profile (Effectiveness)</h3>
            <div className="dna-dimension-grid">
              {dna.proficiency_dimensions.map(dim => (
                <div key={dim.dimension} className="dna-dim-card">
                  <div className="row space-between align-center">
                    <strong className="tiny text-white">{dim.dimension.replace(/_/g, ' ').toUpperCase()}</strong>
                    <span className={`badge tiny ${dim.status === 'OBSERVED' ? 'lime' : 'outline'} tabular`}>
                      {dim.estimated_value != null ? `${(dim.estimated_value * 100).toFixed(0)}%` : 'INSUFFICIENT'}
                    </span>
                  </div>
                  <div className="dna-bar-track">
                    <div className="dna-bar-fill proficiency" style={{ width: `${(dim.estimated_value ?? 0) * 100}%` }} />
                  </div>
                  <div className="tiny text-muted font-mono tabular">
                    Matches: {dim.relevant_match_count} · n_eff: {dim.effective_sample_size}
                    {dim.ci_low != null && dim.ci_high != null ? ` · 95% CI [${(dim.ci_low * 100).toFixed(0)}%, ${(dim.ci_high * 100).toFixed(0)}%]` : ''}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <form onSubmit={saveColdStart} className="coaching-diag-card">
            <h3 className="section-title mb02">Optional Cold-Start Playing Style Questionnaire</h3>
            <div className="grid-4col gap05 tiny mb02">
              <label className="stack gap02">
                <span>Build-Up Tempo</span>
                <select value={coldTempo} onChange={e => setColdTempo(e.target.value as any)}>
                  <option value="SLOW_POSSESSION">Patient Possession</option>
                  <option value="BALANCED">Balanced Tempo</option>
                  <option value="FAST_DIRECT">Fast Direct</option>
                </select>
              </label>
              <label className="stack gap02">
                <span>Pressing Comfort</span>
                <select value={coldPress} onChange={e => setColdPress(e.target.value as any)}>
                  <option value="LOW_BLOCK">Compact Low Block</option>
                  <option value="MID_BLOCK">Balanced Mid Block</option>
                  <option value="HIGH_PRESS">High Press</option>
                </select>
              </label>
              <label className="stack gap02">
                <span>Width Preference</span>
                <select value={coldWidth} onChange={e => setColdWidth(e.target.value as any)}>
                  <option value="NARROW_CENTRAL">Narrow Central Triangles</option>
                  <option value="BALANCED">Balanced Width</option>
                  <option value="WIDE_WINGPLAY">Wide Wingplay</option>
                </select>
              </label>
              <label className="stack gap02">
                <span>Favorite Formation</span>
                <select value={coldFormation} onChange={e => setColdFormation(e.target.value)}>
                  <option value="4-2-3-1">4-2-3-1</option>
                  <option value="4-3-3">4-3-3</option>
                  <option value="4-4-2">4-4-2</option>
                </select>
              </label>
            </div>
            <button type="submit" className="btn-primary-action sm">Save Cold-Start Preferences</button>
          </form>

          {progression && (
            <div>
              <h3 className="section-title mb02">3. Match History ({matches.length}) & Progression</h3>
              {progression.comparability_warnings?.length > 0 && (
                <div className="callout warning tiny mb02">
                  <strong>Comparability Guards:</strong> {progression.comparability_warnings.join(' · ')}
                </div>
              )}
              <div className="audit-log-table-wrapper">
                <table className="audit-log-table tabular">
                  <thead>
                    <tr>
                      <th>Match ID</th>
                      <th>Edition / Patch</th>
                      <th>Formation</th>
                      <th>Provenance</th>
                      <th>Coverage</th>
                      <th>Findings</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {matches.length === 0 ? (
                      <tr><td colSpan={7} className="text-muted">No match records persisted yet.</td></tr>
                    ) : matches.map(m => (
                      <tr key={m.match_id}>
                        <td className="font-mono text-cyan">{m.match_id}</td>
                        <td>{m.game_version} · {m.game_patch}</td>
                        <td>{m.formation}</td>
                        <td><span className={`badge tiny ${m.provenance === 'SYNTHETIC_FIXTURE' ? 'warning' : 'lime'}`}>{m.provenance}</span></td>
                        <td>{m.tracking_coverage_pct}%</td>
                        <td>{(m.coaching_findings || []).length}</td>
                        <td>
                          <button type="button" className="btn ghost sm" onClick={() => handleDeleteMatch(m.match_id)}>
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {Array.isArray(progression.weakness_loop_tracking) && progression.weakness_loop_tracking.length > 0 && (
                <div className="mt05">
                  <h4 className="section-title mb02">Closed-Loop Transfer Monitor (Weakness → Practice → Subsequent Matches)</h4>
                  <p className="tiny text-muted mb02">
                    {progression.causal_disclaimer || 'Within-person observational trends only; patch tuning, formation shifts, and opponent quality prevent causal proof.'}
                  </p>
                  <div className="audit-log-table-wrapper">
                    <table className="audit-log-table tabular">
                      <thead>
                        <tr>
                          <th>Diagnostic / Skill</th>
                          <th>Practice (BKT)</th>
                          <th>Early → Recent Rate</th>
                          <th>Delta</th>
                          <th>Verdict</th>
                        </tr>
                      </thead>
                      <tbody>
                        {progression.weakness_loop_tracking.map((w: any) => (
                          <tr key={w.diagnostic_code}>
                            <td className="font-mono">{w.diagnostic_code} <span className="tiny text-muted">({w.linked_skill_code})</span></td>
                            <td>{w.practice_attempts} tries ({w.practice_accuracy != null ? `${Math.round(w.practice_accuracy * 100)}%` : '—'})</td>
                            <td>{w.early_opportunity_rate ?? '—'} → {w.recent_opportunity_rate ?? '—'}</td>
                            <td>{w.rate_delta != null ? `${w.rate_delta >= 0 ? '+' : ''}${w.rate_delta}` : '—'}</td>
                            <td><span className="badge sm outline font-mono">{w.verdict}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {/* TAB 3: TRAINING ACADEMY */}
      {activeTab === 'TRAINING' && (user || demoMode) && (
        <section className="coach-panel" aria-label="Personalized Training Academy">
          <div className="row space-between align-center flex-wrap gap05">
            <div>
              <h2 className="section-title mb0">Personalized Training Academy (Temporal Occlusion & BKT)</h2>
              <p className="tiny text-secondary mb0">
                Freeze-frame tactical challenges supporting multiple defensible options. Mastery uses Experimental Bayesian Knowledge Tracing pending follow-up match validation.
              </p>
            </div>
          </div>

          {trainingPlan ? (
            <>
              <div className="coaching-priority-box">
                <strong className="text-lime">Next-Match Objectives:</strong>
                <ul className="m0 pl1 tiny text-white mt01">
                  {(trainingPlan.next_match_objectives || []).map((o: string, idx: number) => <li key={idx}>{o}</li>)}
                </ul>
              </div>

              <div className="stack gap05">
                {(trainingPlan.exercises || []).map((ex: any) => {
                  const res = attemptResults[ex.exercise_id]
                  return (
                    <article key={ex.exercise_id} className="coaching-diag-card">
                      <div className="row space-between align-center flex-wrap gap05 mb02">
                        <strong className="text-white">{ex.title}</strong>
                        <div className="row gap05 align-center flex-wrap">
                          {ex.category && <span className="badge sm outline font-mono">{ex.category}</span>}
                          {ex.difficulty && <span className="badge sm outline font-mono">{ex.difficulty}</span>}
                          <span className="badge sm cyan font-mono">{ex.skill_code}</span>
                          {ex.linked_window_id && <span className="badge sm lime font-mono">Decision Window</span>}
                          {ex.source_clip?.deep_link && (
                            <Link className="coach-clip-link" to={ex.source_clip.deep_link}>
                              Freeze @ {ex.freeze_timestamp_sec}s
                            </Link>
                          )}
                        </div>
                      </div>
                      <p className="tiny text-secondary mb02">{ex.scenario_summary}</p>
                      <div className="stack gap03">
                        {(ex.options || []).map((opt: any) => (
                          <button
                            key={opt.option_id}
                            type="button"
                            className={`coach-option-btn ${res ? (opt.is_defensible ? 'correct' : 'suboptimal') : ''}`}
                            onClick={() => submitTrainingChoice(ex, opt.option_id)}
                          >
                            {opt.action_label}
                          </button>
                        ))}
                      </div>
                      {res && (
                        <div className="mt02 tiny text-lime font-mono stack gap01">
                          <div>{res.feedback}</div>
                          {res.revealedOutcome && <div className="text-white">Post-Answer Outcome Reveal: {res.revealedOutcome}</div>}
                          {res.reasoning && <div className="text-secondary">{res.reasoning}</div>}
                          <div>Practice Drill: {ex.in_game_drill}</div>
                        </div>
                      )}
                    </article>
                  )
                })}
              </div>
            </>
          ) : (
            <p className="tiny text-muted">Loading personalized practice plan…</p>
          )}
        </section>
      )}

      {/* TAB 4: KNOWLEDGE BASE */}
      {activeTab === 'KNOWLEDGE' && (
        <section className="coach-panel" aria-label="Official Football Knowledge Explorer">
          <div className="row space-between align-center flex-wrap gap05">
            <div>
              <h2 className="section-title mb0">Versioned EA FC Mechanics & Research Registry ({gameVersion})</h2>
              <p className="tiny text-secondary mb0">
                Ranked via Okapi BM25 separating verified official EA Pitch Notes facts from peer-reviewed sports/esports methodologies.
              </p>
            </div>
          </div>

          <form
            className="row gap05"
            onSubmit={e => {
              e.preventDefault()
              searchKnowledge(kbQuery)
            }}
          >
            <input
              type="text"
              style={{ flex: 1 }}
              value={kbQuery}
              onChange={e => setKbQuery(e.target.value)}
              placeholder="Search FC IQ roles, PlayStyles+, manual defending, EPV, BKT…"
            />
            <button type="submit" className="btn-primary-action sm">Search Knowledge</button>
          </form>

          <div className="stack gap04">
            {kbEntries.map(e => (
              <article key={e.entry_id} className="coaching-diag-card">
                <div className="row space-between align-center flex-wrap gap05 mb01">
                  <strong className="text-white">{e.source_title}</strong>
                  <div className="row gap05">
                    <span className={`badge sm ${e.verification_status === 'OFFICIAL_FACT' ? 'lime' : 'cyan'}`}>
                      {e.verification_status}
                    </span>
                    <span className="badge sm outline font-mono">{e.game_version} · {e.patch_version}</span>
                  </div>
                </div>
                <p className="tiny text-secondary mb02">{e.factual_summary}</p>
                <div className="tiny text-muted font-mono">
                  Topic: {e.topic} · Published: {e.publication_date} · Source: {e.source_url}
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {showRedactor && (
        <ScreenshotRedactorModal
          onCancel={() => setShowRedactor(false)}
          onAttach={payload => {
            setAttachedScreenshot(payload)
            setShowRedactor(false)
            notify('ok', 'Redacted screenshot attached for Co-Pilot review.')
          }}
        />
      )}
    </div>
  )
}
