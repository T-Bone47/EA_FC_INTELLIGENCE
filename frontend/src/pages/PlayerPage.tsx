import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, qs } from '../api/client'
import type { PlayerPage as PlayerPageData } from '../api/types'
import { useApi } from '../lib/useApi'
import { useSession } from '../state/session'
import {
  ErrorBox, FacadeRadar, Loading, Ovr, Pos, Stars, Unknown,
} from '../components/common'
import { UNKNOWN_LABEL, age, dateShort, dateTime, prettyAttr } from '../lib/format'

const OUTFIELD_GROUPS: [string, string[]][] = [
  ['Attacking', ['finishing', 'shot_power', 'long_shots', 'volleys', 'penalties', 'positioning']],
  ['Passing & vision', ['vision', 'crossing', 'short_passing', 'long_passing', 'curve', 'free_kick_accuracy']],
  ['Dribbling & agility', ['dribbling_detail', 'ball_control', 'agility', 'balance', 'composure']],
  ['Defending', ['defensive_awareness', 'interceptions', 'standing_tackle', 'sliding_tackle', 'heading_accuracy']],
  ['Physical', ['strength', 'stamina', 'aggression', 'jumping', 'reactions', 'acceleration', 'sprint_speed']],
]
const GK_GROUPS: [string, string[]][] = [
  ['Goalkeeping', ['gk_diving', 'gk_handling', 'gk_kicking', 'gk_positioning', 'gk_reflexes']],
  ['Physical', ['strength', 'stamina', 'aggression', 'jumping', 'reactions', 'acceleration', 'sprint_speed']],
]

