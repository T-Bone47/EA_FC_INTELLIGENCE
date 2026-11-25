import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, qs } from '../api/client'
import type { CompareResponse, PlayerListItem, RecommendationRequest, ReferenceData } from '../api/types'
import { useApi, useAction } from '../lib/useApi'
import ResearchCards from './ResearchCards'
import { PlayerIdentity } from '../components/PlayerIdentity'
import { ResearchControl, useRelease } from '../components/Availability'
import { useSession } from '../state/session'
import { useCopilot, useCopilotRouteContext } from '../state/copilot'
import { StadiumIcon } from '../components/StadiumIcons'
import { Empty, ErrorBox, Loading, Ovr, Pos } from '../components/common'
import { EpistemicChip, PageHeader } from '../components/ui/StadiumPrimitives'
import { UNKNOWN_LABEL, isUnknown, prettyAttr, prettyEnum } from '../lib/format'
import { TacticalDeltaMatrix, TacticalRadar } from '../components/Visualizations'

interface Picked { id: string; name: string; position: string; overall: number | null }

function PlayerPicker({ onPick, exclude }: { onPick: (p: Picked) => void; exclude: string[] }) {
  const { gameVersion } = useSession()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<PlayerListItem[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setItems([])
    setLoading(false)
    if (q.trim().length < 2) return
    let active = true
    const t = window.setTimeout(async () => {
      setLoading(true)
      try {
        const d = await api.get<{ items: PlayerListItem[] }>(
          `/api/players${qs({ game_version: gameVersion, q: q.trim(), page_size: 6 })}`)
        if (active) setItems(d.items)
      } catch { if (active) setItems([]) } finally { if (active) setLoading(false) }
    }, 300)
    return () => { active = false; window.clearTimeout(t) }
  }, [q, gameVersion])

  const visibleItems = items.filter(i => !exclude.includes(i.id))
  return (
    <div style={{ position: 'relative', minWidth: 'min(100%, 240px)' }} className="flex1">
      <input className="input" placeholder="Search a player to add…" value={q}
             onChange={(e) => { setQ(e.target.value); setOpen(true) }}
             onFocus={() => setOpen(true)} aria-label="Search player to compare" />
      {open && q.trim().length >= 2 && (
        <div className="card" style={{ position: 'absolute', top: '110%', left: 0, right: 0,
                                        zIndex: 20, padding: 0, boxShadow: 'var(--shadow)' }}>
          {loading ? <Loading label="Searching" /> : visibleItems.length === 0 ? (
            <div className="small muted" style={{ padding: '.7rem' }}>No matches in {gameVersion}.</div>
          ) : visibleItems.map((p) => (
            <button key={p.id} className="btn ghost wide" style={{ justifyContent: 'flex-start', borderRadius: 0 }}
                    onClick={() => {
                      onPick({ id: p.id, name: p.display_name,
                               position: p.position_primary, overall: p.overall_rating })
                      setQ(''); setItems([]); setOpen(false)
                    }}>
              <Ovr value={p.overall_rating} /> <Pos value={p.position_primary} />
              <span className="flex1 truncate" style={{ textAlign: 'left' }}>{p.display_name}</span>
              <span className="tiny faint truncate">{p.club ?? ''}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Compare() {
  const { gameVersion } = useSession()
  const [params] = useSearchParams()
  const cardScope = params.get('scope') === 'cards'
  const cards = useRelease('ut_card')
  const players = useRelease('game_player')
  return <div className="stack">
    <nav className="stadium-tabs" aria-label="Comparison scope">
      <Link to="/compare" className={!cardScope ? 'active' : undefined} aria-current={!cardScope ? 'page' : undefined}>Players</Link>
      <Link to="/compare?scope=cards" className={cardScope ? 'active' : undefined} aria-current={cardScope ? 'page' : undefined}>Card versions</Link>
    </nav>
    {cardScope ? <>
      <PageHeader
        title="Compare card versions"
        description="Evaluate FC27 card trait changes, OVR upgrades, and playstyles side by side."
        statusPill={<EpistemicChip kind={cards.active ? 'hypothetical' : 'neutral'} label={cards.status} />}
      />
      {gameVersion === 'FC27' ? <>
        <ResearchControl scope="ut_card" label="Use local FC27 card research" />
        {cards.active && <ResearchCards comparison />}
      </> : <p className="card">Switch to FC27 in the header for card-version diffs, or <Link to="/cards">open the public card catalogue</Link>.</p>}
    </> : gameVersion === 'FC27' ? <section className="card stack">
      <PageHeader
        title="Compare FC27 players"
        description={`${players.status}. Compare FC27 research candidates within the same formation, position, and tactical profile in Intelligence Studio, or switch to Card versions above.`}
        statusPill={<EpistemicChip kind="frozen" label="V3.2.1 Pairwise Engine" />}
        actions={
          <>
            <Link className="btn primary sm" to="/intelligence">Open Intelligence Studio</Link>
            <Link className="btn ghost sm" to="/compare?scope=cards">Compare FC27 Cards</Link>
          </>
        }
      />
    </section> : <ComparePlayers key={gameVersion} />}
  </div>
}

function ComparePlayers() {
  const { gameVersion, notify } = useSession()
  const { openCopilot } = useCopilot()
  const [params, setParams] = useSearchParams()
  const ref = useApi<ReferenceData>(`/api/meta/reference${qs({ game_version: gameVersion })}`, [gameVersion])
  const [picked, setPicked] = useState<Picked[]>([])
  const [useCtx, setUseCtx] = useState(false)
  const [position, setPosition] = useState('')
  const [tactical, setTactical] = useState('BALANCED')
  const [formation, setFormation] = useState('')

  // hydrate from ?ids= (first load only per version)
  const [initialIds] = useState(() => params.get('ids')?.split(',').filter(Boolean).slice(0, 4) ?? [])
  useEffect(() => {
    let active = true
    const list = initialIds
    if (!list.length) return
    Promise.all(list.map((id) =>
      api.get<{ game_player: any }>(`/api/players/${id}${qs({ game_version: gameVersion })}`)
        .then((d) => ({ id, name: d.game_player.display_name as string,
                        position: d.game_player.position_primary as string,
                        overall: d.game_player.overall_rating as number | null }))
        .catch(() => null))).then((rows) => {
      if (!active) return
      const ok = rows.filter((r): r is Picked => !!r)
      if (ok.length < rows.length) notify('info', 'Some ids are not in this game version and were dropped — versions are never mixed.')
      setPicked(ok)
    })
    return () => { active = false }
  }, [initialIds, gameVersion, notify])

  useEffect(() => {
    setParams(picked.length ? { ids: picked.map((p) => p.id).join(',') } : {}, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [picked])

  const contextKey = JSON.stringify([gameVersion, picked.map(p => p.id), useCtx, position, tactical, formation])
  const act = useAction(async () => {
    const body: { game_version: string; entity_ids: string[]; user_context?: RecommendationRequest } = {
      game_version: gameVersion,
      entity_ids: picked.map((p) => p.id),
    }
    if (useCtx) {
      body.user_context = {
        game_version: gameVersion,
        position: position || null,
        formation: formation || null,
        tactical_profile: tactical,
        limit: 1,
      }
    }
    return { contextKey, comparison: await api.post<CompareResponse>('/api/compare', body) }
  })

  const res = act.result?.contextKey === contextKey ? act.result.comparison : null
  const detailCodes = res?.columns?.[0]
    ? Object.keys(res.columns[0].details) : []

  useCopilotRouteContext({
    route_name: 'PLAYER_COMPARE',
    game_version: gameVersion === 'FC26' ? 'FC26' : 'FC27',
    selected_card_ids: picked.map(p => p.id),
    selected_player_names: picked.map(p => p.name),
    active_formation: formation || null,
    active_tactical_profile: tactical || null,
  })

  return (
    <div className="stack">
      <PageHeader
        title="Compare players"
        description={`Side-by-side verified facts for ${gameVersion}. Enable "rank for my context" to run the deterministic engine verdict for your formation and style.`}
        statusPill={<EpistemicChip kind="frozen" label={`${gameVersion} Comparison`} />}
        actions={
          <button
            type="button"
            className="btn ghost sm"
            onClick={() => openCopilot({
              prompt: picked.length >= 2
                ? `Compare ${picked.map(p => p.name).join(' vs ')} for my Gamer DNA and ${tactical.toLowerCase().replace(/_/g, ' ')} system.`
                : 'How should I compare two midfielders or strikers for my Gamer DNA?',
            })}
          >
            <StadiumIcon name="coach" size={14} />
            <span>Ask Co-Pilot</span>
          </button>
        }
      />

      <div className="card mb2">
        <div className="row">
          <PlayerPicker exclude={picked.map((p) => p.id)}
                        onPick={(p) => picked.length >= 4
                          ? notify('info', 'Maximum 4 players per comparison.')
                          : setPicked([...picked, p])} />
          <button className="btn primary" disabled={picked.length < 2 || act.pending}
                  onClick={() => act.run()}>
            {act.pending ? 'Comparing…' : `Compare ${picked.length || ''}`}
          </button>
        </div>
        <div className="comparison-deck mt2">
          {picked.map(p => <section key={p.id} className="card discovery-tile tight">
            <div className="row"><Ovr value={p.overall} /><Pos value={p.position} /></div>
            <PlayerIdentity name={p.name} /><h3><Link to={`/players/${p.id}`}>{p.name}</Link></h3>
            <button className="btn ghost sm" type="button" aria-label={`Remove ${p.name}`}
              onClick={() => setPicked(picked.filter(x => x.id !== p.id))}>Remove</button>
          </section>)}
          {!picked.length && <span className="muted small">Pick 2–4 players.</span>}
        </div>
        <hr className="divider" />
        <label className="checkbox">
          <input type="checkbox" checked={useCtx} onChange={(e) => setUseCtx(e.target.checked)} />
          Rank for my context (adds engine verdict)
        </label>
        {useCtx && (
          <div className="row mt1">
            <select className="select" style={{ maxWidth: 140 }} value={position}
                    onChange={(e) => setPosition(e.target.value)} aria-label="Target position">
              <option value="">Position: any</option>
              {(ref.data?.positions ?? []).map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <select className="select" style={{ maxWidth: 190 }} value={tactical}
                    onChange={(e) => setTactical(e.target.value)} aria-label="Tactical profile">
              {(ref.data?.tactical_profiles ?? ['BALANCED']).map((t) => (
                <option key={t} value={t}>{prettyEnum(t)}</option>))}
            </select>
            <select className="select" style={{ maxWidth: 150 }} value={formation}
                    onChange={(e) => setFormation(e.target.value)} aria-label="Formation">
              <option value="">Formation: —</option>
              {Object.keys(ref.data?.formations ?? {}).map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
        )}
        <ErrorBox error={act.error} />
      </div>

      {act.pending && <div className="card"><Loading label="Comparing" /></div>}

      {!act.pending && !res && (
        <div className="card">
          <Empty title="Nothing compared yet"
                 hint="Add at least two players. Prices and chemistry-related fields show UNKNOWN unless verified — never zeros." />
        </div>
      )}

      {res && (
        <div className="stack">
          {res.columns.length >= 2 && (
            <div className="row" style={{ alignItems: 'stretch', gap: '1rem', flexWrap: 'wrap' }}>
              <div className="flex1" style={{ minWidth: 280 }}>
                <TacticalRadar
                  title="Tactical profile comparison"
                  nameA={res.columns[0].name}
                  facadesA={res.columns[0].facades}
                  nameB={res.columns[1].name}
                  facadesB={res.columns[1].facades}
                />
              </div>
              {res.columns.length === 2 && (
                <div className="flex1" style={{ minWidth: 280 }}>
                  <TacticalDeltaMatrix
                    basePlayer={{
                      name: res.columns[0].name,
                      facades: res.columns[0].facades,
                      overall_rating: res.columns[0].overall_rating,
                    }}
                    comparePlayer={{
                      name: res.columns[1].name,
                      facades: res.columns[1].facades,
                      overall_rating: res.columns[1].overall_rating,
                    }}
                  />
                </div>
              )}
            </div>
          )}

          {res.verdict.user_context && res.verdict.ranked_for_user && (
            <div className="card" style={{ borderColor: 'var(--accent-dim)' }}>
              <div className="section-title">Engine verdict for YOUR context</div>
              <div className="row mb1">
                {res.verdict.ranked_for_user.map((r, i) => (
                  <span key={r.entity_id} className={`badge ${i === 0 ? 'accent' : ''}`}>
                    {i + 1}. {r.name} · {r.weighted_score.toFixed(3)}
                  </span>
                ))}
              </div>
              {res.verdict.why && (
                <ul className="reasons good small mb0">
                  {res.verdict.why.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              )}
              {res.verdict.per_component && (
                <div className="mt2" style={{ overflowX: 'auto' }}>
                  <table className="data">
                    <thead>
                      <tr><th>Component</th>
                        {res.columns.map((c) => <th key={c.entity_id}>{c.name}</th>)}</tr>
                    </thead>
                    <tbody>
                      {Object.entries(res.verdict.per_component).map(([comp, fits]) => (
                        <tr key={comp}>
                          <td className="small">{prettyEnum(comp)}</td>
                          {fits.map((f, i) => (
                            <td key={i} className="small">
                              {f == null || f.status !== 'KNOWN'
                                ? <span className="unknown-val">{f?.status?.replace(/_/g, ' ') ?? UNKNOWN_LABEL}</span>
                                : <span className="mono">{f.value?.toFixed(2)}</span>}
                            </td>))}
                        </tr>))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
            <table className="data">
              <thead>
                <tr>
                  <th>Attribute</th>
                  {res.columns.map((c) => (
                    <th key={c.entity_id}>
                      <Link to={`/players/${c.entity_id}`}>{c.name}</Link>
                    </th>))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="faint small">Overall</td>
                  {res.columns.map((c) => <td key={c.entity_id}><Ovr value={c.overall_rating} /></td>)}
                </tr>
                <tr>
                  <td className="faint small">Position</td>
                  {res.columns.map((c) => (
                    <td key={c.entity_id}>
                      <Pos value={c.position} />{' '}
                      <span className="tiny faint">{c.secondary_positions?.join('/') || ''}</span>
                    </td>))}
                </tr>
                {(['nation', 'club', 'league'] as const).map((k) => (
                  <tr key={k}>
                    <td className="faint small">{prettyEnum(k)}</td>
                    {res.columns.map((c) => (
                      <td key={c.entity_id} className="small">
                        {isUnknown(c[k]) ? <span className="unknown-val">{UNKNOWN_LABEL}</span> : c[k]}
                      </td>))}
                  </tr>))}
                {Object.keys(res.columns[0]?.facades ?? {}).map((f) => (
                  <tr key={f}>
                    <td className="faint small">{prettyAttr(f)}</td>
                    {res.columns.map((c) => (
                      <td key={c.entity_id} className="mono">
                        {isUnknown(c.facades[f]) ? <span className="unknown-val">–</span> : c.facades[f]}
                      </td>))}
                  </tr>))}
                {detailCodes.map((code) => (
                  <tr key={code}>
                    <td className="faint small">{prettyAttr(code)}</td>
                    {res.columns.map((c) => (
                      <td key={c.entity_id} className="mono">
                        {isUnknown(c.details[code]) ? <span className="unknown-val">–</span> : c.details[code]}
                      </td>))}
                  </tr>))}
                <tr>
                  <td className="faint small">PlayStyles</td>
                  {res.columns.map((c) => (
                    <td key={c.entity_id} className="small">
                      {!c.playstyle_data_published
                        ? <span className="unknown-val" title="Data not published — not 'none'">{UNKNOWN_LABEL}</span>
                        : <>
                            <div className="chips">{c.playstyles_base.map((p) => <span key={p} className="chip" style={{ cursor: 'default' }}>{p}</span>)}</div>
                            {c.playstyles_plus.length > 0 && (
                              <div className="chips mt1">{c.playstyles_plus.map((p) => (
                                <span key={p} className="chip on" style={{ cursor: 'default' }}>{p}+</span>))}</div>)}
                          </>}
                    </td>))}
                </tr>
                <tr>
                  <td className="faint small">Rarity</td>
                  {res.columns.map((c) => (
                    <td key={c.entity_id} className="small">
                      {isUnknown(c.rarity) ? <span className="unknown-val">{UNKNOWN_LABEL}</span> : c.rarity}
                    </td>))}
                </tr>
                <tr>
                  <td className="faint small">Market price</td>
                  {res.columns.map((c) => (
                    <td key={c.entity_id} className="small">
                      <span className="unknown-val" title="No verified price feed — never assumed 0 or 'cheap'">
                        {isUnknown(c.price_coins) ? UNKNOWN_LABEL : c.price_coins}
                      </span>
                    </td>))}
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
