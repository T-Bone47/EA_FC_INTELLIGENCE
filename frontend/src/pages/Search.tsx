import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, qs } from '../api/client'
import type { PlayerListItem, ReferenceData } from '../api/types'
import { useApi } from '../lib/useApi'
import { useSession } from '../state/session'
import { ErrorBox, Facades, Loading, Ovr, Pos, Empty } from '../components/common'
import { UNKNOWN_LABEL } from '../lib/format'

interface SearchResponse {
  game_version: string
  total: number
  page: number
  page_size: number
  items: PlayerListItem[]
}
interface Facets {
  nations: { nation: string; n: number }[]
  leagues: { league_name: string; n: number }[]
}

const SORTS: [string, string][] = [
  ['overall_rating', 'Overall'], ['name', 'Name'], ['pace', 'Pace'],
  ['shooting', 'Shooting'], ['passing', 'Passing'], ['dribbling', 'Dribbling'],
  ['defending', 'Defending'], ['physicality', 'Physicality'],
]
const PAGE_SIZE = 25

export default function Search() {
  const { gameVersion, user, notify } = useSession()
  const nav = useNavigate()
  const [params, setParams] = useSearchParams()

  const [q, setQ] = useState(params.get('q') ?? '')
  const [debouncedQ, setDebouncedQ] = useState(q)
  const [position, setPosition] = useState(params.get('position') ?? '')
  const [ovrMin, setOvrMin] = useState(params.get('ovr_min') ?? '')
  const [ovrMax, setOvrMax] = useState(params.get('ovr_max') ?? '')
  const [nation, setNation] = useState(params.get('nation') ?? '')
  const [league, setLeague] = useState(params.get('league') ?? '')
  const [playstyle, setPlaystyle] = useState(params.get('playstyle') ?? '')
  const [sort, setSort] = useState(params.get('sort') ?? 'overall_rating')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>(
    (params.get('sort_dir') as 'asc' | 'desc') ?? 'desc')
  const [page, setPage] = useState(Number(params.get('page') ?? 1))
  const [compareIds, setCompareIds] = useState<string[]>([])
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedQ(q.trim()), 300)
    return () => window.clearTimeout(t)
  }, [q])

  useEffect(() => { setPage(1) }, [debouncedQ, position, ovrMin, ovrMax, nation,
                                  league, playstyle, sort, sortDir, gameVersion])

  const query = useMemo(() => qs({
    game_version: gameVersion, q: debouncedQ || undefined,
    position: position || undefined, ovr_min: ovrMin || undefined,
    ovr_max: ovrMax || undefined, nation: nation || undefined,
    league: league || undefined, playstyle: playstyle || undefined,
    sort, sort_dir: sortDir, page, page_size: PAGE_SIZE,
  }), [gameVersion, debouncedQ, position, ovrMin, ovrMax, nation, league,
       playstyle, sort, sortDir, page])

  const results = useApi<SearchResponse>(`/api/players${query}`, [query])
  const facets = useApi<Facets>(`/api/players/facets${qs({ game_version: gameVersion })}`, [gameVersion])
  const ref = useApi<ReferenceData>(`/api/meta/reference${qs({ game_version: gameVersion })}`, [gameVersion])

  // keep the URL shareable
  useEffect(() => {
    const next: Record<string, string> = {}
    if (debouncedQ) next.q = debouncedQ
    if (position) next.position = position
    if (ovrMin) next.ovr_min = ovrMin
    if (ovrMax) next.ovr_max = ovrMax
    if (nation) next.nation = nation
    if (league) next.league = league
    if (playstyle) next.playstyle = playstyle
    if (sort !== 'overall_rating') next.sort = sort
    if (sortDir !== 'desc') next.sort_dir = sortDir
    if (page > 1) next.page = String(page)
    setParams(next, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ, position, ovrMin, ovrMax, nation, league, playstyle, sort, sortDir, page])

  // load saved list once when authenticated
  useEffect(() => {
    if (!user) { setSavedIds(new Set()); return }
    api.get<{ items: { entity_id: string }[] }>('/api/saved-players')
      .then((d) => setSavedIds(new Set(d.items.map((i) => i.entity_id))))
      .catch(() => { /* non-critical */ })
  }, [user])

  const noData = ref.data?.status === 'NO_DATA'
  const totalPages = results.data ? Math.max(1, Math.ceil(results.data.total / PAGE_SIZE)) : 1

  function toggleCompare(id: string) {
    setCompareIds((ids) => ids.includes(id)
      ? ids.filter((x) => x !== id)
      : ids.length >= 4 ? ids : [...ids, id])
  }

  async function toggleSave(item: PlayerListItem) {
    if (!user) { notify('info', 'Log in to save players.'); nav('/login', { state: { from: '/search' } }); return }
    try {
      if (savedIds.has(item.id)) {
        await api.del(`/api/saved-players/${item.id}`)
        setSavedIds((s) => { const n = new Set(s); n.delete(item.id); return n })
        notify('ok', `Removed ${item.display_name} from saved.`)
      } else {
        await api.post('/api/saved-players', {
          entity_type: 'game_player', entity_id: item.id, game_version: gameVersion })
        setSavedIds((s) => new Set(s).add(item.id))
        notify('ok', `Saved ${item.display_name}.`)
      }
    } catch (e: any) {
      notify('bad', e.detail || 'Could not update saved list.', e.requestId)
    }
  }

  function resetFilters() {
    setQ(''); setPosition(''); setOvrMin(''); setOvrMax('')
    setNation(''); setLeague(''); setPlaystyle('')
    setSort('overall_rating'); setSortDir('desc')
  }

  const positions = ref.data?.positions ?? []

  return (
    <div>
      <div className="page-head">
        <div className="flex1">
          <h1 className="mb0">Player search</h1>
          <div className="sub small">
            {results.data
              ? <>{results.data.total.toLocaleString()} {gameVersion} players match · page {page} of {totalPages}</>
              : <>Indexed, paginated search over the canonical {gameVersion} store.</>}
          </div>
        </div>
        {compareIds.length >= 2 && (
          <button className="btn primary"
                  onClick={() => nav(`/compare?ids=${compareIds.join(',')}`)}>
            Compare {compareIds.length} selected
          </button>
        )}
      </div>

      {noData && (
        <div className="callout warn mb2">
          <div className="t">{gameVersion}: NO_DATA</div>
          <div className="small">
            Zero production records have been ingested for {gameVersion}. The search
            below will honestly return nothing — no FC26 data will be shown under an
            FC27 label, and nothing is fabricated.
          </div>
        </div>
      )}

      <div className="card mb2">
        <div className="row">
          <input
            className="input" style={{ maxWidth: 340 }}
            placeholder="Search name (accent-insensitive)…"
            value={q} maxLength={80}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search players"
          />
          <select className="select" style={{ maxWidth: 150 }} value={sort}
                  onChange={(e) => setSort(e.target.value)} aria-label="Sort by">
            {SORTS.map(([v, l]) => <option key={v} value={v}>Sort: {l}</option>)}
          </select>
          <button className="btn ghost sm" onClick={() => setSortDir(sortDir === 'desc' ? 'asc' : 'desc')}>
            {sortDir === 'desc' ? '↓ desc' : '↑ asc'}
          </button>
          <div className="spacer" />
          <button className="btn ghost sm" onClick={resetFilters}>Reset</button>
        </div>

        <div className="chips mt1" role="group" aria-label="Position filter">
          <button className={`chip ${!position ? 'on' : ''}`} onClick={() => setPosition('')}>All</button>
          {positions.map((p) => (
            <button key={p} className={`chip ${position === p ? 'on' : ''}`}
                    onClick={() => setPosition(position === p ? '' : p)}>{p}</button>
          ))}
        </div>

        <div className="row mt1">
          <label className="tiny faint">OVR</label>
          <input className="input" style={{ width: 72 }} type="number" min={1} max={99}
                 placeholder="min" value={ovrMin}
                 onChange={(e) => setOvrMin(e.target.value)} aria-label="Minimum overall" />
          <span className="faint">–</span>
          <input className="input" style={{ width: 72 }} type="number" min={1} max={99}
                 placeholder="max" value={ovrMax}
                 onChange={(e) => setOvrMax(e.target.value)} aria-label="Maximum overall" />
          <select className="select" style={{ maxWidth: 200 }} value={nation}
                  onChange={(e) => setNation(e.target.value)} aria-label="Nation filter">
            <option value="">Nation: any</option>
            {(facets.data?.nations ?? []).map((n) => (
              <option key={n.nation} value={n.nation}>{n.nation} ({n.n})</option>))}
          </select>
          <select className="select" style={{ maxWidth: 240 }} value={league}
                  onChange={(e) => setLeague(e.target.value)} aria-label="League filter">
            <option value="">League: any</option>
            {(facets.data?.leagues ?? []).map((l) => (
              <option key={l.league_name} value={l.league_name}>{l.league_name} ({l.n})</option>))}
          </select>
          <select className="select" style={{ maxWidth: 200 }} value={playstyle}
                  onChange={(e) => setPlaystyle(e.target.value)} aria-label="PlayStyle filter">
            <option value="">PlayStyle: any</option>
            {(ref.data?.playstyles ?? []).map((p) => (
              <option key={p.playstyle_name} value={p.playstyle_name}>
                {p.playstyle_name} ({p.total_holders})
              </option>))}
          </select>
        </div>
      </div>

      <ErrorBox error={results.error} onRetry={results.reload} />

      <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
        {results.loading ? <Loading label="Searching" /> :
         !results.data || results.data.items.length === 0 ? (
          <Empty title="No players match these filters"
                 hint={noData
                   ? `${gameVersion} has NO ingested data — this empty result is the honest answer.`
                   : `Try widening the search. Missing values are treated as ${UNKNOWN_LABEL}, never as a match.`} />
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th style={{ width: 34 }} aria-label="Compare" />
                <th>OVR</th><th>Pos</th><th>Name</th><th>Nation</th>
                <th>Club</th><th className="hide-sm">League</th>
                <th>Facades</th><th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {results.data.items.map((p) => (
                <tr key={p.id}>
                  <td>
                    <input type="checkbox" aria-label={`Select ${p.display_name} for comparison`}
                           checked={compareIds.includes(p.id)}
                           onChange={() => toggleCompare(p.id)} />
                  </td>
                  <td><Ovr value={p.overall_rating} /></td>
                  <td><Pos value={p.position_primary} /></td>
                  <td>
                    <Link to={`/players/${p.id}`} style={{ fontWeight: 600 }}>
                      {p.display_name}
                    </Link>
                    {p.secondary_positions?.length > 0 && (
                      <span className="tiny faint"> · {p.secondary_positions.join('/')}</span>
                    )}
                  </td>
                  <td className="small">{p.nation ?? <span className="unknown-val">{UNKNOWN_LABEL}</span>}</td>
                  <td className="small">{p.club ?? <span className="unknown-val">{UNKNOWN_LABEL}</span>}</td>
                  <td className="small hide-sm">{p.league ?? <span className="unknown-val">{UNKNOWN_LABEL}</span>}</td>
                  <td><Facades f={p as unknown as Record<string, number | null>} /></td>
                  <td style={{ textAlign: 'right' }} className="nowrap">
                    <button className={`btn sm ${savedIds.has(p.id) ? '' : 'ghost'}`}
                            onClick={() => toggleSave(p)}
                            title={savedIds.has(p.id) ? 'Remove from saved' : 'Save player'}>
                      {savedIds.has(p.id) ? '★' : '☆'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {results.data && results.data.total > PAGE_SIZE && (
        <div className="pager">
          <button className="btn sm ghost" disabled={page <= 1}
                  onClick={() => setPage(page - 1)}>← Prev</button>
          <span>Page {page} / {totalPages}</span>
          <button className="btn sm ghost" disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}>Next →</button>
        </div>
      )}
    </div>
  )
}
