import { DecisionRange } from './DecisionEvidence'
import { Ovr, Pos } from '../components/common'
import { PlayerIdentity } from '../components/PlayerIdentity'
import type { Entry } from './types'

const f4 = (n: number) => n.toFixed(4)
const words = (s: string) => s.replace(/_/g, ' ')

/** One recommendation. Every number and every sentence comes from the backend response. */
export function Card({ entry, selected, onToggle, onInspect }: { entry: Entry; selected?: boolean; onToggle?: () => void; onInspect?: () => void }) {
  const { player, score_interval: iv, near_tie_with_next: tie, tactical_fit: fit, explanation: ex, evidence: ev } = entry
  const styles = player.playstyles
  return (
    <article className="ix-card" data-testid="ix-card">
      <header className="ix-head">
        <span className="ix-rank">{entry.rank}</span>
        <PlayerIdentity name={entry.name} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 style={{ margin: 0 }}>{entry.name}</h3>
        </div>
        <Pos value={player.position_primary} />
        {onToggle && (
          <label className="ix-compare">
            <input type="checkbox" checked={!!selected} onChange={onToggle} aria-label={`Compare ${entry.name}`} /> Compare
          </label>
        )}
      </header>

      <div className="ix-scores">
        <div>
          <span className="ix-label">Intelligence Score</span>{' '}
          <strong className="ix-score" aria-label={`Intelligence Score ${f4(entry.score)}`}>{f4(entry.score)}</strong>{' '}
          <span className="ix-interval">
            {iv.low === iv.high ? 'Complete evidence — no interval' : `${f4(iv.low)}–${f4(iv.high)}`}
          </span>
        </div>
        <div>
          <span className="ix-label">EA OVR</span> <Ovr value={player.overall_rating} />{' '}
          <span className="ix-note">descriptive only, not scored</span>
        </div>
        <div className="ix-note">
          coverage {Math.round(entry.coverage * 100)}% · confidence{' '}
          <span className="badge info" title="reporting only — never part of the score">{entry.confidence?.level ?? 'n/a'}</span>
        </div>
      </div>

      <ul className="ix-attrs">
        {entry.key_strengths.slice(0, 3).map((a, i) => (
          <li key={i}>{words(a.attribute)} <b>{a.value ?? '—'}</b></li>
        ))}
      </ul>

      <div className="ix-styles">
        {styles.published
          ? [...styles.base, ...styles.plus.map(p => `${p}+`)].map((n, i) => <span className="badge info" key={i}>{n}</span>)
          : <span className="ix-note">PlayStyles not published</span>}
      </div>

      <div className="ix-fit">
        <span className="ix-label">Tactical fit</span> {fit.tactical_profile} at {fit.position}
        <span className="ix-note"> · {fit.demand_stages.map(s => words(s.stage)).join(' → ')}</span>
        <ul>
          {fit.top_demanded.map((r, i) => (
            <li key={i}>{words(r.attribute)} <b>{r.value ?? '—'}</b> <span className="ix-note">weight {(r.weight * 100).toFixed(1)}%</span></li>
          ))}
        </ul>
      </div>

      {ex.reasons[0] && <p className="ix-why">{ex.reasons[0]}</p>}
      {onInspect && <button className="btn ghost sm" type="button" onClick={onInspect}>Inspect {entry.name}</button>}
      <details>
        <summary>Why this player · trade-offs · evidence</summary>
        <h4>Why this player?</h4>
        <ul>{ex.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
        <h4>Trade-offs</h4>
        <ul>{ex.trade_offs.map((r, i) => <li key={i}>{r}</li>)}</ul>
        <h4>Evidence</h4>
        <p>{ev.published_attributes} of {ev.demanded_attributes} demanded attributes published
          {ev.missing_attributes.length > 0 && ` · missing: ${ev.missing_attributes.map(words).join(', ')}`}</p>
        <ul>{ex.unknowns.map((r, i) => <li key={i}>{r}</li>)}</ul>
      </details>

      {tie && (
        <div className="ix-tie" data-testid="near-tie-note">
          {tie.decision_evidence ? <DecisionRange evidence={tie.decision_evidence} /> : tie.within_noise_threshold
            ? `Effectively tied with the next player (gap ${f4(tie.score_gap)}) — not a meaningful order.`
            : 'Score intervals overlap with the next player — the order is uncertain.'}
          {tie.why_ahead.length > 0 && (
            <> What separates them:<ul>{tie.why_ahead.map((w, i) => <li key={i}>{w}</li>)}</ul></>
          )}
        </div>
      )}
    </article>
  )
}
