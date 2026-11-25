import { Card } from './Card'
import type { Entry } from './types'

/**
 * Server order, always. A tie run = consecutive entries linked by the backend's own
 * `within_noise_threshold` flag; the UI never sorts, re-scores or decides what counts as a tie.
 */
export function Ladder({ ranked, selected = [], onToggle, onInspect }: {
  ranked: Entry[]; selected?: string[]; onToggle?: (e: Entry) => void; onInspect?: (e: Entry) => void
}) {
  const runs: Entry[][] = []
  ranked.forEach((e, i) => {
    if (ranked[i - 1]?.near_tie_with_next?.within_noise_threshold) runs[runs.length - 1].push(e)
    else runs.push([e])
  })
  const card = (e: Entry) => (
    <Card key={e.entity_id} entry={e} selected={selected.includes(e.entity_id)} onToggle={onToggle && (() => onToggle(e))} onInspect={onInspect && (() => onInspect(e))} />
  )
  return (
    <div className="ix-ladder">
      {runs.map((run, i) => run.length > 1 ? (
        <div key={i} className="ix-tie-run" role="group" aria-label="Effectively tied">
          <p className="ix-tie-label">Effectively tied — scores within noise</p>
          {run.map(card)}
        </div>
      ) : card(run[0]))}
    </div>
  )
}
