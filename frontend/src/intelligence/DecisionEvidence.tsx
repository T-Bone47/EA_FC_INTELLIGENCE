import type { DecisionEvidence, LeadingPair } from './types'

const labels: Record<DecisionEvidence['status'], string> = {
  NEAR_TIE: 'Near tie',
  EVIDENCE_SENSITIVE: 'Lead sensitive to missing evidence',
  CLEAR_SEPARATION: 'Clear separation within modelled evidence',
}

export function DecisionRange({ evidence }: { evidence: DecisionEvidence }) {
  return <span className="small muted">
    <strong>{labels[evidence.status]}.</strong>{' '}
    Modelled fit margin {evidence.margin_low.toFixed(4)} to {evidence.margin_high.toFixed(4)}
  </span>
}

export function LeaderEvidence({ pair }: { pair: LeadingPair }) {
  return <p className="callout info small">
    <strong>{pair.higher} vs {pair.lower}</strong><br />
    <DecisionRange evidence={pair} />
  </p>
}