function AttrGroup({ title, codes, attrs }: {
  title: string; codes: string[]; attrs: Record<string, number | null>
}) {
  const known = codes.filter((c) => attrs[c] !== null && attrs[c] !== undefined)
  return (
    <div className="card tight">
      <div className="section-title">{title}</div>
      {known.length === 0 ? (
        <div className="small">
          <Unknown title="These attributes are not published in the ingested source for this player" />
          <div className="tiny faint mt1">
            Outfield detail attributes for goalkeepers are facade mirrors in the source
            and are deliberately withheld rather than shown as fake values.
          </div>
        </div>
      ) : (
        <div className="col" style={{ gap: '.4rem' }}>
          {codes.map((c) => (
            <div className="attr" key={c}>
              <span className="lbl">{prettyAttr(c)}</span>
              <span className="val">{attrs[c] ?? <Unknown />}</span>
              <div className="bar" style={{ gridColumn: '1 / -1' }}>
                <span style={{
                  width: `${attrs[c] != null ? Math.max(2, (attrs[c] as number) / 99 * 100) : 100}%`,
                  background: attrs[c] != null ? undefined
                    : 'repeating-linear-gradient(45deg,#2a3444,#2a3444 4px,#1b2331 4px,#1b2331 8px)',
                }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function PlayerPage() {
  const { id } = useParams<{ id: string }>()
  const { gameVersion, user, notify } = useSession()
  const nav = useNavigate()
  const page = useApi<PlayerPageData>(
    `/api/players/${id}${qs({ game_version: gameVersion })}`, [id, gameVersion])
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!user || !id) { setSaved(false); return }
    api.get<{ items: { entity_id: string }[] }>('/api/saved-players')
      .then((d) => setSaved(d.items.some((i) => i.entity_id === id)))
      .catch(() => { /* non-critical */ })
  }, [user, id])

  if (page.loading) return <Loading label="Loading player" />
  if (page.error) return (
    <div>
      <div className="page-head"><h1 className="mb0">Player</h1></div>
      <ErrorBox error={page.error} onRetry={page.reload} />
      {page.error.status === 404 && (
        <div className="callout info mt2 small">
          404 means: this entity does not exist in <strong>{gameVersion}</strong> canonical
          data. It may exist in another version — versions are never mixed. Try switching
          the version above or search again.
        </div>
      )}
    </div>
  )
  if (!page.data) return null

  const d = page.data
  const gp = d.game_player
  const attrs = d.attributes as Record<string, number | null>
  const isGk = gp.position_primary === 'GK'
  const groups = isGk ? GK_GROUPS : OUTFIELD_GROUPS
  const basePs = d.playstyles.filter((p) => p.tier === 'base')
  const plusPs = d.playstyles.filter((p) => p.tier === 'plus')

  async function toggleSave() {
    if (!user) { notify('info', 'Log in to save players.'); nav('/login', { state: { from: `/players/${id}` } }); return }
    try {
      if (saved) {
        await api.del(`/api/saved-players/${id}`)
        setSaved(false)
        notify('ok', 'Removed from saved.')
      } else {
        await api.post('/api/saved-players', {
          entity_type: 'game_player', entity_id: id, game_version: gameVersion })
        setSaved(true)
        notify('ok', `Saved ${gp.display_name}.`)
      }
    } catch (e: any) {
      notify('bad', e.detail || 'Save failed.', e.requestId)
    }
  }

  return (
    <div>
      <div className="page-head">
        <div className="row" style={{ gap: '.8rem' }}>
          <Ovr value={gp.overall_rating} />
          <div>
            <h1 className="mb0">{gp.display_name}</h1>
            <div className="row small muted" style={{ gap: '.5rem' }}>
              <Pos value={gp.position_primary} />
              {(d.secondary_positions ?? []).map((p: string) => (
                <span key={p} className="pos" style={{ opacity: .55 }} title="Secondary position">{p}</span>
              ))}
              <span>{gp.nation ?? <Unknown />}</span>
              <span>·</span>
              <span>{gp.club ?? <Unknown />}</span>
              {gp.league && <><span>·</span><span>{gp.league}</span></>}
            </div>
          </div>
        </div>
        <div className="spacer" />
        <div className="row">
          <button className={`btn ${saved ? 'primary' : 'ghost'} sm`} onClick={toggleSave}>
            {saved ? '★ Saved' : '☆ Save'}
          </button>
          <Link className="btn sm" to={`/compare?ids=${id}`}>Compare…</Link>
          <Link className="btn sm primary"
                to={`/recommend?position=${encodeURIComponent(gp.position_primary ?? '')}`}>
            Find alternatives
          </Link>
        </div>
      </div>

      <ErrorBox error={page.error} />

      <div className="grid g2 mb2">
        <div className="card">
          <div className="section-title">Facade stats {isGk && <span className="badge warn" title="For goalkeepers the source mirrors GK ratings into outfield facades; treat with care">GK facades</span>}</div>
          <div className="radar-wrap">
            <FacadeRadar values={{
              pace: attrs.pace ?? null, shooting: attrs.shooting ?? null,
              passing: attrs.passing ?? null, dribbling: attrs.dribbling ?? null,
              defending: attrs.defending ?? null, physicality: attrs.physicality ?? null,
            }} />
            <div className="legend flex1">
              <div className="kv">
                <dt>Age</dt><dd>{age(gp.date_of_birth) ?? <Unknown />}</dd>
                <dt>Height</dt><dd>{gp.height_cm ? `${gp.height_cm} cm` : <Unknown />}</dd>
                <dt>Weight</dt><dd>{gp.weight_kg ? `${gp.weight_kg} kg` : <Unknown />}</dd>
                <dt>Preferred foot</dt><dd>{gp.preferred_foot ?? <Unknown />}</dd>
                <dt>Weak foot</dt><dd><Stars n={gp.weak_foot_stars} /></dd>
                <dt>Skill moves</dt><dd><Stars n={gp.skill_moves_stars} /></dd>
                <dt>Position type</dt><dd>{gp.position_type ?? <Unknown />}</dd>
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="section-title">PlayStyles</div>
          {!d.playstyle_data_published ? (
            <div className="callout warn small">
              <div className="t">PlayStyle data: {UNKNOWN_LABEL}</div>
              EA has not published PlayStyle data for this player in the ingested
              source. This is <strong>not</strong> “no PlayStyles” — it is UNKNOWN.
            </div>
          ) : basePs.length === 0 && plusPs.length === 0 ? (
            <div className="small muted">No PlayStyle rows in the ingested source.</div>
          ) : (
            <>
              <div className="chips">
                {basePs.map((p) => <span key={p.name} className="chip on" style={{ cursor: 'default' }}>{p.name}</span>)}
                {plusPs.map((p) => <span key={p.name} className="chip on" style={{ cursor: 'default', borderColor: 'var(--accent)', background: 'rgba(0,224,138,.25)' }}>{p.name}+</span>)}
              </div>
              <div className="tiny faint mt1">
                Base: {basePs.length} · Plus: {plusPs.length} (FC26 cap: 1 plus per player)
              </div>
            </>
          )}

          <hr className="divider" />
          <div className="section-title">UT cards</div>
          {d.cards.length === 0 ? (
            <div className="callout info small mb0">
              No canonical UT cards are ingested for {gameVersion}. Card-level pages
              activate automatically once real card data is legitimately acquired —
              synthetic test cards are firewalled and never shown here.
            </div>
          ) : (
            <div className="small">{d.cards.length} card(s)</div>
          )}
        </div>
      </div>

      <div className="section-title">Detailed attributes</div>
      <div className="grid g3 mb2">
        {groups.map(([title, codes]) => (
          <AttrGroup key={title} title={title} codes={codes} attrs={attrs} />
        ))}
      </div>

      <div className="grid g2">
        <div className="card">
          <div className="section-title">Provenance & freshness</div>
          <dl className="kv small">
            <dt>Source</dt><dd>{d.provenance.name ?? <Unknown />}{' '}
              <span className="badge">tier {d.provenance.authority_tier ?? '?'}</span></dd>
            <dt>License</dt><dd>{d.provenance.license ?? <Unknown />}</dd>
            <dt>Usage status</dt><dd><span className="badge info">{d.provenance.usage_status ?? UNKNOWN_LABEL}</span></dd>
            <dt>Last observed</dt><dd>{dateTime(d.freshness.last_observed)}</dd>
            <dt>Identity</dt>
            <dd>
              {gp.real_player_name
                ? <>Linked real identity: <strong>{gp.real_player_name}</strong>{' '}
                    <span className="badge ok">{gp.real_identity_status}</span></>
                : <>Real identity: <Unknown title="Identity resolution did not link a RealPlayer row" /></>}
            </dd>
            <dt>Data status</dt><dd><span className="badge ok">{gp.data_status}</span></dd>
          </dl>
          {d.provenance.url && (
            <a className="tiny" href={d.provenance.url} target="_blank" rel="noreferrer noopener">
              Source dataset ↗
            </a>
          )}
        </div>
        <div className="card">
          <div className="section-title">Version isolation</div>
          <p className="small muted">
            This page shows the <strong>{d.game_version}</strong> representation of the
            player only. Other game versions:
          </p>
          {(d.other_game_versions ?? []).length === 0 ? (
            <div className="callout small mb0">
              No representation in any other ingested version.
              {gameVersion === 'FC26' && ' FC27 has NO_DATA — when real FC27 records are ingested, they appear here separately, never merged into this row.'}
            </div>
          ) : (
            <div className="row">
              {d.other_game_versions.map((v) => (
                <Link key={v.game_version} className="btn ghost sm"
                      to={`/players/${v.id}`}>{v.game_version}</Link>
              ))}
            </div>
          )}
          <hr className="divider" />
          <div className="row tiny faint">
            <span>Record id:</span><code>{String(gp.id).slice(0, 13)}…</code>
            <span>· source player id:</span><code>{gp.source_player_id ?? UNKNOWN_LABEL}</code>
            <span>· last data update {dateShort(gp.updated_at)}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
