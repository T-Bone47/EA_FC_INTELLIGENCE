import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, qs } from '../api/client'
import type {
  AttributePreferenceIn, FitValue, RecommendationRequest,
  RecommendationResponse, ReferenceData, SquadSummary,
} from '../api/types'
import { useApi, useAction } from '../lib/useApi'
import { useSession } from '../state/session'
import {
  ConfidenceBadge, ErrorBox, FitBadge, Loading, ScoreBar, Empty,
} from '../components/common'
import { UNKNOWN_LABEL, prettyAttr, prettyEnum } from '../lib/format'

const COMPONENTS = ['overall_quality', 'attribute_fit', 'position_fit',
                    'tactical_fit', 'playstyle_fit', 'role_fit', 'team_fit'] as const

const ATTR_CODES = [
  'pace', 'shooting', 'passing', 'dribbling', 'defending', 'physicality',
  'acceleration', 'sprint_speed', 'finishing', 'shot_power', 'long_shots',
  'volleys', 'penalties', 'positioning', 'vision', 'crossing', 'short_passing',
  'long_passing', 'curve', 'free_kick_accuracy', 'ball_control', 'agility',
  'balance', 'dribbling_detail', 'defensive_awareness', 'interceptions',
  'standing_tackle', 'sliding_tackle', 'heading_accuracy', 'strength',
  'stamina', 'aggression', 'jumping', 'reactions', 'composure',
  'gk_diving', 'gk_handling', 'gk_kicking', 'gk_positioning', 'gk_reflexes',
]

interface Draft extends RecommendationRequest {
  parsed_from?: string
  confidence_notes?: string[]
}

