/**
 * §42/§49 Card discovery. Server-side filtering + pagination (never loads
 * the whole universe). When no production card data exists the page says so
 * honestly — NO_DATA, never an empty-looking fake list.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { qs } from '../api/client'
import type { CardDataStatus, CardListResponse } from '../api/types'
import { useApi } from '../lib/useApi'
import { useSession } from '../state/session'
import { Empty, ErrorBox, Loading, Ovr, Pos } from '../components/common'
import { DataQualityPanel } from '../components/DataQuality'
import { UNKNOWN_LABEL, dateTime } from '../lib/format'

const SORTS: [string, string][] = [
  ['overall_rating', 'Overall'], ['card_name', 'Card name'],
  ['price', 'Price'], ['updated_at', 'Recently updated'],
]
const PAGE_SIZE = 25

export default function Cards() {
  const { gameVersion } = useSession()
  const [params, setParams] = useSearchParams()
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

  const results = useApi<CardListResponse>(`/api/cards${query}`, [query])
  const status = useApi<CardDataStatus>(
    `/api/card-data-status${qs({ game_version: gameVersion })}`, [gameVersion])

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
  const noData = !results.loading && !results.error && total === 0
    && (status.data?.production_cards ?? 0) === 0

  return (
    <div>
      <div className="page-head">
        <h1 className="mb0">UT Cards</h1>
        <div className="faint small">
          card-level intelligence — attributes, PlayStyles and prices belong to
          the CARD, never silently to the base player
        </div>
      </div>

      <div className="grid g2" style={{ alignItems: 'start' }}>
        <div className="col">
          <div className="card tight">
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

          {results.loading && <Loading label="Loading cards" />}
          {results.error && <ErrorBox error={results.error} onRetry={results.reload} />}

          {!results.loading && !results.error && (
            noData ? (
              <Empty title="No production UT card data yet"
                     hint="The card pipeline (identity, versions, attributes, PlayStyles, Roles, evolutions, prices, provenance) is fully built and DATA-READY — but no legally permitted FC26 card source has been cleared for ingestion. Nothing is fabricated.">
                <div className="callout">
                  See <strong>docs/CARD_DATA_ACQUISITION.md</strong> for the
                  per-source license/permission research and the exact blockers.
                </div>
              </Empty>
            ) : (
              <div className="card tight">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Card</th><th>Pos</th><th>OVR</th><th>Type / rarity</th>
                      <th>Price</th><th>Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((c) => (
                      <tr key={c.id}>
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
                </table>
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
        </div>

        <div className="col">
          {status.loading && <Loading label="Checking data status" />}
          <DataQualityPanel status={status.data} />
        </div>
      </div>
    </div>
  )
}
