import { useState } from 'react'
import type { ApiError } from '../api/client'
import { ErrorBox, Loading } from '../components/common'
import { DecisionRange, LeaderEvidence } from './DecisionEvidence'
import { toApiError, whatIf } from './api'
import type { FormationSlot, RecommendRequest, WhatIfResponse, WhatIfVariant } from './types'

interface Preset { label: string; change: Omit<WhatIfVariant, 'label'> }

/** Only presets that differ from, and apply to, the current request. */
export function presetsFor(r: RecommendRequest, slots: FormationSlot[] = []): Preset[] {
  const out: Preset[] = []
  for (const [label, t] of [
    ['High press', 'HIGH_PRESS'], ['Low block', 'LOW_BLOCK'], ['Possession', 'POSSESSION'],
    ['Balanced', 'BALANCED'], ['Counterattack', 'COUNTER_ATTACK'], ['Direct play', 'DIRECT_PLAY'],
  ] as const)
    if (r.tactical_profile !== t &&
        !(t === 'HIGH_PRESS' && r.secondary_tactical_profile === 'LOW_BLOCK') &&
        !(t === 'LOW_BLOCK' && ['HIGH_PRESS', 'PRESSING'].includes(r.secondary_tactical_profile ?? ''))) out.push({ label, change: { tactical_profile: t } })
  if (!r.slot && r.position === 'CM') out.push({ label: 'CM → CAM', change: { position: 'CAM' } })
  if (!r.slot && r.position === 'CAM') out.push({ label: 'CAM → CM', change: { position: 'CM' } })
  if (r.slot) {
    for (const slot of slots.filter(slot => slot.slot !== r.slot && slot.position === r.position))
      out.push({ label: `Try ${slot.slot}`, change: { slot: slot.slot } })
  }
  if (r.game_version === 'FC27')
    for (const d of ["Men's Football", "Women's Football"] as const)
      if (r.division !== d) out.push({ label: `${d} only`, change: { division: d } })
  for (const lam of [0.5, 0.9]) if (r.lam !== lam) out.push({ label: `λ ${lam}`, change: { lam } })
  return out
}

/** Reruns the same engine for one change. Ranks, scores and deltas are rendered exactly as returned. */
export function WhatIfPanel({ request, slots = [] }: { request: RecommendRequest; slots?: FormationSlot[] }) {
  const [res, setRes] = useState<WhatIfResponse | null>(null)
  const [err, setErr] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)
  async function run(presets: Preset[]) {
    setBusy(true); setErr(null); setRes(null)
    try {
      setRes(await whatIf(request, presets.map(p => ({ label: p.label, ...p.change })), 10))
    } catch (e) {
      setErr(toApiError(e))
    } finally {
      setBusy(false)
    }
  }
  const presets = presetsFor(request, slots)
  const styles = presets.filter(p => p.change.tactical_profile)
  const v = res?.variants.length === 1 ? res.variants[0] : undefined
  return (
    <section className="ix-whatif" aria-label="What if">
      <h2>What if…</h2>
      <p className="ix-note">Each preset reruns the engine. Changing position or division can change which players qualify.</p>
      <div className="ix-row">
        {presets.map(p => <button key={p.label} className="btn sm" disabled={busy} onClick={() => run([p])}>{p.label}</button>)}
        <button className="btn sm" disabled={busy || !styles.length} onClick={() => run(styles.slice(0, 5))}>Compare tactical styles</button>
      </div>
      {busy && <Loading label="Re-scoring" />}
      <ErrorBox error={err} />
      {res && res.variants.length > 1 && <div style={{ overflowX: 'auto' }}>
        <h3>Tactical compatibility</h3>
        <p className="ix-note">Each style reuses the submitted position, formation and division.</p>
        <table className="data">
          <thead><tr><th>Style</th><th>Top player</th><th>Fit</th><th>Original leader rank</th><th>Lead evidence</th></tr></thead>
          <tbody>{res.variants.map(variant => {
            const winner = variant.top?.[0]
            const original = variant.tracked_from_base?.find(row => row.entity_id === res.base_top[0]?.entity_id)
            return <tr key={variant.label}>
              <th scope="row">{variant.label}</th>
              <td>{variant.error ? variant.detail ?? variant.error : winner?.name ?? 'Unavailable'}</td>
              <td>{winner?.score.toFixed(3) ?? '—'}</td>
              <td>{variant.error || !original ? '-' : original.new_rank ?? `Outside top ${res.ranking_depth}`}</td>
              <td>{variant.leading_pair ? <DecisionRange evidence={variant.leading_pair} /> : 'Unavailable'}</td>
            </tr>
          })}</tbody>
        </table>
      </div>}
      {v?.error && <p role="alert">{v.detail ?? v.error}</p>}
      {v && !v.error && (
        <>
          <h3>{v.label}</h3>
          {v.leading_pair && <LeaderEvidence pair={v.leading_pair} />}
          {res?.candidate_count !== undefined && v.candidate_count !== undefined &&
            <p>Candidate pool: {res.candidate_count} before, {v.candidate_count} after.</p>}
          <ul>
            {v.tracked_from_base?.map(t => (
              <li key={t.entity_id}>
                {t.name}: #{t.base_rank ?? '—'} → {t.new_rank === null ? `outside the top ${res!.ranking_depth}` : `#${t.new_rank}`}
                {t.score_delta !== null && <span className="ix-note"> ({t.score_delta >= 0 ? '+' : ''}{t.score_delta.toFixed(4)})</span>}
              </li>
            ))}
          </ul>
          {v.entered_top && v.entered_top.length > 0 && <p>Entered the top 10: {v.entered_top.join(', ')}</p>}
        </>
      )}
    </section>
  )
}