export default function Recommend() {
  const { gameVersion, user, notify } = useSession()
  const [params] = useSearchParams()
  const ref = useApi<ReferenceData>(`/api/meta/reference${qs({ game_version: gameVersion })}`, [gameVersion])
  const squads = useApi<SquadSummary[]>(user ? '/api/squads' : null, [user])

  const [position, setPosition] = useState(params.get('position') ?? '')
  const [formation, setFormation] = useState('')
  const [tactical, setTactical] = useState('BALANCED')
  const [role, setRole] = useState('')
  const [prefs, setPrefs] = useState<AttributePreferenceIn[]>([])
  const [playstyles, setPlaystyles] = useState<string[]>([])
  const [playstylesPlus, setPlaystylesPlus] = useState<string[]>([])
  const [budget, setBudget] = useState('')
  const [minOvr, setMinOvr] = useState('')
  const [strict, setStrict] = useState(false)
  // v2.1 intelligence inputs (all optional — empty/false = exact legacy behavior)
  const [secondaryTactical, setSecondaryTactical] = useState('')
  const [archetype, setArchetype] = useState('')
  const [mustHave, setMustHave] = useState('')
  const [qualityBias, setQualityBias] = useState('')
  const [enableInteractions, setEnableInteractions] = useState(false)
  const [enableSaturation, setEnableSaturation] = useState(false)
  const [enablePlaystyleContext, setEnablePlaystyleContext] = useState(false)
  const [limit, setLimit] = useState(10)
  const [squadId, setSquadId] = useState('')
  const [nlText, setNlText] = useState('')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    const p = params.get('position')
    if (p) setPosition(p.toUpperCase())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params])

  const noData = ref.data?.status === 'NO_DATA'

  const buildRequest = useMemo(() => (): RecommendationRequest => ({
    game_version: gameVersion,
    position: position || null,
    formation: formation || null,
    tactical_profile: tactical,
    role: role || null,
    attribute_preferences: prefs.filter((p) => p.min_value || p.target_value),
    desired_playstyles: playstyles,
    desired_playstyles_plus: playstylesPlus,
    budget_coins: budget ? Number(budget) : null,
    min_overall: minOvr ? Number(minOvr) : null,
    squad_id: squadId || null,
    entity_scope: 'game_player',
    strict_tactics: strict,
    limit,
    secondary_tactical_profile: secondaryTactical || null,
    archetype: archetype || null,
    required_playstyles: mustHave.split(',').map((x) => x.trim()).filter(Boolean),
    overall_quality_bias: (qualityBias || null) as 'low' | 'normal' | 'high' | null,
    enable_interactions: enableInteractions,
    enable_saturation: enableSaturation,
    enable_playstyle_context: enablePlaystyleContext,
  }), [gameVersion, position, formation, tactical, role, prefs, playstyles,
       playstylesPlus, budget, minOvr, squadId, strict, limit,
       secondaryTactical, archetype, mustHave, qualityBias,
       enableInteractions, enableSaturation, enablePlaystyleContext])

  const act = useAction(async () => api.post<RecommendationResponse>('/api/recommendations', buildRequest()))
  const parseAct = useAction(async () => {
    const r = await api.post<{ draft: Draft; note: string }>(
      '/api/recommendations/parse-intent', { text: nlText, game_version: gameVersion })
    setDraft(r.draft)
    return r
  })

  function applyDraft() {
    if (!draft) return
    if (draft.position) setPosition(draft.position)
    if (draft.formation) setFormation(draft.formation)
    if (draft.tactical_profile) setTactical(draft.tactical_profile)
    if (draft.budget_coins != null) setBudget(String(draft.budget_coins))
    if (draft.attribute_preferences?.length) setPrefs(draft.attribute_preferences)
    if (draft.desired_playstyles?.length) setPlaystyles(draft.desired_playstyles)
    if (draft.secondary_tactical_profile) setSecondaryTactical(draft.secondary_tactical_profile)
    if (draft.archetype) setArchetype(draft.archetype)
    if (draft.required_playstyles?.length) setMustHave(draft.required_playstyles.join(', '))
    if (draft.overall_quality_bias) setQualityBias(draft.overall_quality_bias)
    setDraft(null)
    notify('ok', 'Draft applied to the form — review before running.')
  }

  async function sendFeedback(rec: RecommendationResponse, entityId: string,
                              entityType: string, action: 'SELECTED' | 'REJECTED') {
    if (!user) { notify('info', 'Log in to record feedback.'); return }
    try {
      await api.post('/api/feedback', {
        recommendation_id: rec.request_id, action,
        entity_type: entityType, entity_id: entityId,
        game_version: gameVersion,
        request_context: { position, tactical_profile: tactical, squad_id: squadId || null },
      })
      notify('ok', `Feedback recorded: ${action}.`)
    } catch (e: any) {
      notify('bad', e.detail || 'Feedback failed.', e.requestId)
    }
  }

  const res = act.result

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="mb0">Recommendation workflow</h1>
          <div className="sub small">
            Deterministic best-fit ranking for <strong>{gameVersion}</strong> · every score
            ships with its evidence · UNKNOWN components are excluded from weighting, never faked.
          </div>
        </div>
      </div>

      {noData && (
        <div className="callout warn mb2">
          <div className="t">{gameVersion}: NO_DATA</div>
          <div className="small">
            The engine is version-aware and ready, but zero {gameVersion} production
            records exist. Requests will return an explicit 404 — the honest answer.
            Nothing will be backfilled from FC26 and nothing is fabricated.
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(300px, 380px) 1fr', gap: '1rem', alignItems: 'start' }}
           className="recommend-layout">
        {/* ---------------------------------------------------------- form */}
        <div className="stack">
          <div className="card">
            <div className="section-title">Natural language (optional)</div>
            <textarea className="textarea" maxLength={1000} value={nlText}
                      placeholder="e.g. need a right winger for counter attack, budget 100k"
                      onChange={(e) => setNlText(e.target.value)} />
            <div className="row mt1">
              <button className="btn sm" disabled={parseAct.pending || nlText.trim().length < 3}
                      onClick={() => parseAct.run()}>
                {parseAct.pending ? 'Parsing…' : 'Parse intent'}
              </button>
              <span className="tiny faint">Deterministic parser — never invents values.</span>
            </div>
            <ErrorBox error={parseAct.error} />
            {draft && (
              <div className="callout ok mt1">
                <div className="t">Parsed draft</div>
                <pre className="tiny mono" style={{ whiteSpace: 'pre-wrap', margin: '.3rem 0' }}>
                  {JSON.stringify({ ...draft, confidence_notes: undefined }, null, 1)}
                </pre>
                {(draft.confidence_notes ?? []).map((n) => (
                  <div key={n} className="tiny faint">· {n}</div>
                ))}
                <div className="row mt1">
                  <button className="btn primary sm" onClick={applyDraft}>Apply to form</button>
                  <button className="btn ghost sm" onClick={() => setDraft(null)}>Discard</button>
                </div>
              </div>
            )}
          </div>

          <div className="card">
            <div className="section-title">Your context</div>
            <div className="col">
              <div className="field">
                <label>Target position</label>
                <div className="chips">
                  <button className={`chip ${!position ? 'on' : ''}`} onClick={() => setPosition('')}>Any</button>
                  {(ref.data?.positions ?? []).map((p) => (
                    <button key={p} className={`chip ${position === p ? 'on' : ''}`}
                            onClick={() => setPosition(position === p ? '' : p)}>{p}</button>
                  ))}
                </div>
              </div>
              <div className="row">
                <div className="field flex1">
                  <label>Formation</label>
                  <select className="select" value={formation} onChange={(e) => setFormation(e.target.value)}>
                    <option value="">— optional —</option>
                    {Object.keys(ref.data?.formations ?? {}).map((f) => (
                      <option key={f} value={f}>{f}</option>))}
                  </select>
                </div>
                <div className="field flex1">
                  <label>Tactical profile</label>
                  <select className="select" value={tactical} onChange={(e) => setTactical(e.target.value)}>
                    {(ref.data?.tactical_profiles ?? ['BALANCED']).map((t) => (
                      <option key={t} value={t}>{prettyEnum(t)}</option>))}
                  </select>
                </div>
              </div>
              <div className="field">
                <label>Role (optional)</label>
                <input className="input" maxLength={60} value={role} placeholder="e.g. Mezzala"
                       onChange={(e) => setRole(e.target.value)} />
                <span className="tiny faint">
                  Role data: {ref.data?.capabilities?.roles_available
                    ? 'available' : 'NOT VERIFIED for this version — role fit stays UNKNOWN unless a matching definition exists.'}
                </span>
              </div>
              <div className="row">
                <div className="field flex1">
                  <label>Budget (coins)</label>
                  <input className="input" type="number" min={0} value={budget} placeholder="—"
                         onChange={(e) => setBudget(e.target.value)} />
                </div>
                <div className="field flex1">
                  <label>Min overall</label>
                  <input className="input" type="number" min={1} max={99} value={minOvr} placeholder="—"
                         onChange={(e) => setMinOvr(e.target.value)} />
                </div>
                <div className="field" style={{ width: 88 }}>
                  <label>Results</label>
                  <input className="input" type="number" min={1} max={50} value={limit}
                         onChange={(e) => setLimit(Math.max(1, Math.min(50, Number(e.target.value) || 10)))} />
                </div>
              </div>
              {budget && (
                <div className="callout warn small">
                  Market prices are NOT verified for {gameVersion}. The budget is
                  recorded and surfaced as <strong>BUDGET_UNVERIFIED</strong> — candidates
                  are never assumed affordable.
                </div>
              )}
              <div className="field">
                <label>Squad context (optional)</label>
                <select className="select" value={squadId} disabled={!user}
                        onChange={(e) => setSquadId(e.target.value)}>
                  <option value="">{user ? '— none —' : 'Log in to use a squad'}</option>
                  {(squads.data ?? []).filter((s) => s.game_version === gameVersion).map((s) => (
                    <option key={s.id} value={s.id}>{s.name} ({s.formation})</option>))}
                </select>
                <span className="tiny faint">
                  Adds real link facts (club/league/nation) to team_fit evidence.
                </span>
              </div>
              <label className="checkbox">
                <input type="checkbox" checked={strict} onChange={(e) => setStrict(e.target.checked)} />
                Strict tactics — exclude candidates below the tactical floor instead of down-ranking
              </label>

              <div className="field mt2">
                <label>Intelligence layers <span className="tiny faint">(v2.1 — optional; off = baseline engine)</span></label>
                <div className="row">
                  <div className="field flex1">
                    <label className="tiny faint">+ Secondary tactics (combination)</label>
                    <select className="select" value={secondaryTactical}
                            onChange={(e) => setSecondaryTactical(e.target.value)}>
                      <option value="">— none —</option>
                      {(ref.data?.tactical_profiles ?? []).filter((t) => t !== tactical).map((t) => (
                        <option key={t} value={t}>{prettyEnum(t)}</option>))}
                    </select>
                  </div>
                  <div className="field flex1">
                    <label className="tiny faint">Archetype (computed, never assigned)</label>
                    <select className="select" value={archetype} onChange={(e) => setArchetype(e.target.value)}>
                      <option value="">— none —</option>
                      {Object.entries(ref.data?.archetypes ?? {}).map(([name, def]) => (
                        <option key={name} value={name} title={def.description}>{prettyEnum(name)}</option>))}
                    </select>
                  </div>
                </div>
                <div className="row">
                  <div className="field flex1">
                    <label className="tiny faint">Must-have PlayStyles (comma-separated, hard constraint)</label>
                    <input className="input" maxLength={160} value={mustHave} placeholder="e.g. Intercept, Tiki Taka"
                           onChange={(e) => setMustHave(e.target.value)} />
                  </div>
                  <div className="field" style={{ width: 150 }}>
                    <label className="tiny faint">OVR emphasis</label>
                    <select className="select" value={qualityBias} onChange={(e) => setQualityBias(e.target.value)}>
                      <option value="">normal</option>
                      <option value="low">low</option>
                      <option value="normal">normal</option>
                      <option value="high">high</option>
                    </select>
                  </div>
                </div>
                <label className="checkbox tiny">
                  <input type="checkbox" checked={enableInteractions} onChange={(e) => setEnableInteractions(e.target.checked)} />
                  Attribute interactions (pace+dribbling etc., all explainable)
                </label>
                <label className="checkbox tiny">
                  <input type="checkbox" checked={enableSaturation} onChange={(e) => setEnableSaturation(e.target.checked)} />
                  Diminishing returns above attribute knees
                </label>
                <label className="checkbox tiny">
                  <input type="checkbox" checked={enablePlaystyleContext} onChange={(e) => setEnablePlaystyleContext(e.target.checked)} />
                  Contextual PlayStyle value (PS+ never wins automatically)
                </label>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="section-title">Attribute requirements</div>
            {prefs.map((p, i) => (
              <div className="row mt1" key={i}>
                <select className="select flex1" value={p.attribute}
                        onChange={(e) => setPrefs(prefs.map((x, j) => j === i ? { ...x, attribute: e.target.value } : x))}>
                  {ATTR_CODES.map((a) => <option key={a} value={a}>{prettyAttr(a)}</option>)}
                </select>
                <input className="input" style={{ width: 72 }} type="number" min={1} max={99}
                       placeholder="min" value={p.min_value ?? ''}
                       onChange={(e) => setPrefs(prefs.map((x, j) => j === i
                         ? { ...x, min_value: e.target.value ? Number(e.target.value) : null } : x))} />
                <input className="input" style={{ width: 72 }} type="number" min={1} max={99}
                       placeholder="target" value={p.target_value ?? ''}
                       onChange={(e) => setPrefs(prefs.map((x, j) => j === i
                         ? { ...x, target_value: e.target.value ? Number(e.target.value) : null } : x))} />
                <button className="btn ghost sm" aria-label="Remove"
                        onClick={() => setPrefs(prefs.filter((_, j) => j !== i))}>×</button>
              </div>
            ))}
            <button className="btn ghost sm mt1" disabled={prefs.length >= 8}
                    onClick={() => setPrefs([...prefs, { attribute: 'stamina', min_value: null, target_value: null, weight: 1 }])}>
              + Add attribute
            </button>
          </div>

          <div className="card">
            <div className="section-title">Desired PlayStyles</div>
            <div className="chips">
              {(ref.data?.playstyles ?? []).map((p) => {
                const on = playstyles.includes(p.playstyle_name)
                return (
                  <button key={p.playstyle_name} className={`chip ${on ? 'on' : ''}`}
                          onClick={() => setPlaystyles(on
                            ? playstyles.filter((x) => x !== p.playstyle_name)
                            : playstyles.length >= 6 ? playstyles : [...playstyles, p.playstyle_name])}>
                    {p.playstyle_name}
                  </button>)
              })}
            </div>
            <div className="section-title mt2">PlayStyle+ demands</div>
            <div className="chips">
              {(ref.data?.playstyles ?? []).map((p) => {
                const on = playstylesPlus.includes(p.playstyle_name)
                return (
                  <button key={p.playstyle_name} className={`chip ${on ? 'on' : ''}`}
                          onClick={() => setPlaystylesPlus(on
                            ? playstylesPlus.filter((x) => x !== p.playstyle_name)
                            : playstylesPlus.length >= 3 ? playstylesPlus : [...playstylesPlus, p.playstyle_name])}>
                    {p.playstyle_name}+
                  </button>)
              })}
            </div>
            <div className="tiny faint mt1">
              Missing PlayStyle data on a candidate counts as UNKNOWN, not as “lacks it”.
            </div>
          </div>

          <button className="btn primary wide" style={{ padding: '.7rem' }}
                  disabled={act.pending} onClick={() => { setExpanded(null); act.run() }}>
            {act.pending ? <span className="spinner" aria-hidden /> : null}
            {act.pending ? 'Scoring candidates…' : `Run recommendation (${gameVersion})`}
          </button>
        </div>

        {/* ---------------------------------------------------------- results */}
        <div>
          <ErrorBox error={act.error} onRetry={() => act.run()} />
          {act.pending && <div className="card"><Loading label="Evaluating candidates" /></div>}
          {!act.pending && !act.error && !res && (
            <div className="card">
              <Empty title="No recommendation run yet"
                     hint="Set your context on the left and run the engine. Results are deterministic: the same request always produces the same ranking." />
            </div>
          )}
          {res && <Results res={res} expanded={expanded} setExpanded={setExpanded}
                           onFeedback={sendFeedback} authed={!!user} />}
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ results */
export function Results({ res, expanded, setExpanded, onFeedback, authed }: {
  res: RecommendationResponse
  expanded: string | null
  setExpanded: (id: string | null) => void
  onFeedback: (res: RecommendationResponse, entityId: string, entityType: string,
               action: 'SELECTED' | 'REJECTED') => void
  authed: boolean
}) {
  return (
    <div className="stack">
      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div className="section-title mb0">Summary</div>
          <div className="row tiny faint">
            <span>{res.evaluations_total.toLocaleString()} candidates evaluated</span>
            <span>· {res.timing_ms.toFixed(0)} ms</span>
            {res.engine_version && <span>· engine v{res.engine_version}</span>}
            <span>· request <code>{res.request_id.slice(0, 8)}</code></span>
          </div>
        </div>
        <p className="mt1">{res.explanations.summary}</p>
        {res.budget_status && !res.budget_status.startsWith('OK') && (
          <div className="callout warn small">{res.budget_status}</div>
        )}
        <div className="row mt1">
          <ConfidenceBadge score={res.confidence.score} />
          {res.confidence_v2 && (
            <span className="badge" title={res.confidence_v2.reasons.join(' · ')}>
              confidence v2: {res.confidence_v2.score_v2.toFixed(2)} · {prettyEnum(res.confidence_v2.level)}
            </span>
          )}
          {res.confidence.unknown_components.length > 0 && (
            <span className="badge unknown" title={res.confidence.notes.join(' · ')}>
              {res.confidence.unknown_components.length} component(s) UNKNOWN — weight redistributed
            </span>
          )}
        </div>
      </div>

      {res.best && (
        <div className="card" style={{ borderColor: 'var(--accent-dim)' }}>
          <div className="section-title">Best fit for THIS request</div>
          <div className="row" style={{ gap: '1rem', flexWrap: 'wrap' }}>
            <div className="score-hero"><span className="n">{res.best_score.toFixed(3)}</span>
              <span className="tiny faint">weighted suitability</span>
              {res.best.score_band && (
                <span className={`badge ${res.best.score_band.band === 'INSUFFICIENT_EVIDENCE' ? 'unknown' : ''}`}
                      style={{ marginTop: 6 }} title={res.best.score_band.meaning}>
                  {prettyEnum(res.best.score_band.band)}
                </span>
              )}
            </div>
            <div className="flex1">
              <h2 className="mb0">
                <Link to={`/players/${res.best.entity_id}`}>{res.best.name}</Link>
              </h2>
              <div className="tiny faint">
                {res.best.entity_type === 'game_player' ? 'GamePlayer' : 'UTCard'} · {res.best.entity_id.slice(0, 8)}…
              </div>
            </div>
            <div className="row">
              {authed && (
                <>
                  <button className="btn primary sm"
                          onClick={() => onFeedback(res, res.best!.entity_id, res.best!.entity_type, 'SELECTED')}>
                    👍 This one
                  </button>
                  <button className="btn ghost sm"
                          onClick={() => onFeedback(res, res.best!.entity_id, res.best!.entity_type, 'REJECTED')}>
                    👎 Not this
                  </button>
                </>
              )}
            </div>
          </div>
          {res.best.intelligence && (
            <div className="row tiny mt1" style={{ flexWrap: 'wrap', gap: 4 }}>
              {res.best.intelligence.dominant_archetype && (
                <span className="badge" title={res.best.intelligence.dominant_archetype.description}>
                  {prettyEnum(res.best.intelligence.dominant_archetype.archetype)} · derived
                  ({res.best.intelligence.dominant_archetype.score.toFixed(2)})
                </span>
              )}
              {(res.best.intelligence.gameplay_profile?.labels ?? []).map((l) => (
                <span key={l.label} className="badge" title={l.evidence ?? ''}>{prettyEnum(l.label)}</span>
              ))}
              {res.best.intelligence.versatility?.value != null && (
                <span className="badge faint" title={res.best.intelligence.versatility.reason ?? ''}>
                  versatility {(res.best.intelligence.versatility.value * 100).toFixed(0)}%
                </span>
              )}
              <span className="tiny faint">ENGINE-DERIVED analytics — not official EA attributes</span>
            </div>
          )}
          {res.explanations.why_this.length > 0 && (
            <ul className="reasons good small mt1">
              {res.explanations.why_this.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          )}
          <div className="grid g2 mt1">
            <div>
              <div className="section-title">Strengths</div>
              {res.explanations.strengths.length
                ? <ul className="reasons good small mb0">{res.explanations.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
                : <div className="small unknown-val">{UNKNOWN_LABEL}</div>}
            </div>
            <div>
              <div className="section-title">Concerns</div>
              {res.explanations.weaknesses.length
                ? <ul className="reasons bad small mb0">{res.explanations.weaknesses.map((s, i) => <li key={i}>{s}</li>)}</ul>
                : <div className="small muted mb0">None surfaced by the engine.</div>}
            </div>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 0 }}>
        <div className="section-title" style={{ padding: '1rem 1rem 0' }}>
          Ranked candidates ({res.ranked.length})
        </div>
        <table className="data">
          <thead>
            <tr>
              <th style={{ width: 30 }}>#</th><th>Player</th><th>Score</th>
              <th>Confidence</th><th style={{ textAlign: 'right' }}>Detail</th>
            </tr>
          </thead>
          <tbody>
            {res.ranked.map((r, i) => (
              <RankRow key={r.entity_id + i} rank={i + 1} r={r} res={res}
                       open={expanded === r.entity_id}
                       onToggle={() => setExpanded(expanded === r.entity_id ? null : r.entity_id)}
                       onFeedback={onFeedback} authed={authed} />
            ))}
          </tbody>
        </table>
      </div>

      {(res.excluded_hard.length > 0 || res.excluded_by_floor.length > 0) && (
        <div className="callout info small">
          Excluded honestly: {res.excluded_hard.length} hard-constraint violation(s),{' '}
          {res.excluded_by_floor.length} below the tactical floor
          {res.ranked.length === 0 && ' — no candidate passes; the engine will not pad the list'}.
        </div>
      )}

      {res.explanations.why_not_alternatives.length > 0 && (
        <div className="card">
          <div className="section-title">Why not the runners-up?</div>
          <div className="col">
            {res.explanations.why_not_alternatives.map((w) => (
              <div key={w.entity_id} className="card tight">
                <strong className="small">{w.name}</strong>
                <ul className="reasons bad small mb0 mt1">
                  {w.reasons.map((x, i) => <li key={i}>{x}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {(res.constraints || res.sensitivity || (res.counterfactuals?.length ?? 0) > 0) && (
        <div className="card">
          <div className="section-title">Decision intelligence</div>
          {res.constraints && (
            <div className="grid g3">
              <div>
                <div className="tiny faint">Constraints satisfied</div>
                <ul className="reasons good tiny">{res.constraints.satisfied.map((x, i) => <li key={i}>{x}</li>)}</ul>
              </div>
              <div>
                <div className="tiny faint">Failed</div>
                {res.constraints.failed.length
                  ? <ul className="reasons bad tiny">{res.constraints.failed.map((x, i) => <li key={i}>{x}</li>)}</ul>
                  : <div className="tiny muted">none</div>}
              </div>
              <div>
                <div className="tiny faint">Cannot verify (UNKNOWN)</div>
                {res.constraints.unknown.length
                  ? <ul className="reasons tiny">{res.constraints.unknown.map((x, i) => <li key={i}>{x}</li>)}</ul>
                  : <div className="tiny muted">none</div>}
              </div>
            </div>
          )}
          {res.sensitivity && (
            <div className="callout info small mt1">
              <strong>Sensitivity:</strong> {res.sensitivity.summary}
            </div>
          )}
          {(res.counterfactuals?.length ?? 0) > 0 && (
            <div className="mt1">
              <div className="tiny faint">Counterfactuals — what would change the recommendation</div>
              <ul className="reasons tiny mt1">
                {res.counterfactuals!.map((c, i) => (
                  <li key={i}>
                    <strong>If</strong> {c.if} <strong>then</strong> {c.then}
                    {c.changes_recommendation
                      ? <span className="badge warn" style={{ marginLeft: 6 }}>changes the pick</span>
                      : <span className="badge faint" style={{ marginLeft: 6 }}>pick holds</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="card">
        <div className="section-title">Weights & pareto dimensions</div>
        <div className="row small">
          {Object.entries(res.weights_used).map(([k, w]) => (
            <span key={k} className="badge">{prettyEnum(k)} {Math.round(w * 100)}%</span>
          ))}
        </div>
        <div className="grid g3 mt2">
          {Object.entries(res.pareto).filter(([k]) => k !== 'unavailable_dimensions').map(([k, v]) => (
            <div key={k} className="card tight">
              <div className="tiny faint">{prettyEnum(k.replace('best_', ''))}</div>
              <div className="small" style={{ fontWeight: 650 }}>
                {v ? (v as any).name ?? JSON.stringify(v).slice(0, 40) : <span className="unknown-val">UNAVAILABLE</span>}
              </div>
            </div>
          ))}
        </div>
        {Array.isArray((res.pareto as any).unavailable_dimensions) &&
         (res.pareto as any).unavailable_dimensions.length > 0 && (
          <div className="tiny faint mt1">
            Unavailable dimensions (missing verified data, never invented):{' '}
            {(res.pareto as any).unavailable_dimensions.map(prettyEnum).join(', ')}
          </div>
        )}
        <div className="tiny faint mt1">
          Data freshness: last source observation {res.data_freshness.last_source_observation
            ? new Date(res.data_freshness.last_source_observation).toLocaleString() : UNKNOWN_LABEL}
        </div>
      </div>
    </div>
  )
}

function RankRow({ rank, r, res, open, onToggle, onFeedback, authed }: {
  rank: number
  r: RecommendationResponse['ranked'][number]
  res: RecommendationResponse
  open: boolean
  onToggle: () => void
  onFeedback: (res: RecommendationResponse, entityId: string, entityType: string,
               action: 'SELECTED' | 'REJECTED') => void
  authed: boolean
}) {
  return (
    <>
      <tr>
        <td className="faint mono">{rank}</td>
        <td>
          <Link to={`/players/${r.entity_id}`} style={{ fontWeight: 600 }}>{r.name}</Link>
          {r.below_tactical_floor && <span className="badge warn" style={{ marginLeft: 6 }}>below tactical floor</span>}
          {r.hard_constraint_violation && <span className="badge bad" style={{ marginLeft: 6 }}>{r.hard_constraint_violation}</span>}
        </td>
        <td><ScoreBar score={r.weighted_score} /></td>
        <td><ConfidenceBadge score={r.confidence.score} /></td>
        <td style={{ textAlign: 'right' }}>
          <button className="btn ghost sm" onClick={onToggle} aria-expanded={open}>
            {open ? 'Hide' : 'Evidence'}
          </button>
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={5} style={{ background: 'var(--bg)' }}>
            <div className="grid g2" style={{ padding: '.4rem 0' }}>
              <div className="col">
                {COMPONENTS.map((c) => {
                  const fit: FitValue = (r.components as any)[c]
                  return (
                    <div key={c} className="card tight">
                      <div className="row" style={{ justifyContent: 'space-between' }}>
                        <strong className="small">{prettyEnum(c)}</strong>
                        <FitBadge fit={fit} />
                      </div>
                      {fit?.value != null && (
                        <div className="bar mt1"><span style={{ width: `${fit.value * 100}%` }} /></div>
                      )}
                      {fit?.reason && <div className="tiny faint mt1">{fit.reason}</div>}
                      {fit?.evidence?.length > 0 && (
                        <ul className="reasons tiny mt1" style={{ paddingLeft: '1rem' }}>
                          {fit.evidence.slice(0, 6).map((e, i) => <li key={i}>{e}</li>)}
                        </ul>
                      )}
                    </div>
                  )
                })}
              </div>
              <div className="col">
                <div className="card tight">
                  <div className="section-title">Confidence breakdown</div>
                  <div className="kv small">
                    <dt>Score</dt><dd className="mono">{r.confidence.score?.toFixed(2) ?? UNKNOWN_LABEL}</dd>
                    <dt>Evidence coverage</dt><dd className="mono">{Math.round((r.confidence.evidence_coverage ?? 0) * 100)}%</dd>
                    <dt>Known</dt><dd className="tiny">{r.confidence.known_components.map(prettyEnum).join(', ') || '—'}</dd>
                    <dt>Unknown</dt><dd className="tiny">{r.confidence.unknown_components.map(prettyEnum).join(', ') || '—'}</dd>
                  </div>
                  {r.confidence.notes.map((n, i) => (
                    <div key={i} className="tiny faint mt1">· {n}</div>))}
                </div>
                {authed && (
                  <div className="row">
                    <button className="btn primary sm"
                            onClick={() => onFeedback(res, r.entity_id, r.entity_type, 'SELECTED')}>
                      👍 Selected
                    </button>
                    <button className="btn ghost sm"
                            onClick={() => onFeedback(res, r.entity_id, r.entity_type, 'REJECTED')}>
                      👎 Rejected
                    </button>
                    <Link className="btn ghost sm" to={`/compare?ids=${res.best?.entity_id ?? ''},${r.entity_id}`}>
                      Compare with best
                    </Link>
                  </div>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
