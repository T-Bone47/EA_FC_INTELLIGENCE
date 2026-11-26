import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { api, getToken, type ApiError } from '../api/client'
import { recordAnalysis } from '../lib/recentAnalyses'
import { useAction } from '../lib/useApi'
import { ErrorBox, Field, Loading } from '../components/common'
import { StadiumCombobox, StadiumSelect } from '../components/StadiumControls'
import { compare, recommend, recommendationOptions, savedFootballStyle, toApiError } from './api'
import { LeaderEvidence } from './DecisionEvidence'
import { ErrorBoundary } from './ErrorBoundary'
import { ComparePanel } from './ComparePanel'
import { Ladder } from './Ladder'
import { WhatIfPanel } from './WhatIfPanel'
import { TacticalPreview } from '../components/TacticalPreview'
import { PlayerIdentity } from '../components/PlayerIdentity'
import { StadiumIcon } from '../components/StadiumIcons'
import { SuitabilityScore, EvidenceBadge } from '../components/Visualizations'
import type { CompareResponse, DivisionInfo, Entry, FormationSlot, RecommendRequest, RecommendResponse } from './types'

export const MAX_COMPARE = 3

export const POSITIONS = ['GK', 'CB', 'LB', 'RB', 'CDM', 'CM', 'CAM', 'LM', 'RM', 'LW', 'RW', 'ST']
/** The six styles the Phase 23 intelligence lab measured (the API also accepts legacy aliases and CUSTOM). */
export const TACTICS = ['BALANCED', 'POSSESSION', 'HIGH_PRESS', 'LOW_BLOCK', 'COUNTER_ATTACK', 'DIRECT_PLAY']

const OUTFIELD_ATTRIBUTES = ['acceleration', 'ball_control', 'finishing', 'interceptions', 'short_passing', 'stamina', 'vision']
const GOALKEEPER_ATTRIBUTES = ['gk_diving', 'gk_handling', 'gk_kicking', 'gk_positioning', 'gk_reflexes']

function preferencesAt(position: string) {
  return position === 'GK' ? GOALKEEPER_ATTRIBUTES : OUTFIELD_ATTRIBUTES
}

export interface TacticalDemands {
  description: string
  keyAttributes: string[]
  recommendedPlayStyles: string[]
  idealDuty: string
}

export const TACTICAL_PROFILES: Record<string, TacticalDemands> = {
  POSSESSION: {
    description: 'Prioritizes ball retention, technical precision, press resistance, and progressive distribution.',
    keyAttributes: ['Short Passing', 'Vision', 'Ball Control', 'Composure', 'Agility'],
    recommendedPlayStyles: ['Tiki Taka+', 'Incisive Pass', 'Press Proven', 'First Touch'],
    idealDuty: 'Deep Playmaker / Regista / Controller',
  },
  HIGH_PRESS: {
    description: 'Requires relentless physical stamina, quick recovery, aggressive duel engagement, and high turnovers in the attacking third.',
    keyAttributes: ['Stamina', 'Acceleration', 'Interceptions', 'Aggression', 'Standing Tackle'],
    recommendedPlayStyles: ['Relentless+', 'Anticipate', 'Intercept', 'Bruiser'],
    idealDuty: 'Ball Winner / Press Trigger / Box-to-Box',
  },
  COUNTER_ATTACK: {
    description: 'Demands rapid vertical transitions, explosive straight-line pace, direct ball progression, and clinical finishing.',
    keyAttributes: ['Acceleration', 'Sprint Speed', 'Finishing', 'Shot Power', 'Reactions'],
    recommendedPlayStyles: ['Quick Step+', 'Rapid', 'Power Shot', 'Finesse Shot'],
    idealDuty: 'Advanced Forward / Inside Winger / Direct Runner',
  },
  LOW_BLOCK: {
    description: 'Focuses on rigid defensive structure, physical containment, aerial dominance, and goal-line protection.',
    keyAttributes: ['Defensive Awareness', 'Strength', 'Jumping', 'Heading Accuracy', 'Standing Tackle'],
    recommendedPlayStyles: ['Block+', 'Aerial', 'Bruiser', 'Anticipate'],
    idealDuty: 'Stopper / Defensive Anchor / Penalty Box Wall',
  },
  DIRECT_PLAY: {
    description: 'Bypasses midfield with long vertical passing, target man hold-up play, second-ball duels, and wide crosses.',
    keyAttributes: ['Long Passing', 'Strength', 'Heading Accuracy', 'Crossing', 'Shot Power'],
    recommendedPlayStyles: ['Long Ball Pass+', 'Aerial', 'Whipped Pass', 'Power Header'],
    idealDuty: 'Target Forward / Box-to-Box Disruptor / Crossing Specialist',
  },
  BALANCED: {
    description: 'Harmonious tactical setup emphasizing versatility, positional discipline, and equal phase contributions.',
    keyAttributes: ['Short Passing', 'Stamina', 'Ball Control', 'Interceptions', 'Sprint Speed'],
    recommendedPlayStyles: ['Relentless', 'Incisive Pass', 'Anticipate', 'Trivela'],
    idealDuty: 'All-Round Contributor / Complete Player',
  },
}

