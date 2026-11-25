import { Link } from 'react-router-dom'
import type { PlayerListItem } from '../api/types'
import { Ovr, Pos } from './common'
import { PlayerIdentity } from './PlayerIdentity'
import { StadiumIcon } from './StadiumIcons'
import { qs } from '../api/client'

interface FootballCardProps {
  player: PlayerListItem
  gameVersion: string
  isResearch?: boolean
  optedIn?: boolean
  isCompared?: boolean
  isSaved?: boolean
  onToggleCompare?: (id: string) => void
  onToggleSave?: (player: PlayerListItem) => void
}

export function FootballCard({
  player: p,
  gameVersion,
  isResearch,
  optedIn,
  isCompared,
  isSaved,
  onToggleCompare,
  onToggleSave,
}: FootballCardProps) {
  const facets = [
    { key: 'PAC', val: p.pace },
    { key: 'SHO', val: p.shooting },
    { key: 'PAS', val: p.passing },
    { key: 'DRI', val: p.dribbling },
    { key: 'DEF', val: p.defending },
    { key: 'PHY', val: p.physicality },
  ]

  const ovr = p.overall_rating ?? 0
  const ovrTier = ovr >= 88 ? 'tier-elite' : ovr >= 82 ? 'tier-high' : ovr >= 75 ? 'tier-mid' : 'tier-entry'
  const cardTierClass = isResearch ? 'card-tier-special' : ovr >= 85 ? 'card-tier-gold' : ovr < 75 ? 'card-tier-silver' : ''
  const detailUrl = `/players/${p.id}${qs({ game_version: gameVersion, include_research_data: optedIn || undefined })}`

  return (
    <article className={`card discovery-tile football-card ${cardTierClass} ${isCompared ? 'is-selected' : ''}`} key={p.id}>
      <div className="fc-card-header">
        <div className="fc-badge-group">
          <span className={`fc-ovr-badge ${ovrTier}`}><Ovr value={p.overall_rating} /></span>
          <Pos value={p.position_primary} />
          {p.secondary_positions?.length > 0 && (
            <span className="tiny faint" title="Secondary positions">{p.secondary_positions.join('/')}</span>
          )}
        </div>
        <span className={`badge ${isResearch ? 'warning' : 'info'} fc-edition-tag`}>
          {isResearch ? 'FC27 Research' : gameVersion}
        </span>
      </div>

      <div className="fc-identity-hero">
        <PlayerIdentity name={p.display_name} />
        <h3 className="fc-player-name">
          <Link to={detailUrl}>{p.display_name}</Link>
        </h3>
        <p className="fc-club-nation muted small mb0">
          {[p.club, p.nation].filter(Boolean).join(' · ') || 'Club & Nation unavailable'}
        </p>
      </div>

      <div className="fc-facet-grid" aria-label="Player attributes">
        {facets.map(f => (
          <div className="fc-facet-item" key={f.key}>
            <span className="fc-facet-lbl">{f.key}</span>
            <span className={`fc-facet-val ${f.val && f.val >= 88 ? 'elite' : f.val && f.val >= 82 ? 'high' : ''}`}>
              {f.val ?? '—'}
            </span>
          </div>
        ))}
      </div>

      <div className="fc-action-tray">
        {!optedIn && onToggleCompare && (
          <label className="checkbox">
            <input
              type="checkbox"
              checked={isCompared}
              aria-label={`Select ${p.display_name} for comparison`}
              onChange={() => onToggleCompare(p.id)}
            />
            <span>Compare</span>
          </label>
        )}
        <div className="row gap05" style={{ marginLeft: 'auto' }}>
          <Link
            to={`/intelligence?position=${p.position_primary}&game_version=${gameVersion}`}
            className="fc-inspect-link"
            title="Evaluate tactical suitability in Intelligence Studio"
          >
            <StadiumIcon name="zap" size={13} />
            <span>Tactics</span>
          </Link>
          <Link
            to={`/cards/squad-lab?item=${encodeURIComponent(p.display_name)}`}
            className="fc-inspect-link"
            title="Inspect or test player in Squad Lab"
          >
            <StadiumIcon name="squad" size={13} />
            <span>Squad</span>
          </Link>
          {!optedIn && onToggleSave && (
            <button
              className={`btn ghost sm ${isSaved ? 'accent' : ''}`}
              type="button"
              aria-pressed={!!isSaved}
              onClick={() => onToggleSave(p)}
              title={isSaved ? 'Remove from saved' : 'Save player'}
            >
              <StadiumIcon name="star" size={13} />
              <span>{isSaved ? 'Saved' : 'Save'}</span>
            </button>
          )}
        </div>
      </div>
    </article>
  )
}
