/**
 * §43 Premium CARD page. Everything shown is card-level data: attributes,
 * PlayStyles, prices and identity belong to the CARD. Anything the ingested
 * source does not publish is rendered as UNKNOWN — never back-filled from the
 * base player, never zero, never estimated.
 */
import { Link, useParams } from 'react-router-dom'
import { qs } from '../api/client'
import type { CardPageData, PriceHistoryResponse } from '../api/types'
import { useApi } from '../lib/useApi'
import { useSession } from '../state/session'
import {
  AttrRows, ErrorBox, Facades, Loading, Ovr, Pos, Unknown,
} from '../components/common'
import { UNKNOWN_LABEL, dateTime } from '../lib/format'

const FACADES = ['pace', 'shooting', 'passing', 'dribbling', 'defending', 'physicality']
const DETAILS = [
  'acceleration', 'sprint_speed', 'finishing', 'shot_power', 'long_shots',
  'volleys', 'penalties', 'positioning', 'vision', 'crossing', 'free_kick_accuracy',
  'short_passing', 'long_passing', 'curve', 'dribbling_detail', 'ball_control',
  'agility', 'balance', 'composure', 'reactions', 'defensive_awareness',
  'interceptions', 'standing_tackle', 'sliding_tackle', 'heading_accuracy',
  'jumping', 'stamina', 'strength', 'aggression',
]
const GK_DETAILS = ['gk_diving', 'gk_handling', 'gk_kicking', 'gk_positioning', 'gk_reflexes']

function IdentityPill({ status }: { status: string | null }) {
  const cls = status === 'RESOLVED' ? 'ok'
    : status === 'REVIEW_REQUIRED' ? 'warn' : 'unknown'
  return <span className={`badge ${cls}`}>{status ?? UNKNOWN_LABEL}</span>
}

