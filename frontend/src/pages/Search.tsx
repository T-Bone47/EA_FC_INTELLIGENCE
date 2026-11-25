import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { api, qs } from '../api/client'
import type { PlayerListItem, ReferenceData } from '../api/types'
import { useApi } from '../lib/useApi'
import { useSession } from '../state/session'
import { useCopilot, useCopilotRouteContext } from '../state/copilot'
import { ErrorBox, Facades, Loading, Ovr, Pos, Empty } from '../components/common'
import { StadiumField, StadiumInput, StadiumSelect } from '../components/StadiumControls'
import { ResearchControl, useRelease } from '../components/Availability'
import { FootballCard } from '../components/FootballCard'
import { StadiumIcon } from '../components/StadiumIcons'
import { EpistemicChip, PageHeader } from '../components/ui/StadiumPrimitives'
import { UNKNOWN_LABEL } from '../lib/format'

interface SearchResponse {
  game_version: string
  total: number
  page: number
  page_size: number
  items: PlayerListItem[]
  research_only?: boolean
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
  const { openCopilot } = useCopilot()
  const nav = useNavigate()
  const [params, setParams] = useSearchParams()
  const { state } = useLocation()
  const quickSearch = (state as { quickSearch?: string } | null)?.quickSearch

  const [view, setView] = useState<'grid' | 'table'>('grid')
  const release = useRelease('game_player', gameVersion)
  const optedIn = release.active
  const browsing = release.canBrowse
  const [q, setQ] = useState(params.get('q') ?? '')
  const [debouncedQ, setDebouncedQ] = useState(q)
  useEffect(() => { if (quickSearch !== undefined) setQ(quickSearch) }, [quickSearch])
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
                                  league, playstyle, sort, sortDir, gameVersion, optedIn])

  const query = useMemo(() => qs({
    game_version: gameVersion, include_research_data: optedIn || undefined, q: debouncedQ || undefined,
    position: position || undefined, ovr_min: ovrMin || undefined,
    ovr_max: ovrMax || undefined, nation: nation || undefined,
    league: league || undefined, playstyle: playstyle || undefined,
    sort, sort_dir: sortDir, page, page_size: PAGE_SIZE,
  }), [gameVersion, optedIn, debouncedQ, position, ovrMin, ovrMax, nation, league,
       playstyle, sort, sortDir, page])

  const results = useApi<SearchResponse>(browsing ? `/api/players${query}` : null)
  const scope = qs({ game_version: gameVersion, include_research_data: optedIn || undefined })
  const facets = useApi<Facets>(browsing ? '/api/players/facets' + scope : null)
  const ref = useApi<ReferenceData>(browsing ? '/api/meta/reference' + scope : null)

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

  useEffect(() => { setCompareIds([]) }, [gameVersion, optedIn])
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

  // Active filter chip helpers
  const activeFilters = useMemo(() => {
    const list: { key: string; label: string; clear: () => void }[] = []
    if (debouncedQ) list.push({ key: 'q', label: `Search: "${debouncedQ}"`, clear: () => setQ('') })
    if (position) list.push({ key: 'pos', label: `Pos: ${position}`, clear: () => setPosition('') })
    if (ovrMin || ovrMax) list.push({ key: 'ovr', label: `OVR: ${ovrMin || '1'}–${ovrMax || '99'}`, clear: () => { setOvrMin(''); setOvrMax('') } })
    if (nation) list.push({ key: 'nat', label: `Nation: ${nation}`, clear: () => setNation('') })
    if (league) list.push({ key: 'lea', label: `League: ${league}`, clear: () => setLeague('') })
    if (playstyle) list.push({ key: 'ps', label: `PlayStyle: ${playstyle}`, clear: () => setPlaystyle('') })
    return list
  }, [debouncedQ, position, ovrMin, ovrMax, nation, league, playstyle])

  useCopilotRouteContext({
    route_name: 'PLAYER_DISCOVERY',
    game_version: gameVersion === 'FC26' ? 'FC26' : 'FC27',
    selected_card_ids: compareIds,
    active_filters: {
      q: debouncedQ || null,
      position: position || null,
      ovr_min: ovrMin || null,
      ovr_max: ovrMax || null,
      playstyle: playstyle || null,
    },
  })

  return (
    <div className="stack">
      <PageHeader
        title="Player Discovery"
        description={results.data
          ? `${results.data.total.toLocaleString()} players match active scouting criteria · Page ${page} of ${totalPages}`
          : `Search and evaluate the ${gameVersion} player catalogue.`}
        statusPill={
          <EpistemicChip
            kind={results.data?.research_only ? 'hypothetical' : 'observed'}
            label={results.data?.research_only ? 'FC27 Research' : `${gameVersion} Catalogue`}
          />
        }
        actions={
          <>
            {!optedIn && compareIds.length >= 2 && (
              <button
                type="button"
                className="btn primary sm"
                onClick={() => nav(`/compare?ids=${compareIds.join(',')}`)}
              >
                <StadiumIcon name="compare" size={14} />
                <span>Compare {compareIds.length} selected</span>
              </button>
            )}
            <button
              type="button"
              className="btn ghost sm"
              onClick={() => openCopilot({
                prompt: position
                  ? `Which ${position} targets in my current filters best fit my Gamer DNA?`
                  : 'Which players matching these search filters fit my tactical style best?',
              })}
            >
              <StadiumIcon name="coach" size={14} />
              <span>Ask Co-Pilot</span>
            </button>
            <Link className="btn ghost sm" to="/cards/squad-lab">
              <StadiumIcon name="squad" size={14} />
              <span>Open Squad Lab</span>
            </Link>
          </>
        }
      />

      <nav className="stadium-tabs" aria-label="Discovery scope">
        <Link to="/search" className="active" aria-current="page">Players</Link>
        <Link to="/cards">Card versions</Link>
      </nav>
      {gameVersion === 'FC27' && <ResearchControl scope="game_player" label="Include FC27 research players" />}
      {results.data?.research_only && (
        <p className="callout info small" style={{ maxWidth: '72ch' }}>
          FC27 research snapshot · Pinned dataset: {release.data?.research?.release_id} · Non-commercial research scope
        </p>
      )}
      {!browsing && (
        <Empty
          title={release.status}
          hint={release.canOptIn
            ? 'Enable FC27 local research above to browse the research player pool, or switch to FC26 in the workspace header.'
            : 'Verify database connectivity in Overview or switch to FC26 in the workspace header.'}
        />
      )}

      {browsing && <div className="discovery-layout">
        {/* Left Filter Rail */}
        <section className="card discovery-rail" aria-label="Player filters">
          <div className="row space-between align-center">
            <h2 className="mb0">Scouting Filters</h2>
            {activeFilters.length > 0 && (
              <button className="btn ghost sm" onClick={resetFilters}>Reset all</button>
            )}
          </div>

          <div className="mt1">
            <StadiumField label="Search Player Name" hint="Search verified database">
              <StadiumInput
                placeholder="Search player name…"
                value={q}
                maxLength={80}
                onChange={(e) => setQ(e.target.value)}
                aria-label="Search players"
                clearable
                onClear={() => setQ('')}
              />
            </StadiumField>
          </div>

          {/* Active Filter Chips Tray */}
          {activeFilters.length > 0 && (
            <div className="active-filter-chips" aria-label="Active filters">
              {activeFilters.map(f => (
                <span className="filter-chip-item" key={f.key}>
                  {f.label}
                  <button
                    type="button"
                    className="filter-chip-remove"
                    onClick={f.clear}
                    aria-label={`Remove filter ${f.label}`}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}

          {/* Position Selector */}
          <div className="mt1">
            <label className="section-title">Tactical Position</label>
            <div className="chips mt05" role="group" aria-label="Position filter">
              <button className={`chip ${!position ? 'on' : ''}`} onClick={() => setPosition('')}>All</button>
              {positions.map((p) => (
                <button key={p} className={`chip ${position === p ? 'on' : ''}`}
                        onClick={() => setPosition(position === p ? '' : p)}>{p}</button>
              ))}
            </div>
          </div>

          {/* OVR Range */}
          <div className="mt1">
            <label className="section-title">Overall Rating Range</label>
            <div className="row mt05 align-center gap05">
              <StadiumInput
                style={{ width: 88 }}
                type="number"
                min={1}
                max={99}
                placeholder="Min"
                value={ovrMin}
                onChange={(e) => setOvrMin(e.target.value)}
                aria-label="Minimum overall"
              />
              <span className="faint">–</span>
              <StadiumInput
                style={{ width: 88 }}
                type="number"
                min={1}
                max={99}
                placeholder="Max"
                value={ovrMax}
                onChange={(e) => setOvrMax(e.target.value)}
                aria-label="Maximum overall"
              />
            </div>
          </div>

          {/* Detailed Facets */}
          <div className="stack gap07 mt1">
            <label className="section-title mb0">Cohort & Profile</label>
            <StadiumField label="Nation">
              <StadiumSelect
                value={nation}
                onChange={(val) => setNation(val)}
                aria-label="Nation filter"
              >
                <option value="">Nation: Any</option>
                {(facets.data?.nations ?? []).map((n) => (
                  <option key={n.nation} value={n.nation}>{n.nation} ({n.n})</option>
                ))}
              </StadiumSelect>
            </StadiumField>

            <StadiumField label="League">
              <StadiumSelect
                value={league}
                onChange={(val) => setLeague(val)}
                aria-label="League filter"
              >
                <option value="">League: Any</option>
                {(facets.data?.leagues ?? []).map((l) => (
                  <option key={l.league_name} value={l.league_name}>{l.league_name} ({l.n})</option>
                ))}
              </StadiumSelect>
            </StadiumField>

            <StadiumField label="PlayStyle">
              <StadiumSelect
                value={playstyle}
                onChange={(val) => setPlaystyle(val)}
                aria-label="PlayStyle filter"
              >
                <option value="">PlayStyle: Any</option>
                {(ref.data?.playstyles ?? []).map((p) => (
                  <option key={p.playstyle_name} value={p.playstyle_name}>
                    {p.playstyle_name} ({p.total_holders})
                  </option>
                ))}
              </StadiumSelect>
            </StadiumField>
          </div>

          {/* Sorting */}
          <div className="mt1">
            <label className="section-title">Sort Candidates</label>
            <div className="row mt05 align-center gap05">
              <div className="flex1">
                <StadiumSelect
                  value={sort}
                  onChange={(val) => setSort(val)}
                  aria-label="Sort by"
                >
                  {SORTS.map(([v, l]) => <option key={v} value={v}>Sort: {l}</option>)}
                </StadiumSelect>
              </div>
              <button
                type="button"
                className="btn ghost sm"
                onClick={() => setSortDir(sortDir === 'desc' ? 'asc' : 'desc')}
                title="Toggle sort direction"
              >
                {sortDir === 'desc' ? '↓ Desc' : '↑ Asc'}
              </button>
            </div>
          </div>
        </section>

        {/* Main Content Workspace */}
        <section className="stack" aria-label="Player results">
          <div className="row space-between align-center">
            <div className="stadium-tabs" role="group" aria-label="Player view">
              <button type="button" aria-pressed={view === 'grid'} onClick={() => setView('grid')}>Grid</button>
              <button type="button" aria-pressed={view === 'table'} onClick={() => setView('table')}>Table</button>
            </div>
            {results.data && (
              <span className="tiny faint">
                Showing {results.data.items.length} of {results.data.total} candidates
              </span>
            )}
          </div>

          <ErrorBox error={results.error} onRetry={results.reload} />

          <div className={view === 'table' ? 'card scroll-table' : undefined}>
            {results.loading ? <Loading label="Searching player intelligence" /> :
             !results.data || results.data.items.length === 0 ? (
              <div className="card">
                <Empty
                  title="No players match these filters"
                  hint={`Try widening the search parameters. Missing values are treated as ${UNKNOWN_LABEL}, never as a fabricated match.`}
                />
                {activeFilters.length > 0 && (
                  <div className="row mt1" style={{ justifyContent: 'center' }}>
                    <button type="button" className="btn ghost sm" onClick={resetFilters}>Reset all filters</button>
                  </div>
                )}
              </div>
            ) : view === 'grid' ? (
              <div className="discovery-tiles">
                {results.data.items.map(p => (
                  <FootballCard
                    key={p.id}
                    player={p}
                    gameVersion={gameVersion}
                    isResearch={!!results.data?.research_only}
                    optedIn={optedIn}
                    isCompared={compareIds.includes(p.id)}
                    isSaved={savedIds.has(p.id)}
                    onToggleCompare={toggleCompare}
                    onToggleSave={toggleSave}
                  />
                ))}
              </div>
            ) : (
              <table className="data">
                <thead>
                  <tr>
                    <th style={{ width: 42 }} aria-label="Compare" />
                    <th>OVR</th><th>Pos</th><th>Name</th><th>Nation</th>
                    <th>Club</th><th className="hide-sm">League</th>
                    <th>Facades</th><th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {results.data.items.map((p) => (
                    <tr key={p.id}>
                      <td>
                        {!optedIn && (
                          <label className="checkbox" style={{ justifyContent: 'center', margin: 0 }}>
                            <input
                              type="checkbox"
                              aria-label={`Select ${p.display_name} for comparison`}
                              checked={compareIds.includes(p.id)}
                              onChange={() => toggleCompare(p.id)}
                            />
                          </label>
                        )}
                      </td>
                      <td><Ovr value={p.overall_rating} /></td>
                      <td><Pos value={p.position_primary} /></td>
                      <td>
                        <Link to={`/players/${p.id}${qs({ game_version: gameVersion, include_research_data: optedIn || undefined })}`} style={{ fontWeight: 600 }}>
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
                        <div className="row gap05" style={{ justifyContent: 'flex-end' }}>
                          <Link
                            to={`/intelligence?position=${p.position_primary}&game_version=${gameVersion}`}
                            className="btn ghost sm"
                            title="Analyze in Intelligence Studio"
                            aria-label={`Analyze ${p.display_name} in Intelligence Studio`}
                          >
                            <StadiumIcon name="zap" size={14} />
                          </Link>
                          {!optedIn && (
                            <button
                              type="button"
                              className={`btn sm ${savedIds.has(p.id) ? 'accent' : 'ghost'}`}
                              aria-pressed={savedIds.has(p.id)}
                              onClick={() => toggleSave(p)}
                              title={savedIds.has(p.id) ? 'Remove from saved' : 'Save player'}
                              aria-label={savedIds.has(p.id) ? `Remove ${p.display_name} from saved` : `Save ${p.display_name}`}
                            >
                              <StadiumIcon name="star" size={14} />
                            </button>
                          )}
                        </div>
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
              <span>Page {page} of {totalPages}</span>
              <button className="btn sm ghost" disabled={page >= totalPages}
                      onClick={() => setPage(page + 1)}>Next →</button>
            </div>
          )}
        </section>
      </div>}
    </div>
  )
}