export type DivisionChoice = 'MEN' | 'WOMEN' | 'BOTH' | null
export interface FormState {
  gameVersion: 'FC26' | 'FC27'; position: string; division: DivisionChoice
  tactical: string; secondary: string; lam: number | null
  formation?: string; slot?: string
  preferredAttribute?: string; playstylePlus?: string
}

/** null = not sendable yet. FC27 never defaults a division: the user must choose Men's / Women's / Both. */
export function buildRequest(s: FormState, researchEnabled = false): RecommendRequest | null {
  const fc27 = s.gameVersion === 'FC27'
  if ((fc27 && s.division === null) || (s.formation && !s.slot)) return null
  const req: RecommendRequest = { game_version: s.gameVersion, position: s.position, tactical_profile: s.tactical, limit: 10 }
  if (fc27 && researchEnabled) req.include_research_data = true
  if (fc27 && s.division === 'MEN') req.division = "Men's Football"
  if (fc27 && s.division === 'WOMEN') req.division = "Women's Football"
  if (s.formation && s.slot) { req.formation = s.formation; req.slot = s.slot }
  if (s.secondary) req.secondary_tactical_profile = s.secondary
  if (s.lam !== null) req.lam = s.lam
  if (s.preferredAttribute && preferencesAt(s.position).includes(s.preferredAttribute)) {
    req.attribute_preferences = [{ attribute: s.preferredAttribute, weight: 2 }]
  }
  if (s.playstylePlus?.trim()) req.desired_playstyles_plus = [s.playstylePlus.trim()]
  return req
}

const isResponse = (r: unknown): r is RecommendResponse =>
  !!r && Array.isArray((r as RecommendResponse).ranked) && !!(r as RecommendResponse).division

function ScopeBanner({ division }: { division: DivisionInfo }) {
  const parts = Object.entries(division.candidate_counts ?? {}).map(([label, n]) => `${n.toLocaleString()} ${label}`)
  const text = division.scope === 'ALL_DIVISIONS' && parts.length > 1
    ? `Mixed pool — scored together: ${parts.join(', ')}.`
    : `Pool: ${parts.join(', ')}${division.requested ? ' (division filter applied)' : ''}.`
  return <p className="ix-scope" data-testid="scope-banner">{text}</p>
}

function RecommendationFeedback({ result, player, version }: {
  result: RecommendResponse; player: Entry; version: string
}) {
  const action = useAction((label: 'SELECTED' | 'REJECTED') => api.post('/api/feedback', {
    recommendation_id: result.request_id, receipt: result.feedback_receipt,
    entity_id: player.entity_id, entity_type: 'game_player', game_version: version, action: label,
  }))
  return <div className="ix-row">
    <span>Feedback for {player.name}</span>
    {action.result ? <span role="status">Feedback recorded</span> : <>
      <button className="btn sm" disabled={action.pending} onClick={() => void action.run('SELECTED')}>Useful fit</button>
      <button className="btn sm" disabled={action.pending} onClick={() => void action.run('REJECTED')}>Poor fit</button>
    </>}
    <ErrorBox error={action.error} />
  </div>
}

