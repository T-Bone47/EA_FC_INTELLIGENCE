import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, qs } from '../api/client'
import type { CompareResponse, PlayerListItem, RecommendationRequest, ReferenceData } from '../api/types'
import { useApi, useAction } from '../lib/useApi'
import { useSession } from '../state/session'
import { Empty, ErrorBox, Loading, Ovr, Pos } from '../components/common'
import { UNKNOWN_LABEL, isUnknown, prettyAttr, prettyEnum } from '../lib/format'

interface Picked { id: string; name: string; position: string; overall: number | null }

function PlayerPicker({ onPick, exclude }: { onPick: (p: Picked) => void; exclude: string[] }) {
  const { gameVersion } = useSession()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<PlayerListItem[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (q.trim().length < 2) { setItems([]); return }
    const t = window.setTimeout(async () => {
      setLoading(true)
      try {
        const d = await api.get<{ items: PlayerListItem[] }>(
          `/api/players${qs({ game_version: gameVersion, q: q.trim(), page_size: 6 })}`)
        setItems(d.items.filter((i) => !exclude.includes(i.id)))
      } catch { setItems([]) } finally { setLoading(false) }
    }, 300)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, gameVersion])

  return (
    <div style={{ position: 'relative', minWidth: 240 }} className="flex1">
      <input className="input" placeholder="Search a player to add…" value={q}
             onChange={(e) => { setQ(e.target.value); setOpen(true) }}
             onFocus={() => setOpen(true)} aria-label="Search player to compare" />
      {open && q.trim().length >= 2 && (
        <div className="card" style={{ position: 'absolute', top: '110%', left: 0, right: 0,
                                        zIndex: 20, padding: 0, boxShadow: 'var(--shadow)' }}>
          {loading ? <Loading label="Searching" /> : items.length === 0 ? (
            <div className="small muted" style={{ padding: '.7rem' }}>No matches in {gameVersion}.</div>
          ) : items.map((p) => (
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
  const { gameVersion, notify } = useSession()
  const [params, setParams] = useSearchParams()
  const ref = useApi<ReferenceData>(`/api/meta/reference${qs({ game_version: gameVersion })}`, [gameVersion])
  const [picked, setPicked] = useState<Picked[]>([])
  const [useCtx, setUseCtx] = useState(false)
  const [position, setPosition] = useState('')
  const [tactical, setTactical] = useState('BALANCED')
  const [formation, setFormation] = useState('')

  // hydrate from ?ids= (first load only per version)
  const [hydrated, setHydrated] = useState<string | null>(null)
  useEffect(() => {
    const ids = params.get('ids')
    if (!ids || hydrated === gameVersion) return
    setHydrated(gameVersion)
    const list = ids.split(',').filter(Boolean).slice(0, 4)
    if (!list.length) return
    Promise.all(list.map((id) =>
      api.get<{ game_player: any }>(`/api/players/${id}${qs({ game_version: gameVersion })}`)
        .then((d) => ({ id, name: d.game_player.display_name as string,
                        position: d.game_player.position_primary as string,
                        overall: d.game_player.overall_rating as number | null }))
        .catch(() => null))).then((rows) => {
      const ok = rows.filter((r): r is Picked => !!r)
      if (ok.length < rows.length) notify('info', 'Some ids are not in this game version and were dropped — versions are never mixed.')
      setPicked(ok)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, gameVersion])

  useEffect(() => {
    setParams(picked.length ? { ids: picked.map((p) => p.id).join(',') } : {}, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [picked])

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
    return api.post<CompareResponse>('/api/compare', body)
  })

  useEffect(() => { act.clear(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [gameVersion])

  const res = act.result
  const detailCodes = res?.columns?.[0]
    ? Object.keys(res.columns[0].details) : []

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="mb0">Compare players</h1>
          <div className="sub small">
            Side-by-side facts for {gameVersion}. With “rank for my context” enabled, the
            deterministic engine also says <em>why</em> one beats another for your request.
          </div>
        </div>
      </div>

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
        <div className="chips mt1">
          {picked.map((p) => (
            <span key={p.id} className="chip on">
              <Link to={`/players/${p.id}`}>{p.name}</Link>{' '}
              <button aria-label={`Remove ${p.name}`} style={{ background: 'none', border: 0, color: 'inherit', cursor: 'pointer' }}
                      onClick={() => setPicked(picked.filter((x) => x.id !== p.id))}>×</button>
            </span>
          ))}
          {picked.length === 0 && <span className="tiny faint">Pick 2–4 players…</span>}
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
