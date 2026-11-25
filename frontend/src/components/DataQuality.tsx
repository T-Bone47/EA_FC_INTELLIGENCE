/**
 * §44 Data-quality surface: shows what card data EXISTS and what is NO_DATA.
 * Every unavailable dimension is rendered as its honest status — never as 0,
 * empty, or a guessed value.
 */
import type { CardDataStatus } from '../api/types'
import { UNKNOWN_LABEL } from '../lib/format'

const STATUS_LABEL: Record<string, string> = {
  AVAILABLE: 'Available',
  PARTIAL: 'Partial',
  NO_DATA: 'NO DATA',
  NO_VERIFIED_RULES: 'No verified rules',
}

function AvailabilityPill({ status }: { status: string }) {
  const cls = status === 'AVAILABLE' ? 'ok'
    : status === 'PARTIAL' ? 'warn' : 'bad'
  return (
    <span className={`badge ${cls}`} title={`data_status: ${status}`}>
      {STATUS_LABEL[status] ?? status ?? UNKNOWN_LABEL}
    </span>
  )
}

export function DataQualityPanel({ status }: { status: CardDataStatus | null }) {
  if (!status) return null
  const a = status.availability
  const rows: [string, string | undefined, number | undefined][] = [
    ['Card attributes', a.card_attributes, status.cards_with_attributes ?? status.production_cards],
    ['Market prices', a.card_prices, status.cards_with_price],
    ['Card Roles', a.card_roles, status.card_roles_rows],
    ['Chemistry rules', a.chemistry_rules, status.verified_chemistry_rules],
    ['Evolutions', a.evolutions, status.evolution_rows],
  ]
  return (
    <div className="card tight" data-testid="data-quality">
      <div className="section-title">Card data status — {status.game_version}</div>
      <table className="table small">
        <thead>
          <tr><th>Dimension</th><th>Status</th><th>Rows</th></tr>
        </thead>
        <tbody>
          {rows.map(([label, st, n]) => st != null && n != null && (
            <tr key={label}>
              <td>{label}</td>
              <td><AvailabilityPill status={st} /></td>
              <td>{n}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {status.synthetic_cards_firewalled != null && <div className="tiny faint mt1">
        Synthetic test cards firewalled: {status.synthetic_cards_firewalled} ·
        identity resolved: {status.identity_resolved_cards} ·
        quarantined rows: {status.quarantined_rows} ·
        last card update: {status.last_card_update
          ? new Date(status.last_card_update).toISOString().slice(0, 16).replace('T', ' ')
          : UNKNOWN_LABEL}
      </div>}
      {status.production_cards === 0 && (
        <div className="callout mt1">
          No approved UT card records are available for {status.game_version}.
        </div>
      )}
    </div>
  )
}