export default function CardPage() {
  const { id } = useParams<{ id: string }>()
  const { gameVersion } = useSession()
  const page = useApi<CardPageData>(
    `/api/cards/${id}${qs({ game_version: gameVersion })}`, [id, gameVersion])
  const prices = useApi<PriceHistoryResponse>(
    page.data ? `/api/cards/${id}/prices${qs({ game_version: gameVersion })}` : null,
    [id, gameVersion, !!page.data])

  if (page.loading) return <Loading label="Loading card" />
  if (page.error || !page.data) return (
    <div>
      <div className="page-head"><h1 className="mb0">UT Card</h1></div>
      <ErrorBox error={page.error} onRetry={page.reload} />
      {page.error?.status === 404 && (
        <div className="callout mt1">
          This card is not part of {gameVersion}'s canonical data (or is
          synthetic test data, which production endpoints never expose).
          Card data status: see the <Link to="/cards">Cards page</Link>.
        </div>
      )}
    </div>
  )

  const { card, attribute_overrides: attrs, playstyles, versions, game_player: gp } = page.data
  const facadeVals: Record<string, number | null> = {}
  for (const f of FACADES) facadeVals[f] = attrs[f] ?? null
  const details = card.position === 'GK' ? GK_DETAILS : DETAILS
  const knownDetails = details.filter((d) => attrs[d] != null)
  const psBase = playstyles.filter((p) => p.tier === 'base').map((p) => p.playstyle_name)
  const psPlus = playstyles.filter((p) => p.tier === 'plus').map((p) => p.playstyle_name)
  const history = prices.data

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="mb0">{card.card_name}</h1>
          <div className="faint small">
            {card.card_type ?? 'Card type: ' + UNKNOWN_LABEL}
            {' · '}rarity {card.rarity_code ?? card.rarity_raw ?? UNKNOWN_LABEL}
            {card.release_group ? ` · ${card.release_group}` : ''}
          </div>
        </div>
        <div className="row" style={{ gap: '.8rem', alignItems: 'center' }}>
          <Ovr value={card.overall_rating} />
          <Pos value={card.position} />
        </div>
      </div>

      <div className="grid g2" style={{ alignItems: 'start' }}>
        <div className="col">
          <div className="card tight">
            <div className="section-title">Card attributes (card-level only)</div>
            {Object.keys(attrs).length === 0 ? (
              <Unknown title="This card's attributes are not published in the ingested source — base-player values are NEVER substituted" />
            ) : (
              <>
                <Facades f={facadeVals} />
                {knownDetails.length > 0 && (
                  <div className="mt1">
                    <AttrRows attrs={attrs} codes={knownDetails} />
                  </div>
                )}
                <div className="tiny faint mt1">
                  Attributes the card does not publish are UNKNOWN — the engine
                  never silently falls back to the base player (§5).
                </div>
              </>
            )}
          </div>

          <div className="card tight">
            <div className="section-title">PlayStyles</div>
            {!card.playstyle_data_published ? (
              <Unknown title="This card's PlayStyle list is not published by the source — base-player PlayStyles are never inherited" />
            ) : (
              <div className="col" style={{ gap: '.5rem' }}>
                <div className="row wrap" style={{ gap: '.4rem' }}>
                  <span className="small faint" style={{ minWidth: 70 }}>Base:</span>
                  {psBase.length ? psBase.map((p) => (
                    <span key={p} className="chip on">{p}</span>))
                    : <span className="tiny faint">none published</span>}
                </div>
                <div className="row wrap" style={{ gap: '.4rem' }}>
                  <span className="small faint" style={{ minWidth: 70 }}>PlayStyle+:</span>
                  {psPlus.length ? psPlus.map((p) => (
                    <span key={p} className="badge accent">{p}+</span>))
                    : <span className="tiny faint">none published</span>}
                </div>
                <div className="tiny faint">
                  Base and PlayStyle+ are distinct tiers; contextual value is
                  judged by the engine per request — a mismatched PlayStyle+
                  never auto-beats a well-matched base PlayStyle.
                </div>
              </div>
            )}
          </div>

          <div className="card tight">
            <div className="section-title">Market price & history</div>
            {!card.price && (!history || history.observations === 0) ? (
              <Unknown title="No verified price observation exists for this card — price is UNKNOWN (never 0, never estimated); value and budget checks stay UNAVAILABLE" />
            ) : (
              <>
                {card.price?.price_coins != null && (
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <strong>{card.price.price_coins.toLocaleString()} coins</strong>
                    <span className="tiny faint">
                      platform {card.price.platform ?? UNKNOWN_LABEL} ·
                      observed {card.price.observed_at ? dateTime(card.price.observed_at) : UNKNOWN_LABEL} ·
                      confidence {card.price.confidence ?? UNKNOWN_LABEL}
                    </span>
                  </div>
                )}
                {history && history.observations > 0 && (
                  <table className="data small mt1">
                    <thead><tr><th>Observed</th><th>Price</th><th>Platform</th><th>Source</th></tr></thead>
                    <tbody>
                      {history.history.slice(0, 12).map((h, i) => (
                        <tr key={i}>
                          <td>{h.observed_at ? dateTime(h.observed_at) : UNKNOWN_LABEL}</td>
                          <td>{h.price_coins != null ? h.price_coins.toLocaleString() : UNKNOWN_LABEL}</td>
                          <td>{h.platform ?? UNKNOWN_LABEL}</td>
                          <td className="tiny faint">{h.source_id ?? UNKNOWN_LABEL}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                {history?.status === 'NO_PRICE_HISTORY' && (
                  <div className="tiny faint mt1">{history.note}</div>
                )}
              </>
            )}
          </div>
        </div>

        <div className="col">
          <div className="card tight">
            <div className="section-title">Card identity (§4)</div>
            <div className="kv small">
              <span className="faint">Identity</span>
              <span><IdentityPill status={card.identity_status} /></span>
              <span className="faint">Card id</span>
              <span className="mono tiny">{card.id}</span>
              <span className="faint">Canonical id</span>
              <span className="mono tiny">{card.canonical_card_id ?? UNKNOWN_LABEL}</span>
              <span className="faint">Source</span>
              <span className="tiny">{card.source_id} · row {card.source_card_id}</span>
              <span className="faint">Game version</span>
              <span>{gameVersion}</span>
            </div>
            <div className="tiny faint mt1">
              Identity is source+version+row based with a deterministic
              canonical id — never “name + OVR”. FC26 and FC27 cards can never
              collide.
            </div>
          </div>

          <div className="card tight">
            <div className="section-title">Version history</div>
            {versions.length === 0 ? (
              <Unknown title="No persisted card versions — upgrade history is never inferred" />
            ) : (
              <table className="data small">
                <thead><tr><th>#</th><th>OVR</th><th>Valid from</th><th>Current</th></tr></thead>
                <tbody>
                  {versions.map((v) => (
                    <tr key={v.version_number}>
                      <td>{v.version_number}</td>
                      <td><Ovr value={v.overall_rating} /></td>
                      <td className="tiny">{v.valid_from ? dateTime(v.valid_from) : UNKNOWN_LABEL}</td>
                      <td>{v.is_current ? <span className="badge ok">current</span> : ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="card tight">
            <div className="section-title">Base player link</div>
            {gp ? (
              <div className="kv small">
                <span className="faint">Player</span>
                <span><Link to={`/players/${gp.id}`}>{gp.display_name}</Link></span>
                <span className="faint">Position</span>
                <span><Pos value={gp.position_primary} /></span>
                <span className="faint">Base OVR</span>
                <span><Ovr value={gp.overall_rating} /></span>
              </div>
            ) : (
              <Unknown title="No verified link to a base player — link facts (nation/club/league) stay UNKNOWN for this card" />
            )}
            <div className="tiny faint mt1">
              The base player provides identity link facts only. Ratings,
              PlayStyles and price above are the CARD's own data.
            </div>
          </div>

          <div className="callout tiny">
            Chemistry: no verified {gameVersion} chemistry rules are ingested —
            any chemistry score would be invented, so none is shown. Squad
            structural links (club/league/nation) are available in comparison
            and squad views and are labelled as structural, not chemistry.
          </div>
        </div>
      </div>
    </div>
  )
}