export function Intelligence({ initialVersion = 'FC27', initialPosition, onVersionChange, analysisScope,
  researchEnabled = false, canRecommend = researchEnabled || initialVersion === 'FC26',
  availabilityStatus, researchControl }: {
  initialVersion?: FormState['gameVersion']; initialPosition?: string
  onVersionChange?: (version: FormState['gameVersion']) => void; analysisScope?: string
  researchEnabled?: boolean; canRecommend?: boolean; availabilityStatus?: string; researchControl?: ReactNode
} = {}) {
  const [s, setS] = useState<FormState>({ gameVersion: initialVersion,
    position: initialPosition && POSITIONS.includes(initialPosition.toUpperCase()) ? initialPosition.toUpperCase() : 'CM',
    division: null, tactical: 'BALANCED', secondary: '', lam: null })
  const [formations, setFormations] = useState<Record<string, FormationSlot[]>>({})
  const [result, setResult] = useState<RecommendResponse | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)
  const [lastReq, setLastReq] = useState<RecommendRequest | null>(null)   // the context the SHOWN results belong to
  const [selected, setSelected] = useState<string[]>([])
  const [inspectedId, inspect] = useState<string | null>(null)
  const inspected = result?.ranked.find(entry => entry.entity_id === inspectedId) ?? result?.ranked[0]
  const [cmp, setCmp] = useState<CompareResponse | null>(null)
  const [cmpErr, setCmpErr] = useState<ApiError | null>(null)
  const recommendGeneration = useRef(0)
  const compareGeneration = useRef(0)
  const requestPending = useRef(false)
  const autoSubmitRef = useRef(false)
  const req = (onVersionChange ? canRecommend : s.gameVersion === 'FC26' || researchEnabled)
    ? buildRequest(s, researchEnabled) : null
  const slots = formations[s.formation ?? ''] ?? []

  useEffect(() => {
    let active = true
    void recommendationOptions().then(options => {
      if (active) setFormations(options?.formations ?? {})
    }).catch(() => {})
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (autoSubmitRef.current && req && !busy) {
      autoSubmitRef.current = false
      void submit()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s, req])

  function set(p: Partial<FormState>) {
    recommendGeneration.current++
    requestPending.current = false
    setBusy(false); setError(null)
    setS(prev => ({ ...prev, ...p }))
  }

  async function applySavedStyle() {
    const generation = recommendGeneration.current
    try {
      const style = await savedFootballStyle()
      if (!style || generation !== recommendGeneration.current) return
      const proposed: Partial<FormState> = {}
      if (style.position && POSITIONS.includes(style.position)) {
        proposed.position = style.position
        proposed.formation = ''
        proposed.slot = ''
      }
      if (style.tactical_profile && TACTICS.includes(style.tactical_profile)) proposed.tactical = style.tactical_profile
      set(proposed)
    } catch (e) {
      if (generation === recommendGeneration.current) setError(toApiError(e))
    }
  }

  function applyPreset(preset: { formation?: string; slot?: string; position: string; tactical: string }) {
    const updates: Partial<FormState> = {
      position: preset.position,
      tactical: preset.tactical,
      formation: preset.formation ?? '',
      slot: preset.slot ?? '',
    }
    if (s.gameVersion === 'FC27' && s.division === null) {
      updates.division = 'BOTH'
    }
    if (s.gameVersion === 'FC26' || researchEnabled) {
      autoSubmitRef.current = true
    }
    set(updates)
  }

  async function submit() {
    if (!req || requestPending.current) return
    const generation = ++recommendGeneration.current
    compareGeneration.current++
    requestPending.current = true
    setResult(null); setLastReq(null)
    setBusy(true); setError(null); setCmp(null); setCmpErr(null); setSelected([])
    try {
      const res = await recommend(req)
      if (generation !== recommendGeneration.current) return
      if (!isResponse(res)) throw new Error('The server returned an unexpected response.')
      setResult(res); setLastReq(req)
      if (analysisScope) recordAnalysis(analysisScope, { version: req.game_version, position: req.position,
        tactic: req.tactical_profile, formation: req.formation, slot: req.slot })
    } catch (e) {
      if (generation === recommendGeneration.current) setError(toApiError(e))
    } finally {
      if (generation === recommendGeneration.current) {
        requestPending.current = false
        setBusy(false)
      }
    }
  }

  function toggle(e: Entry) {
    compareGeneration.current++
    setCmp(null); setCmpErr(null)
    setSelected(sel => sel.includes(e.entity_id)
      ? sel.filter(x => x !== e.entity_id) : sel.length < MAX_COMPARE ? [...sel, e.entity_id] : sel)
  }
  async function runCompare() {
    if (!lastReq) return
    const generation = ++compareGeneration.current
    setCmpErr(null)
    try {
      const response = await compare(lastReq, selected)
      if (generation === compareGeneration.current) setCmp(response)
    } catch (e) {
      if (generation === compareGeneration.current) { setCmp(null); setCmpErr(toApiError(e)) }
    }
  }

  const currentTacticalProfile = TACTICAL_PROFILES[s.tactical] ?? TACTICAL_PROFILES.BALANCED
  const activeRoleName = s.slot || s.position

  return (
    <div className="ix">
      {/* Workflow Stepper */}
      <div className="ix-stepper" aria-label="Intelligence decision steps">
        <div className={`ix-step-item ${!result ? 'is-active' : ''}`}>
          <span className="ix-step-num">1</span>
          <span>Tactical Context</span>
        </div>
        <span className="faint">→</span>
        <div className={`ix-step-item ${s.formation || s.slot ? 'is-active' : ''}`}>
          <span className="ix-step-num">2</span>
          <span>Pitch Alignment</span>
        </div>
        <span className="faint">→</span>
        <div className={`ix-step-item ${result ? 'is-active' : ''}`}>
          <span className="ix-step-num">3</span>
          <span>Ranked Intelligence</span>
        </div>
      </div>

      <div className="page-head">
        <div className="flex1">
          <div className="row align-center gap05 mb02">
            <span className="badge lime">Stadium 3.0</span>
            <span className="badge outline">Deterministic Engine</span>
          </div>
          <h1 className="mb0">Player Intelligence Studio</h1>
          <p className="muted mb0">Evaluate candidate suitability for your tactic, formation slot and playing style.</p>
        </div>
        <span className="badge info">V3.2.1 Engine · λ {s.lam ?? 0.70} Emphasis</span>
      </div>

      <div className="workspace-grid ix-workbench">
        {/* Left Form: Tactical Problem Definition */}
        <section className="card workspace-rail ix-context" aria-label="Football context">
          <div className="row justify-between align-center mb05">
            <h2 className="mb0" style={{ fontSize: '1.05rem', letterSpacing: '0.04em', textTransform: 'uppercase' }}>Tactical Setup</h2>
            {getToken() && (
              <button type="button" className="btn sm" onClick={applySavedStyle}>
                Use saved football preferences
              </button>
            )}
          </div>

          {/* Quick-Start Tactical Presets */}
          <div className="mt05 mb1">
            <label className="section-title" style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-tertiary)' }}>
              Quick Tactical Archetypes
            </label>
            <div className="ix-archetype-tray mt05">
              <button
                type="button"
                className="ix-archetype-chip row align-center gap03"
                onClick={() => applyPreset({ formation: '4-3-3', slot: 'ST', position: 'ST', tactical: 'COUNTER_ATTACK' })}
              >
                <StadiumIcon name="zap" size={13} />
                <span>4-3-3 Counter ST</span>
              </button>
              <button
                type="button"
                className="ix-archetype-chip row align-center gap03"
                onClick={() => applyPreset({ formation: '4-3-3', slot: 'CDM', position: 'CDM', tactical: 'POSSESSION' })}
              >
                <StadiumIcon name="target" size={13} />
                <span>Possession CDM</span>
              </button>
              <button
                type="button"
                className="ix-archetype-chip row align-center gap03"
                onClick={() => applyPreset({ formation: '4-3-3', slot: 'RB', position: 'RB', tactical: 'HIGH_PRESS' })}
              >
                <StadiumIcon name="shield" size={13} />
                <span>High-Press RB</span>
              </button>
              <button
                type="button"
                className="ix-archetype-chip row align-center gap03"
                onClick={() => applyPreset({ formation: '4-3-3', slot: 'LCM', position: 'CM', tactical: 'BALANCED' })}
              >
                <StadiumIcon name="intelligence" size={13} />
                <span>Creative CM</span>
              </button>
            </div>
          </div>

          <h2>Game</h2>
          <div className="ix-row">
            {(['FC26', 'FC27'] as const).map(v => (
              <label key={v} className="radio-pill" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer' }}>
                <input
                  type="radio"
                  name="gv"
                  checked={s.gameVersion === v}
                  onChange={() => { if (onVersionChange) onVersionChange(v); else set({ gameVersion: v }) }}
                />{' '}
                <strong style={{ color: s.gameVersion === v ? 'var(--accent-lime)' : 'inherit' }}>{v}</strong>
              </label>
            ))}
          </div>
          {s.gameVersion === 'FC27' ? researchControl : !canRecommend && availabilityStatus &&
            <p className="ix-note">{availabilityStatus}</p>}

          <h2>Formation & Position</h2>
          {Object.keys(formations).length > 0 && (
            <div className="ix-row">
              <Field label="Formation">
                <StadiumSelect
                  aria-label="Formation"
                  value={s.formation ?? ''}
                  onChange={val => set({ formation: val, slot: '' })}
                >
                  <option value="">Standalone position</option>
                  {Object.keys(formations).map(formation => <option key={formation} value={formation}>{formation}</option>)}
                </StadiumSelect>
              </Field>
              {s.formation && (
                <Field label="Formation slot" hint="Tactical emphasis uses the app’s formation model">
                  <StadiumSelect
                    aria-label="Formation slot"
                    value={s.slot ?? ''}
                    onChange={val => {
                      const assignment = slots.find(slot => slot.slot === val)
                      set({ slot: assignment?.slot ?? '', position: assignment?.position ?? s.position })
                    }}
                  >
                    <option value="">Choose a slot</option>
                    {slots.map(slot => (
                      <option key={slot.slot} value={slot.slot}>
                        {slot.slot} · {slot.position} · {slot.duty.toLowerCase()}
                      </option>
                    ))}
                  </StadiumSelect>
                </Field>
              )}
            </div>
          )}

          <Field label="Position">
            <StadiumSelect
              aria-label="Position"
              disabled={!!s.formation}
              value={s.position}
              onChange={val => set({ position: val })}
            >
              {POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
            </StadiumSelect>
          </Field>

          {/* Miniature Tactical Pitch Context */}
          <TacticalPreview
            formation={s.formation}
            slot={s.slot || s.position}
            tacticalStyle={s.tactical}
            slots={slots}
          />

          <h2>Division</h2>
          {s.gameVersion === 'FC27' ? (
            <fieldset className="ix-row">
              <legend>Choose explicitly — nothing is selected for you</legend>
              {([['MEN', "Men's Football"], ['WOMEN', "Women's Football"], ['BOTH', 'Both (mixed pool)']] as const).map(([k, label]) => (
                <label key={k} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    name="division"
                    checked={s.division === k}
                    onChange={() => set({ division: k })}
                  />{' '}
                  {label}
                </label>
              ))}
            </fieldset>
          ) : <p className="ix-note">FC26 has no division label, so no division filter applies.</p>}

          <h2>Tactical Style</h2>
          <StadiumSelect
            aria-label="Tactical style"
            value={s.tactical}
            onChange={val => set({ tactical: val })}
          >
            {TACTICS.map(t => <option key={t} value={t}>{t}</option>)}
          </StadiumSelect>

          <details
            className="st3-disclosure"
            open={!!(s.secondary || s.lam != null || s.preferredAttribute || s.playstylePlus)}
          >
            <summary>Optional Preferences</summary>
            <div className="stack gap07 mt05">
              <div className="ix-row">
                <Field label="Secondary style">
                  <StadiumSelect
                    aria-label="Secondary style"
                    value={s.secondary}
                    onChange={val => set({ secondary: val })}
                  >
                    <option value="">None</option>
                    {TACTICS.map(t => <option key={t} value={t}>{t}</option>)}
                  </StadiumSelect>
                </Field>
                <Field label="Tactical emphasis" hint="engine default 0.70">
                  <StadiumSelect
                    aria-label="Tactical emphasis"
                    value={s.lam != null ? String(s.lam) : ''}
                    onChange={val => set({ lam: val === '' ? null : Number(val) })}
                  >
                    <option value="">Engine default</option>
                    <option value="0.5">Lower (0.50)</option>
                    <option value="0.9">Higher (0.90)</option>
                  </StadiumSelect>
                </Field>
              </div>

              <div className="ix-row">
                <Field label="Preferred attribute">
                  <StadiumSelect
                    aria-label="Preferred attribute"
                    value={s.preferredAttribute && preferencesAt(s.position).includes(s.preferredAttribute) ? s.preferredAttribute : ''}
                    onChange={val => set({ preferredAttribute: val })}
                  >
                    <option value="">None</option>
                    {preferencesAt(s.position).map(attribute => (
                      <option key={attribute} value={attribute}>{attribute.replace(/_/g, ' ')}</option>
                    ))}
                  </StadiumSelect>
                </Field>
                <Field label="Preferred PlayStyle+">
                  <StadiumCombobox
                    ariaLabel="Preferred PlayStyle+"
                    placeholder="e.g. Finesse Shot+"
                    value={s.playstylePlus ?? ''}
                    onChange={val => set({ playstylePlus: val })}
                  />
                </Field>
              </div>
            </div>
          </details>

          <div className="ix-sticky-submit">
            <button className="btn primary w-full" disabled={!req || busy} onClick={submit}>
              {busy ? 'Scoring Candidates...' : 'Find players'}
            </button>
          </div>
        </section>

        {/* Center: Ranked Results Workspace */}
        <section className="card stack ix-results" aria-label="Recommendation results">
          <div className="row justify-between align-center">
            <h2 className="mb0">Recommendation Results</h2>
            {result && <span className="badge outline">{result.ranked.length} candidates evaluated</span>}
          </div>

          {!busy && !error && !result && (
            <div className="empty-results-guide stack gap1" style={{ padding: '1rem 0' }}>
              <div>
                <h3 className="mb02 row align-center gap05" style={{ fontSize: '1.1rem' }}>
                  <StadiumIcon name="dashboard" size={18} />
                  <span>Scouting Mission Briefing</span>
                </h3>
                <p className="muted small mb0">
                  Ready to evaluate candidates for <strong>{activeRoleName}</strong> in a <strong>{s.tactical.replace(/_/g, ' ')}</strong> system ({s.gameVersion}).
                </p>
              </div>

              <div className="row gap1 wrap pt05 border-t">
                <div className="flex1" style={{ minWidth: '160px', padding: '0.65rem 0.75rem', background: 'var(--surface-inset)' }}>
                  <div className="tiny muted uppercase letter-spacing">Target Slot</div>
                  <div className="mt02" style={{ fontWeight: 600, color: 'var(--accent-lime)' }}>{activeRoleName}</div>
                </div>
                <div className="flex1" style={{ minWidth: '160px', padding: '0.65rem 0.75rem', background: 'var(--surface-inset)' }}>
                  <div className="tiny muted uppercase letter-spacing">Tactical System</div>
                  <div className="mt02" style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>{s.tactical.replace(/_/g, ' ')}</div>
                </div>
                <div className="flex1" style={{ minWidth: '160px', padding: '0.65rem 0.75rem', background: 'var(--surface-inset)' }}>
                  <div className="tiny muted uppercase letter-spacing">Scoring Model</div>
                  <div className="mt02" style={{ fontWeight: 600 }}>V3.2.1 Engine (λ = {s.lam ?? '0.70'})</div>
                </div>
              </div>

              <p className="muted small mb0 pt05 border-t" style={{ maxWidth: '64ch' }}>
                <strong>How recommendations work:</strong> Candidates are scored on tactical fit, position suitability, and published PlayStyles with zero fabricated market prices or chemistry offsets.
              </p>

              <button className="btn ghost row align-center gap05" disabled={!req || busy} onClick={submit} style={{ alignSelf: 'flex-start' }}>
                <StadiumIcon name="zap" size={14} />
                <span>Score Eligible Candidates</span>
              </button>
            </div>
          )}

          {busy && <Loading label="Scoring candidate pool with V3.2 engine" />}
          <ErrorBox error={error} />
          {result && (
            <ErrorBoundary key={result.request_id}>
              {lastReq && (
                <p className="ix-scope" data-testid="submitted-request">
                  Results for {lastReq.game_version} · {lastReq.position} · {lastReq.tactical_profile.replace(/_/g, ' ').toLowerCase()}
                  {lastReq.formation ? ` · ${lastReq.formation} ${lastReq.slot}` : ''}
                  {lastReq.division ? ` · ${lastReq.division}` : lastReq.game_version === 'FC27' ? ' · Both divisions' : ''}
                  {lastReq.secondary_tactical_profile ? ` · Secondary ${lastReq.secondary_tactical_profile.replace(/_/g, ' ').toLowerCase()}` : ''}
                  {lastReq.lam != null ? ` · Emphasis ${lastReq.lam.toFixed(2)}` : ''}
                  {lastReq.attribute_preferences?.map(p => ' · Prefer ' + p.attribute.replace(/_/g, ' '))}
                  {lastReq.desired_playstyles_plus?.map(p => ' · Prefer ' + p.replace(/\+$/, '') + '+')}
                </p>
              )}
              <ScopeBanner division={result.division} />
              {result.leading_pair && <LeaderEvidence pair={result.leading_pair} />}
              {result.ranked.length === 0 ? (
                <p role="status" className="ix-scope">
                  No eligible players for this request ({result.counts?.candidates ?? 0} candidates considered, {result.counts?.excluded ?? 0} excluded by eligibility gates).
                </p>
              ) : (
                <>
                  <p className="ix-note">
                    Select 2–{MAX_COMPARE} players to compare{selected.length >= MAX_COMPARE ? ' (maximum reached)' : ''}.
                  </p>
                  <Ladder ranked={result.ranked} selected={selected} onToggle={toggle} onInspect={e => inspect(e.entity_id)} />
                  <button className="btn" disabled={selected.length < 2} onClick={runCompare}>
                    Compare {selected.length} players
                  </button>
                  <ErrorBox error={cmpErr} />
                  {lastReq && result.feedback_receipt && result.ranked.filter(player => selected.includes(player.entity_id)).map(player => (
                    <RecommendationFeedback key={player.entity_id} result={result} player={player} version={lastReq.game_version} />
                  ))}
                  {cmp && <ComparePanel response={cmp} />}
                  {lastReq && <WhatIfPanel key={result.request_id} request={lastReq} slots={formations[lastReq.formation ?? ''] ?? []} />}
                </>
              )}
            </ErrorBoundary>
          )}
        </section>

        {/* Right Rail: Contextual Scouting Inspector */}
        <aside className="card workspace-rail workspace-insights ix-inspector" aria-label="Recommendation explanation">
          <h2>Why this recommendation?</h2>
          {inspected && result ? (
            <>
              <div className="row align-center gap07 mb05">
                <PlayerIdentity name={inspected.name} />
                <div className="flex1">
                  <h3 className="mb02" style={{ fontSize: '1.2rem' }}>{inspected.name}</h3>
                  <span className="tiny muted">{inspected.player.club || inspected.player.nation || activeRoleName}</span>
                </div>
              </div>

              <div className="mt05 mb07">
                <SuitabilityScore
                  score={inspected.score}
                  contextLabel="V3.2 Suitability Score"
                  subtitle={`${Math.round(inspected.coverage * 100)}% evidence coverage`}
                />
              </div>

              <div className="mb07">
                <EvidenceBadge
                  status={inspected.confidence?.level}
                  label={`Confidence: ${inspected.confidence?.level ?? 'n/a'}`}
                />
              </div>

              <div className="callout info small mb07">
                {Math.round(inspected.coverage * 100)}% evidence coverage · Confidence: {inspected.confidence?.level ?? 'n/a'}
              </div>

              <h3>Key factors</h3>
              <ul className="reasons">
                {inspected.explanation.reasons.map((reason, i) => <li key={i}>{reason}</li>)}
              </ul>

              {inspected.explanation.trade_offs.length > 0 && (
                <>
                  <h3>Trade-offs</h3>
                  <ul className="reasons">
                    {inspected.explanation.trade_offs.map((reason, i) => <li key={i}>{reason}</li>)}
                  </ul>
                </>
              )}

              {inspected.evidence.missing_attributes.length > 0 && (
                <p className="tiny muted mt05">
                  Missing attributes: {inspected.evidence.missing_attributes.join(', ')}
                </p>
              )}

              {inspected.near_tie_with_next?.within_noise_threshold && (
                <p className="callout warn small mt05">Effectively tied with the following recommendation.</p>
              )}

              <div className="mt1 pt07" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                <button
                  type="button"
                  className={`btn sm w-full ${selected.includes(inspected.entity_id) ? 'outline' : 'secondary'}`}
                  onClick={() => toggle(inspected)}
                >
                  {selected.includes(inspected.entity_id) ? '✓ In comparison' : '+ Add to comparison'}
                </button>
              </div>

              <p className="ix-note mt07">
                {lastReq?.game_version} · Engine {result.engine_version} · Config {result.config_version}
                {typeof result.dataset?.reference_distribution === 'string' && ' · ' + result.dataset.reference_distribution}
              </p>
            </>
          ) : (
            <div className="empty-inspector-guide stack gap07">
              {/* Dynamic Tactical Profile Guidance */}
              <div style={{ padding: '0.75rem', background: 'var(--surface-inset)' }}>
                <div className="row justify-between align-center mb02">
                  <span className="tiny muted uppercase letter-spacing">Tactical Demand Blueprint</span>
                  <span className="badge lime" style={{ fontSize: '0.72rem' }}>{activeRoleName}</span>
                </div>
                <h3 className="mb02" style={{ color: 'var(--accent-lime)' }}>{s.tactical.replace(/_/g, ' ')}</h3>
                <p className="tiny muted mb05">{currentTacticalProfile.description}</p>
                <div className="tiny" style={{ color: 'var(--accent-cyan)' }}>
                  Ideal Role: {currentTacticalProfile.idealDuty}
                </div>
              </div>

              {/* Demanded Attributes */}
              <div>
                <label className="section-title mb02" style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-tertiary)' }}>
                  Demanded Attributes
                </label>
                <div className="row gap03 wrap mt02">
                  {currentTacticalProfile.keyAttributes.map(attr => (
                    <span key={attr} className="badge outline" style={{ fontSize: '0.72rem', padding: '0.2rem 0.5rem' }}>
                      {attr}
                    </span>
                  ))}
                </div>
              </div>

              {/* Benchmark PlayStyles */}
              <div>
                <label className="section-title mb02" style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-tertiary)' }}>
                  Benchmark PlayStyles
                </label>
                <div className="row gap03 wrap mt02">
                  {currentTacticalProfile.recommendedPlayStyles.map(ps => (
                    <span key={ps} className="badge gold" style={{ fontSize: '0.72rem', padding: '0.2rem 0.5rem' }}>
                      {ps}
                    </span>
                  ))}
                </div>
              </div>

              <div className="pt05 border-t small">
                <strong>V3.2.1 Engine Formula:</strong>
                <p className="tiny muted mt02 mb0">
                  Suitability = (1 - λ) · Baseline + λ · TacticalFit.
                  With λ = {s.lam ?? '0.70'}, 70% of candidate rank reflects your exact tactical demands.
                </p>
              </div>

              <p className="muted tiny mb0">
                Select <strong>Find players</strong> to rank candidates, then click any card to inspect detailed trade-offs.
              </p>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
