/**
 * §42/§49 Card discovery. Server-side filtering + pagination (never loads
 * the whole universe). When no production card data exists the page says so
 * honestly — NO_DATA, never an empty-looking fake list.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import ResearchCards from './ResearchCards'
import { api, qs } from '../api/client'
import type { CardDataStatus, CardListResponse } from '../api/types'
import { useAction, useApi } from '../lib/useApi'
import { ResearchControl, useRelease } from '../components/Availability'
import { useSession } from '../state/session'
import { Empty, ErrorBox, Loading, Ovr, Pos } from '../components/common'
import { PlayerIdentity } from '../components/PlayerIdentity'
import { DataQualityPanel } from '../components/DataQuality'
import { EpistemicChip, PageHeader } from '../components/ui/StadiumPrimitives'
import { UNKNOWN_LABEL, dateTime } from '../lib/format'

interface CardComparison {
  cards: { id: string; card_name: string }[]
  attributes: { attribute: string; left: number | null; right: number | null; delta: number | null }[]
}

function CompareCards({ version, ids }: { version: string; ids: string[] }) {
  const comparison = useAction(() => api.post<CardComparison>('/api/cards/compare', { game_version: version, card_ids: ids }))
  return <section className="card tight mb1" aria-label="Card comparison" style={{ overflowX: 'auto' }}>
    <button className="btn" disabled={ids.length !== 2 || comparison.pending} onClick={() => void comparison.run()}>
      Compare cards
    </button>
    <ErrorBox error={comparison.error} />
    {comparison.pending && <Loading label="Comparing cards" />}
    {comparison.result && <>
      <table className="data">
        <thead><tr><th>Attribute</th>{comparison.result.cards.map(card => <th key={card.id}>{card.card_name}</th>)}<th>Difference</th></tr></thead>
        <tbody>{comparison.result.attributes.map(row => <tr key={row.attribute}>
          <th scope="row">{row.attribute.replace(/_/g, ' ')}</th>
          <td>{row.left ?? UNKNOWN_LABEL}</td><td>{row.right ?? UNKNOWN_LABEL}</td>
          <td>{row.delta == null ? UNKNOWN_LABEL : row.delta > 0 ? `+${row.delta}` : row.delta}</td>
        </tr>)}</tbody>
      </table>
      {!comparison.result.attributes.length && <p>Card attributes are unavailable.</p>}
    </>}
  </section>
}

const SORTS: [string, string][] = [
  ['overall_rating', 'Overall'], ['card_name', 'Card name'],
  ['price', 'Price'], ['updated_at', 'Recently updated'],
]
const PAGE_SIZE = 25

export default function Cards() {
  const { gameVersion } = useSession()
  const [view, setView] = useState<'grid' | 'table'>('grid')
  const release = useRelease('ut_card', gameVersion)
  const localResearch = release.active
  const publicBrowse = !localResearch && release.canBrowse
  const [params, setParams] = useSearchParams()
  const [selection, setSelection] = useState<{ version: string; ids: string[] }>({ version: gameVersion, ids: [] })
  const selected = selection.version === gameVersion ? selection.ids : []
  const [q, setQ] = useState(params.get('q') ?? '')
  const [debouncedQ, setDebouncedQ] = useState(q)
  const [position, setPosition] = useState(params.get('position') ?? '')
  const [rarity, setRarity] = useState(params.get('rarity') ?? '')
  const [ovrMin, setOvrMin] = useState(params.get('ovr_min') ?? '')
  const [priceMax, setPriceMax] = useState(params.get('price_max') ?? '')
  const [sort, setSort] = useState(params.get('sort') ?? 'overall_rating')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>(
    (params.get('sort_dir') as 'asc' | 'desc') ?? 'desc')
  const [page, setPage] = useState(Number(params.get('page') ?? 1))

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedQ(q.trim()), 300)
    return () => window.clearTimeout(t)
  }, [q])
  useEffect(() => { setPage(1) },
    [debouncedQ, position, rarity, ovrMin, priceMax, sort, sortDir, gameVersion])

  const query = useMemo(() => qs({
    game_version: gameVersion, q: debouncedQ || undefined,
    position: position || undefined, rarity: rarity || undefined,
    ovr_min: ovrMin || undefined, price_max: priceMax || undefined,
    sort, sort_dir: sortDir, page, page_size: PAGE_SIZE,
  }), [gameVersion, debouncedQ, position, rarity, ovrMin, priceMax,
       sort, sortDir, page])

  const results = useApi<CardListResponse>(publicBrowse ? `/api/cards${query}` : null)
  const status = useApi<CardDataStatus>(
    publicBrowse ? `/api/card-data-status${qs({ game_version: gameVersion })}` : null, [gameVersion])

  useEffect(() => {
    const next = new URLSearchParams()
    if (debouncedQ) next.set('q', debouncedQ)
    if (position) next.set('position', position)
    if (rarity) next.set('rarity', rarity)
    if (ovrMin) next.set('ovr_min', ovrMin)
    if (priceMax) next.set('price_max', priceMax)
    if (sort !== 'overall_rating') next.set('sort', sort)
    if (sortDir !== 'desc') next.set('sort_dir', sortDir)
    if (page > 1) next.set('page', String(page))
    setParams(next, { replace: true })
  }, [debouncedQ, position, rarity, ovrMin, priceMax, sort, sortDir, page,
      setParams])

  const items = results.data?.items ?? []
  const total = results.data?.total ?? 0
  const noData = results.error?.code === 'DATA_LICENSE_GATE_FAILED' ||
    (results.data != null && total === 0 && status.data?.production_cards === 0)

  return (
    <div className="stack">
      <PageHeader
        title="UT Card Catalogue"
        description="Browse published card versions, traits, PlayStyles, and verified market coverage."
        statusPill={
          <EpistemicChip
            kind={localResearch ? 'hypothetical' : 'observed'}
            label={localResearch ? 'FC27 Local Research' : `${gameVersion} Catalogue`}
          />
        }
      />

      <nav className="stadium-tabs" aria-label="Discovery scope">
        <Link to="/search">Players</Link><Link to="/cards" className="active" aria-current="page">Card versions</Link>
      </nav>
      {gameVersion === 'FC27' && <ResearchControl scope="ut_card" label="Use local FC27 card research" />}
      {localResearch ? <ResearchCards /> : !publicBrowse ? <Empty title={release.status}
        hint={release.canOptIn ? 'Enable local research to browse exact card versions.' : undefined} /> :
      <div className="discovery-layout">
        <aside className="workspace-rail" aria-label="Card filters and source status">
          <div className="card discovery-rail"><h2>Filters</h2>
            <div className="row" style={{ gap: '.6rem' }}>
              <input className="input" style={{ flex: 1, minWidth: 180 }} placeholder="Search card name…"
                     value={q} onChange={(e) => setQ(e.target.value)}
                     aria-label="Card name search" maxLength={80} />
              <select className="input" value={position} aria-label="Position"
                      onChange={(e) => setPosition(e.target.value)}>
                <option value="">Any position</option>
                {['GK','CB','LB','RB','CDM','CM','CAM','LM','RM','LW','RW','ST']
                  .map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
              <input className="input" style={{ maxWidth: 110 }} placeholder="Rarity"
                     value={rarity} onChange={(e) => setRarity(e.target.value)}
                     aria-label="Rarity code" maxLength={40} />
              <input className="input" style={{ maxWidth: 100 }} type="number"
                     placeholder="OVR ≥" min={1} max={99} value={ovrMin}
                     onChange={(e) => setOvrMin(e.target.value)}
                     aria-label="Minimum overall" />
              <input className="input" style={{ maxWidth: 130 }} type="number"
                     placeholder="Max price" min={0} value={priceMax}
                     onChange={(e) => setPriceMax(e.target.value)}
                     aria-label="Maximum price (verified prices only)" />
              <select className="input" value={sort} aria-label="Sort"
                      onChange={(e) => setSort(e.target.value)}>
                {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <button type="button" className="btn ghost"
                      onClick={() => setSortDir(sortDir === 'desc' ? 'asc' : 'desc')}>
                {sortDir === 'desc' ? '↓' : '↑'}
              </button>
            </div>
            {priceMax && (
              <div className="tiny faint mt1">
                Price filters apply only to cards with VERIFIED price
                observations — unpriced cards are UNKNOWN, never treated as free.
              </div>
            )}
          </div>

          <DataQualityPanel status={status.data} />
        </aside>
        <section className="stack" aria-label="Card catalogue results">
          <div className="stadium-tabs" role="group" aria-label="Card view">
            <button type="button" aria-pressed={view === 'grid'} onClick={() => setView('grid')}>Grid</button>
            <button type="button" aria-pressed={view === 'table'} onClick={() => setView('table')}>Table</button>
          </div>
          {results.loading && <Loading label="Loading cards" />}
          {results.error && !noData && <ErrorBox error={results.error} onRetry={results.reload} />}
          {noData && <Empty title={`UT card data unavailable for ${gameVersion}`}
                            hint="There are no approved card records available here." />}

          {!noData && selected.length > 0 && (
            <CompareCards key={`${gameVersion}:${selected.join(',')}`} version={gameVersion} ids={selected} />
          )}
          {!noData && results.data && (
            total === 0 ? (
              <Empty title="No cards match these filters" />
            ) : (
              <div className="stack">
                {view === 'grid' ? (
                  <div className="football-cards-grid">
                    {items.map(c => (
                      <article className={`card discovery-tile football-card ${selected.includes(c.id) ? 'is-selected' : ''}`} key={c.id}>
                        <div className="fc-card-header">
                          <div className="fc-badge-group">
                            <span className="fc-ovr-badge tier-high"><Ovr value={c.overall_rating} /></span>
                            <Pos value={c.position} />
                          </div>
                          <span className="badge info fc-edition-tag">{c.rarity_code ?? c.rarity_raw ?? UNKNOWN_LABEL}</span>
                        </div>
                        <div className="fc-identity-hero">
                          <PlayerIdentity name={c.player_name ?? c.card_name} />
                          <h3 className="fc-player-name">
                            <Link to={`/cards/${c.id}`}>{c.card_name}</Link>
                          </h3>
                          <p className="fc-club-nation muted small mb0">
                            {c.player_name ? `${c.player_name} · ` : ''}
                            {c.price_coins != null ? `${c.price_coins.toLocaleString()} coins` : 'Price unavailable'}
                          </p>
                        </div>
                        <div className="fc-action-tray">
                          <label className="checkbox">
                            <input
                              type="checkbox"
                              checked={selected.includes(c.id)}
                              disabled={selected.length === 2 && !selected.includes(c.id)}
                              onChange={() => setSelection({
                                version: gameVersion,
                                ids: selected.includes(c.id) ? selected.filter(id => id !== c.id) : [...selected, c.id]
                              })}
                            />
                            <span>Compare {c.card_name}</span>
                          </label>
                          <Link to={`/cards/squad-lab?item=${c.id}`} className="fc-inspect-link">
                            Squad Lab ▦
                          </Link>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : <div className="card scroll-table"><table className="data">
                  <thead>
                    <tr>
                      <th scope="col">Compare</th><th>Card</th><th>Pos</th><th>OVR</th><th>Type / rarity</th>
                      <th>Price</th><th>Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((c) => (
                      <tr key={c.id}>
                        <td><input type="checkbox" aria-label={`Compare ${c.card_name}`} checked={selected.includes(c.id)}
                                   disabled={selected.length === 2 && !selected.includes(c.id)}
                                   onChange={() => setSelection({ version: gameVersion,
                                     ids: selected.includes(c.id) ? selected.filter(id => id !== c.id) : [...selected, c.id] })} /></td>
                        <td>
                          <Link to={`/cards/${c.id}`}>{c.card_name}</Link>
                          {c.player_name && (
                            <div className="tiny faint">{c.player_name}</div>
                          )}
                        </td>
                        <td><Pos value={c.position} /></td>
                        <td><Ovr value={c.overall_rating} /></td>
                        <td className="small">
                          {c.card_type ?? UNKNOWN_LABEL}
                          <span className="faint"> · {c.rarity_code ?? c.rarity_raw ?? UNKNOWN_LABEL}</span>
                          {!c.playstyle_data_published && (
                            <div className="tiny faint">PlayStyles: UNKNOWN</div>
                          )}
                        </td>
                        <td>{c.price_coins != null
                          ? `${c.price_coins.toLocaleString()} coins`
                          : <span className="badge unknown">UNKNOWN</span>}</td>
                        <td className="tiny faint">
                          {c.updated_at ? dateTime(c.updated_at) : UNKNOWN_LABEL}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table></div>}
                <div className="row mt1" style={{ justifyContent: 'space-between' }}>
                  <span className="small faint">
                    {total} card{total === 1 ? '' : 's'} · page {page} of
                    {' '}{Math.max(1, Math.ceil(total / PAGE_SIZE))}
                  </span>
                  <span className="row" style={{ gap: '.5rem' }}>
                    <button type="button" className="btn ghost" disabled={page <= 1}
                            onClick={() => setPage(page - 1)}>Prev</button>
                    <button type="button" className="btn ghost"
                            disabled={page * PAGE_SIZE >= total}
                            onClick={() => setPage(page + 1)}>Next</button>
                  </span>
                </div>
              </div>
            )
          )}
        </section>
      </div>}
    </div>
  )
}
