import { DecisionRange } from './DecisionEvidence'
import type { CompareResponse, Entry } from './types'

const f4 = (n: number) => n.toFixed(4)
const words = (s: string) => s.replace(/_/g, ' ')
const interval = (e: Entry) => e.score_interval.low === e.score_interval.high
  ? 'complete evidence' : `${f4(e.score_interval.low)}–${f4(e.score_interval.high)}`

/** Same-context comparison. Every cell and sentence is a backend field; nothing is computed here. */
export function ComparePanel({ response }: { response: CompareResponse }) {
  const name = (id: string) => response.players.find(p => p.entity_id === id)?.name ?? id
  const row = (label: string, cell: (e: Entry) => React.ReactNode) => (
    <tr><th scope="row">{label}</th>{response.players.map(p => <td key={p.entity_id}>{cell(p)}</td>)}</tr>
  )
  return (
    <section className="ix-cmp" aria-label="Comparison">
      <table>
        <thead><tr><th scope="col"><span className="sr-only">Measure</span></th>{response.players.map(p => <th key={p.entity_id} scope="col">{p.name}</th>)}</tr></thead>
        <tbody>
          {row('Intelligence Score', p => <>{f4(p.score)} <span className="ix-note">{interval(p)}</span></>)}
          {row('Coverage', p => `${Math.round(p.coverage * 100)}%`)}
          {row('Confidence', p => p.confidence?.level ?? 'n/a')}
          {row('Key attributes', p => p.key_strengths.slice(0, 3).map(a => `${words(a.attribute)} ${a.value ?? '—'}`).join(', '))}
          {row('PlayStyles', p => p.player.playstyles.published
            ? [...p.player.playstyles.base, ...p.player.playstyles.plus.map(x => `${x}+`)].join(', ') || 'none' : 'not published')}
        </tbody>
      </table>
      <ul className="ix-cmp-why">
        {response.pairwise.map((p, i) => (
          <li key={i}>
            {p.within_noise_threshold
              ? `${name(p.higher)} and ${name(p.lower)} are effectively tied (gap ${f4(p.score_gap)}). What separates them: ${p.why.join('; ')}`
              : `For this tactical context, ${name(p.higher)} scores higher than ${name(p.lower)} because ${p.why.join('; ')}`}
            {p.decision_evidence && <><br /><DecisionRange evidence={p.decision_evidence} /></>}
          </li>
        ))}
      </ul>
      {response.note && <p className="ix-note">{response.note}</p>}
    </section>
  )
}
