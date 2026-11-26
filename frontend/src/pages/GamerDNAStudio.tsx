import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useSession } from '../state/session'
import { useCopilot, useCopilotRouteContext } from '../state/copilot'
import { EpistemicChip } from '../components/ui/StadiumPrimitives'
import { StadiumSelect } from '../components/StadiumControls'
import { StadiumIcon } from '../components/StadiumIcons'
import './GamerDNAStudio.css'

type DnaTab = 'IDENTITY' | 'PRO_MATCHING' | 'SKILL_GAP' | 'EVOLUTION' | 'SANDBOX' | 'GOVERNANCE'

const SANDBOX_MODES = [
  { value: 'SUPPORT_NATURAL_POSSESSION', label: 'Build XI to Support Natural Possession' },
  { value: 'SHIFT_COUNTER_ATTACK', label: 'Shift Toward Fast Counter-Attack' },
  { value: 'BALANCE_STABILITY_CREATIVITY', label: 'Balance Stability & Creativity' },
  { value: 'PRO_INSPIRED_TEMPLATE', label: 'Pro-Inspired Template (Metadata Structural)' },
  { value: 'NATURAL_VS_BALANCED', label: 'Natural Archetype vs Balanced Shape' },
]

const POS_OPTIONS = [
  { value: 'ST', label: 'ST' },
  { value: 'CAM', label: 'CAM' },
  { value: 'CM', label: 'CM' },
  { value: 'CDM', label: 'CDM' },
  { value: 'LW', label: 'LW' },
  { value: 'RW', label: 'RW' },
  { value: 'CB', label: 'CB' },
  { value: 'LB', label: 'LB' },
  { value: 'RB', label: 'RB' },
]

const STYLE_GROUPS: { key: string; label: string }[] = [
  { key: 'POSSESSION_BUILDUP', label: 'Group A · Possession & Build-Up' },
  { key: 'ATTACKING_IDENTITY', label: 'Group B · Attacking Identity' },
  { key: 'DEFENSIVE_IDENTITY', label: 'Group C · Defensive Identity' },
  { key: 'SPATIAL_TACTICAL', label: 'Group D · Spatial & Tactical' },
  { key: 'DECISION_PREFERENCE', label: 'Group E · Decision Preference' },
  { key: 'TACTICAL_ADAPTABILITY', label: 'Group F · Tactical Adaptability' },
]

function pct(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return 'N/A'
  return `${(Number(v) * 100).toFixed(1)}%`
}

export default function GamerDNAStudio() {
  const { user, gameVersion, notify } = useSession()
  const { openCopilot } = useCopilot()

  const [tab, setTab] = useState<DnaTab>('IDENTITY')
  const [patch, setPatch] = useState('ALL')
  const [loading, setLoading] = useState(false)

  const [profile, setProfile] = useState<Record<string, any> | null>(null)
  const [similarity, setSimilarity] = useState<Record<string, any> | null>(null)
  const [references, setReferences] = useState<Record<string, any> | null>(null)
  const [skillGap, setSkillGap] = useState<Record<string, any> | null>(null)
  const [evolution, setEvolution] = useState<Record<string, any> | null>(null)
  const [formations, setFormations] = useState<Record<string, any> | null>(null)
  const [pathway, setPathway] = useState<Record<string, any> | null>(null)
  const [feedbackItems, setFeedbackItems] = useState<Record<string, any>[]>([])

  // Recommendation & Sandbox state
  const [recPos, setRecPos] = useState('CM')
  const [recMode, setRecMode] = useState<'SUPPORT_NATURAL_STYLE' | 'COMPENSATE_WEAKNESS'>('SUPPORT_NATURAL_STYLE')
  const [playerRecs, setPlayerRecs] = useState<Record<string, any> | null>(null)
  const [sandboxMode, setSandboxMode] = useState('SUPPORT_NATURAL_POSSESSION')
  const [sandboxFormation, setSandboxFormation] = useState('')
  const [sandboxResult, setSandboxResult] = useState<Record<string, any> | null>(null)
  const [showAllFeatures, setShowAllFeatures] = useState(false)

  const gv = gameVersion === 'FC26' ? 'FC26' : 'FC27'

  useCopilotRouteContext({
    route_name: 'GAMER_DNA',
    game_version: gv,
    active_filters: { game_patch: patch, rec_mode: recMode, position: recPos },
  })

  async function loadAll() {
    if (!user) return
    setLoading(true)
    try {
      const [pRes, sRes, rRes, gRes, eRes, fRes, tRes, fbRes] = await Promise.all([
        api.get<Record<string, any>>(`/api/phase44/profile?game_version=${gv}&game_patch=${encodeURIComponent(patch)}`).catch(() => null),
        api.get<Record<string, any>>(`/api/phase44/similarity?game_version=${gv}&game_patch=${encodeURIComponent(patch)}`).catch(() => null),
        api.get<Record<string, any>>('/api/phase44/references').catch(() => null),
        api.get<Record<string, any>>(`/api/phase44/skill-gap?game_version=${gv}&game_patch=${encodeURIComponent(patch)}`).catch(() => null),
        api.get<Record<string, any>>(`/api/phase44/evolution?game_version=${gv}`).catch(() => null),
        api.get<Record<string, any>>(`/api/phase44/recommendations/formations?game_version=${gv}`).catch(() => null),
        api.get<Record<string, any>>(`/api/phase44/training-pathway?game_version=${gv}`).catch(() => null),
        api.get<{ items: Record<string, any>[] }>(`/api/phase44/feedback?game_version=${gv}`).catch(() => ({ items: [] })),
      ])
      if (pRes) setProfile(pRes)
      if (sRes) setSimilarity(sRes)
      if (rRes) setReferences(rRes)
      if (gRes) setSkillGap(gRes)
      if (eRes) setEvolution(eRes)
      if (fRes) setFormations(fRes)
      if (tRes) setPathway(tRes)
      setFeedbackItems(fbRes?.items || [])
      if (!pRes || !sRes) notify('bad', 'Some Gamer DNA endpoints failed to load cleanly.')
    } catch {
      notify('bad', 'Unable to load Gamer DNA V2 Studio data.')
    } finally {
      setLoading(false)
    }
  }

  async function loadPlayerRecs(nextPos = recPos, nextMode = recMode) {
    if (!user) return
    try {
      const res = await api.get<Record<string, any>>(
        `/api/phase44/recommendations/players?game_version=${gv}&position=${encodeURIComponent(nextPos)}&mode=${encodeURIComponent(nextMode)}&limit=5`
      )
      setPlayerRecs(res)
    } catch {
      notify('bad', 'Failed to load style-aware player picks.')
    }
  }

  useEffect(() => {
    loadAll()
  }, [user?.id, gv, patch])

  useEffect(() => {
    loadPlayerRecs()
  }, [user?.id, gv, recPos, recMode])

  const groupMeans = useMemo(() => {
    const feats = Object.values(profile?.style_features || {}) as Record<string, any>[]
    return STYLE_GROUPS.map(g => {
      const subset = feats.filter(f => f.feature_group === g.key && f.raw_value !== null && f.raw_value !== undefined)
      const avg = subset.length > 0 ? subset.reduce((s, f) => s + Number(f.raw_value), 0) / subset.length : null
      return {
        ...g,
        observedCount: subset.length,
        totalCount: feats.filter(f => f.feature_group === g.key).length,
        mean: avg,
      }
    })
  }, [profile])

  async function runSandbox(convertToExp = false) {
    if (!user) return
    try {
      const res = await api.post<Record<string, any>>('/api/phase44/sandbox/preview', {
        game_version: gv,
        game_patch: patch === 'ALL' ? 'PATCH_1.04' : patch,
        sandbox_mode: sandboxMode,
        formation: sandboxFormation || null,
        convert_to_experiment: convertToExp,
      })
      setSandboxResult(res)
      notify('ok', convertToExp ? 'Phase 43 Tactical Experiment created from Style Sandbox.' : 'Playing Style Sandbox XI preview updated (non-mutating).')
    } catch {
      notify('bad', 'Sandbox preview failed.')
    }
  }

  async function recordFeedback(action: 'ACCEPTED' | 'DEFERRED' | 'REJECTED', recType: string) {
    if (!user) return
    try {
      const saved = await api.post<Record<string, any>>('/api/phase44/feedback', {
        recommendation_id: `P44-${Date.now().toString().slice(-6)}`,
        recommendation_type: recType,
        game_version: gv,
        game_patch: patch === 'ALL' ? 'PATCH_1.04' : patch,
        user_action: action,
        profile_version_id: profile?.profile_version_id || null,
        similarity_run_id: similarity?.similarity_run_id || null,
      })
      setFeedbackItems(prev => [saved, ...prev])
      notify('ok', `Feedback (${action}) saved cleanly.`)
    } catch {
      notify('bad', 'Could not save style feedback.')
    }
  }

  async function handleReset() {
    if (!user) return
    try {
      await api.post('/api/phase44/reset', {})
      notify('ok', 'Phase 44 persisted profiles, similarity runs & feedback reset cleanly.')
      loadAll()
    } catch {
      notify('bad', 'Reset failed.')
    }
  }

  if (!user) {
    return (
      <section className="gdna-page">
        <div className="gdna-hero">
          <div>
            <h1>Gamer DNA V2 & Pro Style Matching Studio</h1>
            <p className="st3-subtitle">
              Sign in via <Link to="/account">Account</Link> to compute your 60-feature playing identity, inspect skill gaps separately from style similarity, and preview squads safely.
            </p>
          </div>
          <EpistemicChip kind="neutral" label="AUTH_REQUIRED" />
        </div>
      </section>
    )
  }

  const arch = profile?.archetype || {}
  const styleFeaturesList = Object.values(profile?.style_features || {}) as Record<string, any>[]
  const profFeaturesList = Object.values(profile?.proficiency_features || {}) as Record<string, any>[]

  return (
    <section className="gdna-page">
      <header className="gdna-hero">
        <div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center', marginBottom: '0.35rem' }}>
            <h1 style={{ margin: 0, display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
              <StadiumIcon name="dna" size={22} />
              Gamer DNA V2 & Style Matching
            </h1>
            <EpistemicChip kind={profile?.eligible_match_count > 0 ? 'observed' : 'neutral'} label={`${gv} · ${profile?.profile_maturity || 'COLD_START'}`} />
            <EpistemicChip kind="frozen" label="V3.2.1 Untouched" />
          </div>
          <p className="st3-subtitle" style={{ margin: 0 }}>
            Playing-style similarity reflects tactical geometry & decision preference (Groups A–F) strictly separated from Group G technical execution quality.
          </p>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.55rem', alignItems: 'center' }}>
          <div style={{ minWidth: '145px' }}>
            <StadiumSelect
              aria-label="Patch Scope"
              value={patch}
              onChange={setPatch}
              options={[
                { value: 'ALL', label: 'All Patches' },
                { value: 'PATCH_1.04', label: 'Patch 1.04' },
                { value: 'PATCH_1.03', label: 'Patch 1.03' },
              ]}
            />
          </div>
          <button
            type="button"
            className="btn primary sm"
            onClick={() => openCopilot({ prompt: 'Who plays most like my playing style and what are my top execution skill gaps?' })}
          >
            <StadiumIcon name="coach" size={15} />
            Ask AI Coach
          </button>
        </div>
      </header>

      <nav className="gdna-tabs" aria-label="Gamer DNA Sections">
        {(
          [
            ['IDENTITY', 'Style Identity (60D)', 'dna'],
            ['PRO_MATCHING', 'Pro Style Matching', 'shield'],
            ['SKILL_GAP', 'Elite Skill Gaps', 'activity'],
            ['EVOLUTION', 'Style Evolution', 'zap'],
            ['SANDBOX', 'Squad & Style Sandbox', 'sliders'],
            ['GOVERNANCE', 'Governance & Controls', 'info'],
          ] as [DnaTab, string, any][]
        ).map(([k, lbl, icon]) => (
          <button
            key={k}
            type="button"
            className={`gdna-tab-btn${tab === k ? ' active' : ''}`}
            onClick={() => setTab(k)}
          >
            <StadiumIcon name={icon} size={14} />
            {lbl}
          </button>
        ))}
      </nav>

      {loading && (
        <div className="gdna-card">
          <span className="gdna-num">Updating {gv} Gamer DNA V2 intelligence…</span>
        </div>
      )}

      {tab === 'IDENTITY' && (
        <div className="gdna-grid-2">
          <article className="gdna-card">
            <div className="gdna-kv">
              <h2 style={{ margin: 0, fontSize: '1.05rem' }}>Primary Playing Style Identity</h2>
              <span className="gdna-badge lime">{arch.primary_archetype || 'Unclassified'}</span>
            </div>
            <p style={{ margin: 0, fontSize: '0.88rem', color: '#cbd5e1' }}>{arch.summary}</p>
            <div className="gdna-grid-3">
              <div className="gdna-subbox">
                <span style={{ fontSize: '0.74rem', color: '#94a3b8' }}>Eligible Matches</span>
                <strong className="gdna-num">{profile?.eligible_match_count ?? 0}</strong>
              </div>
              <div className="gdna-subbox">
                <span style={{ fontSize: '0.74rem', color: '#94a3b8' }}>Style Feature Coverage</span>
                <strong className="gdna-num">{pct(profile?.overall_coverage)}</strong>
              </div>
              <div className="gdna-subbox">
                <span style={{ fontSize: '0.74rem', color: '#94a3b8' }}>Layer Active</span>
                <strong className="gdna-num">{arch.status || 'COLD_START_HINT'}</strong>
              </div>
            </div>

            <h3 style={{ margin: '0.35rem 0 0', fontSize: '0.92rem' }}>Top Archetype Affinities (Groups A–F)</h3>
            {(arch.archetypes || []).map((a: Record<string, any>) => (
              <div key={a.archetype} className="gdna-subbox">
                <div className="gdna-kv">
                  <strong>{a.archetype}</strong>
                  <span className="gdna-num">{(Number(a.affinity_score) * 100).toFixed(1)}% affinity</span>
                </div>
                <div className="gdna-bar-track">
                  <div className="gdna-bar-fill" style={{ width: `${Math.min(100, Math.round(Number(a.affinity_score) * 100))}%` }} />
                </div>
                <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>{a.rationale}</span>
              </div>
            ))}
          </article>

          <article className="gdna-card">
            <div className="gdna-kv">
              <h2 style={{ margin: 0, fontSize: '1.05rem' }}>Six Tactical Style Groups (A–F)</h2>
              <EpistemicChip kind="modelled" label="Missing stays N/A" />
            </div>
            {groupMeans.map(g => (
              <div key={g.key} className="gdna-subbox">
                <div className="gdna-kv">
                  <span>{g.label}</span>
                  <span className="gdna-num">
                    {g.mean !== null ? `${(g.mean * 100).toFixed(1)}%` : 'N/A'} ({g.observedCount}/{g.totalCount})
                  </span>
                </div>
                <div className="gdna-bar-track">
                  <div className="gdna-bar-fill" style={{ width: g.mean !== null ? `${Math.round(g.mean * 100)}%` : '0%' }} />
                </div>
              </div>
            ))}

            <div className="gdna-kv" style={{ marginTop: '0.35rem' }}>
              <strong style={{ fontSize: '0.88rem' }}>Group G · Technical Execution (Isolated from Style)</strong>
              <button type="button" className="btn ghost sm" onClick={() => setShowAllFeatures(s => !s)}>
                {showAllFeatures ? 'Hide 60-Feature Matrix' : 'Inspect All 60 Features'}
              </button>
            </div>
            <div className="gdna-grid-2">
              {profFeaturesList.slice(0, 4).map(f => (
                <div key={f.feature_id} className="gdna-subbox">
                  <div className="gdna-kv">
                    <span style={{ fontSize: '0.78rem' }}>{f.feature_id.replace(/_/g, ' ')}</span>
                    <strong className="gdna-num">{pct(f.raw_value)}</strong>
                  </div>
                </div>
              ))}
            </div>
          </article>

          {showAllFeatures && (
            <article className="gdna-card" style={{ gridColumn: '1 / -1' }}>
              <h3 style={{ margin: 0 }}>Complete 60-Feature Vector ({gv})</h3>
              <div className="gdna-table-wrap">
                <table className="gdna-table">
                  <thead>
                    <tr>
                      <th>Feature</th>
                      <th>Group</th>
                      <th>Raw Value</th>
                      <th>Source</th>
                      <th>Uncertainty (SE)</th>
                      <th>Matches</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...styleFeaturesList, ...profFeaturesList].map(f => (
                      <tr key={f.feature_id}>
                        <td>{f.feature_id}</td>
                        <td>{f.feature_group}{f.is_proficiency_only ? ' (Exec Only)' : ''}</td>
                        <td className="gdna-num">{pct(f.raw_value)}</td>
                        <td>{f.source_type}</td>
                        <td className="gdna-num">{f.uncertainty !== null && f.uncertainty !== undefined ? f.uncertainty.toFixed(3) : 'N/A'}</td>
                        <td className="gdna-num">{f.match_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          )}
        </div>
      )}

      {tab === 'PRO_MATCHING' && (
        <div className="gdna-grid-2">
          <article className="gdna-card">
            <div className="gdna-kv">
              <h2 style={{ margin: 0, fontSize: '1.05rem' }}>Governed Pro Style Comparison ({gv})</h2>
              <EpistemicChip kind={similarity?.abstained ? 'neutral' : 'observed'} label={similarity?.abstained ? 'ABSTAINED' : 'RIGHTS_VERIFIED'} />
            </div>

            {similarity?.abstained ? (
              <div className="gdna-abstain-banner">
                <strong>Pro Comparison Abstained Honestly (Fail-Closed Governance)</strong>
                <p style={{ margin: 0, fontSize: '0.86rem' }}>{similarity.abstention_reason}</p>
                <span style={{ fontSize: '0.82rem', color: '#cbd5e1' }}>
                  Fallback Archetype Identity: <strong>{similarity.fallback_archetype_summary}</strong>
                </span>
              </div>
            ) : (
              (similarity?.matches || []).map((m: Record<string, any>) => (
                <div key={m.reference_id} className="gdna-subbox">
                  <div className="gdna-kv">
                    <strong>#{m.rank_position} {m.public_alias}</strong>
                    <span className="gdna-badge lime">{m.interpretable_similarity_index}/100 Style Index</span>
                  </div>
                  <div className="gdna-kv" style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                    <span>90% Band: {m.confidence_band?.join('–')} · Rank Stability: {m.rank_stability_pct}%</span>
                    <span>Overlap: {(Number(m.feature_overlap_ratio) * 100).toFixed(0)}%</span>
                  </div>
                  {m.indistinguishable_note && (
                    <span style={{ fontSize: '0.78rem', color: '#fbbf24' }}>{m.indistinguishable_note}</span>
                  )}
                </div>
              ))
            )}
            <p style={{ margin: 0, fontSize: '0.78rem', color: '#94a3b8' }}>
              {similarity?.scale_disclosure} · {similarity?.disclaimer}
            </p>
          </article>

          <article className="gdna-card">
            <div className="gdna-kv">
              <h2 style={{ margin: 0, fontSize: '1.05rem' }}>EA FC Pro Candidate Registry</h2>
              <span className="gdna-badge">
                {references?.manifest?.authorized_profile_count ?? 0} Authorized / {references?.manifest?.total_candidates ?? 0} Tracked
              </span>
            </div>
            <div className="gdna-table-wrap">
              <table className="gdna-table">
                <thead>
                  <tr>
                    <th>Pro Alias</th>
                    <th>Rights Status</th>
                    <th>Matches</th>
                    <th>Edition Scope</th>
                  </tr>
                </thead>
                <tbody>
                  {(references?.candidates || []).map((c: Record<string, any>) => (
                    <tr key={c.reference_id}>
                      <td>{c.public_alias}</td>
                      <td><span className="gdna-badge">{c.rights_status}</span></td>
                      <td className="gdna-num">{c.reference_match_count}</td>
                      <td>{(c.applicable_editions || []).join(', ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </div>
      )}

      {tab === 'SKILL_GAP' && (
        <div className="gdna-grid-2">
          <article className="gdna-card">
            <div className="gdna-kv">
              <h2 style={{ margin: 0, fontSize: '1.05rem' }}>Priority Execution Gaps (Group G)</h2>
              <EpistemicChip kind={skillGap?.reference_population_verified ? 'observed' : 'hypothetical'} label={skillGap?.reference_scope || 'INTERNAL_BENCHMARK'} />
            </div>
            {(skillGap?.gaps || []).length === 0 ? (
              <p style={{ margin: 0, fontSize: '0.86rem', color: '#94a3b8' }}>
                No observed Group G execution gaps yet — log or analyze matches to reveal verified execution differentials.
              </p>
            ) : (
              (skillGap?.gaps || []).map((g: Record<string, any>) => (
                <div key={g.dimension} className="gdna-subbox">
                  <div className="gdna-kv">
                    <strong>{g.dimension.replace(/_/g, ' ')}</strong>
                    <span className="gdna-num">
                      You {pct(g.user_value)} vs Target {pct(g.reference_benchmark_value)}
                    </span>
                  </div>
                  <div className="gdna-bar-track">
                    <div className="gdna-bar-fill gap" style={{ width: `${Math.min(100, Math.round(Math.abs(Number(g.skill_gap_estimate || 0)) * 250))}%` }} />
                  </div>
                  <span style={{ fontSize: '0.78rem', color: '#e2e8f0' }}>Drill: {g.suggested_training_objective}</span>
                  <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>Tactic: {g.suggested_tactical_adjustment}</span>
                </div>
              ))
            )}
          </article>

          <article className="gdna-card">
            <h2 style={{ margin: 0, fontSize: '1.05rem' }}>Execution Strengths & Linked Training Pathway</h2>
            {(skillGap?.strengths || []).slice(0, 5).map((s: Record<string, any>) => (
              <div key={s.dimension} className="gdna-subbox">
                <div className="gdna-kv">
                  <span>{s.dimension.replace(/_/g, ' ')}</span>
                  <span className="gdna-badge">{s.status} · {pct(s.user_value)}</span>
                </div>
              </div>
            ))}
            <h3 style={{ margin: '0.4rem 0 0', fontSize: '0.9rem' }}>Training Academy Drills (Practice Only)</h3>
            {(pathway?.linked_exercises || []).slice(0, 3).map((ex: Record<string, any>) => (
              <div key={ex.exercise_id} className="gdna-subbox">
                <strong>{ex.title}</strong>
                <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>{ex.in_game_drill}</span>
              </div>
            ))}
          </article>
        </div>
      )}

      {tab === 'EVOLUTION' && (
        <article className="gdna-card">
          <div className="gdna-kv">
            <h2 style={{ margin: 0, fontSize: '1.05rem' }}>Rolling-Window Style Evolution ({evolution?.total_matches_evaluated ?? 0} Matches)</h2>
            <EpistemicChip kind={evolution?.shift_detected ? 'observed' : 'neutral'} label={evolution?.shift_detected ? 'SHIFT_DETECTED' : 'STABLE_IDENTITY'} />
          </div>
          <p style={{ margin: 0, fontSize: '0.88rem', color: '#cbd5e1' }}>{evolution?.shift_summary}</p>
          {(evolution?.experiment_attribution_notes || []).length > 0 && (
            <div className="gdna-subbox">
              <strong>Phase 43 Tactical Experiment Attributions</strong>
              {evolution?.experiment_attribution_notes.map((n: string, i: number) => (
                <span key={i} style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>{n}</span>
              ))}
            </div>
          )}
          <div className="gdna-grid-3">
            {(evolution?.windows || []).map((w: Record<string, any>) => (
              <div key={w.window_index} className="gdna-subbox">
                <div className="gdna-kv">
                  <strong>{w.window_label}</strong>
                  <span className="gdna-badge">{w.primary_archetype}</span>
                </div>
                <span className="gdna-num" style={{ fontSize: '0.78rem' }}>
                  Matches: {w.match_count} · Stability: {(Number(w.stability_score) * 100).toFixed(0)}%
                </span>
                {w.experiment_linked_id && (
                  <span className="gdna-badge lime">Linked Experiment: {w.experiment_linked_id}</span>
                )}
              </div>
            ))}
          </div>
        </article>
      )}

      {tab === 'SANDBOX' && (
        <div className="gdna-grid-2">
          <article className="gdna-card">
            <div className="gdna-kv">
              <h2 style={{ margin: 0, fontSize: '1.05rem' }}>Style-Aware Player Recommendations</h2>
              <EpistemicChip kind="frozen" label="V3.2.1 Base + Additive Style" />
            </div>
            <div className="gdna-grid-2">
              <StadiumSelect aria-label="Target Position" value={recPos} onChange={setRecPos} options={POS_OPTIONS} />
              <StadiumSelect
                aria-label="Recommendation Mode"
                value={recMode}
                onChange={v => setRecMode(v as 'SUPPORT_NATURAL_STYLE' | 'COMPENSATE_WEAKNESS')}
                options={[
                  { value: 'SUPPORT_NATURAL_STYLE', label: 'Support Natural Style' },
                  { value: 'COMPENSATE_WEAKNESS', label: 'Compensate Skill Gaps' },
                ]}
              />
            </div>
            {(playerRecs?.items || []).map((p: Record<string, any>) => (
              <div key={p.entity_id} className="gdna-subbox">
                <div className="gdna-kv">
                  <strong>{p.name} ({p.position} · {p.overall_rating ?? '—'} OVR)</strong>
                  <span className="gdna-num">V3.2.1: {p.frozen_v321_suitability} · Combined: {p.advisory_combined_score}</span>
                </div>
                <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>{p.style_rationale}</span>
              </div>
            ))}
            <h3 style={{ margin: '0.4rem 0 0', fontSize: '0.92rem' }}>Top Compatible Formations</h3>
            {(formations?.ranked_formations || []).slice(0, 3).map((f: Record<string, any>) => (
              <div key={f.formation} className="gdna-subbox">
                <div className="gdna-kv">
                  <strong>{f.formation} ({f.tactical_profile})</strong>
                  <span className="gdna-num">{(Number(f.theoretical_score) * 100).toFixed(1)} · {f.evidence_grade}</span>
                </div>
              </div>
            ))}
          </article>

          <article className="gdna-card">
            <div className="gdna-kv">
              <h2 style={{ margin: 0, fontSize: '1.05rem' }}>Interactive Playing Style Sandbox</h2>
              <EpistemicChip kind="hypothetical" label="NON_MUTATING_DRY_RUN" />
            </div>
            <StadiumSelect aria-label="Sandbox Mode" value={sandboxMode} onChange={setSandboxMode} options={SANDBOX_MODES} />
            <StadiumSelect
              aria-label="Sandbox Formation Override"
              value={sandboxFormation}
              onChange={setSandboxFormation}
              options={[
                { value: '', label: 'Auto Formation for Selected Mode' },
                { value: '4-2-3-1', label: '4-2-3-1' },
                { value: '4-3-3', label: '4-3-3' },
                { value: '4-4-2', label: '4-4-2' },
              ]}
            />
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              <button type="button" className="btn primary sm" onClick={() => runSandbox(false)}>
                Preview Sandbox XI
              </button>
              <button type="button" className="btn ghost sm" onClick={() => runSandbox(true)}>
                Convert to Phase 43 Experiment
              </button>
            </div>
            {sandboxResult && (
              <div className="gdna-subbox">
                <div className="gdna-kv">
                  <strong>{sandboxResult.formation} · {sandboxResult.objective}</strong>
                  <span className="gdna-badge">{sandboxResult.market_price_status}</span>
                </div>
                <span style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>{sandboxResult.description}</span>
                <span className="gdna-num" style={{ fontSize: '0.8rem' }}>
                  Utility U(S): {sandboxResult.preview_xi?.utility} · {sandboxResult.created_experiment ? `Experiment ${sandboxResult.created_experiment.experiment_id} Created` : 'Dry-Run Only'}
                </span>
              </div>
            )}
          </article>
        </div>
      )}

      {tab === 'GOVERNANCE' && (
        <div className="gdna-grid-2">
          <article className="gdna-card">
            <h2 style={{ margin: 0, fontSize: '1.05rem' }}>Closed-Loop Style Recommendation Feedback</h2>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              <button type="button" className="btn primary sm" onClick={() => recordFeedback('ACCEPTED', 'STYLE_IDENTITY_PROFILE')}>
                Accept Style Assessment
              </button>
              <button type="button" className="btn ghost sm" onClick={() => recordFeedback('DEFERRED', 'STYLE_FORMATION')}>
                Defer Recommendation
              </button>
              <button type="button" className="btn ghost sm" onClick={() => recordFeedback('REJECTED', 'STYLE_PLAYER')}>
                Reject Recommendation
              </button>
            </div>
            {feedbackItems.slice(0, 6).map(fb => (
              <div key={fb.feedback_id} className="gdna-subbox">
                <div className="gdna-kv">
                  <span>{fb.recommendation_type}</span>
                  <span className="gdna-badge">{fb.user_action}</span>
                </div>
              </div>
            ))}
          </article>

          <article className="gdna-card">
            <h2 style={{ margin: 0, fontSize: '1.05rem' }}>Epistemic Disclaimers & User Control</h2>
            {(profile?.limitations || []).map((l: string, i: number) => (
              <p key={i} style={{ margin: 0, fontSize: '0.83rem', color: '#cbd5e1' }}>· {l}</p>
            ))}
            <div style={{ marginTop: '0.5rem' }}>
              <button type="button" className="btn ghost sm" onClick={handleReset}>
                Reset Saved Phase 44 Profiles & Runs
              </button>
            </div>
          </article>
        </div>
      )}
    </section>
  )
}
