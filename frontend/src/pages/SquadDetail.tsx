import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, qs } from '../api/client'
import type {
  PlayerListItem, RecommendationResponse, ReferenceData,
  SquadDetail as SquadDetailData, SquadEvaluation, SquadSlot,
} from '../api/types'
import { useApi, useAction } from '../lib/useApi'
import { useSession } from '../state/session'
import { Empty, ErrorBox, Loading, Modal, Ovr, Pos } from '../components/common'
import { UNKNOWN_LABEL } from '../lib/format'

/* ------------------------------------------------------------- pitch layout */
const SIDE: Record<string, number> = {
  LW: 0, LM: 0, LB: 0,
  ST: 1, CF: 1, CAM: 1, CM: 1, CDM: 1, CB: 1, GK: 1,
  RW: 2, RM: 2, RB: 2,
}
const ROW_Y: Record<string, number> = {
  GK: 90, LB: 74, CB: 74, RB: 74,
  CDM: 58, CM: 42, LM: 42, RM: 42, CAM: 28,
  LW: 14, ST: 14, RW: 14,
}

function slotCoords(layout: string[]): { x: number; y: number }[] {
  // group slots into visual rows, then spread each row horizontally
  const rows = new Map<number, number[]>()
  layout.forEach((pos, idx) => {
    const y = ROW_Y[pos] ?? 42
    if (!rows.has(y)) rows.set(y, [])
    rows.get(y)!.push(idx)
  })
  // merge rows closer than 10% (e.g. CAM 28 + ST 14 stay apart; CM 42 + CDM 58 apart)
  const coords: { x: number; y: number }[] = new Array(layout.length)
  for (const [y, idxs] of rows) {
    idxs.sort((a, b) => (SIDE[layout[a]] ?? 1) - (SIDE[layout[b]] ?? 1) || a - b)
    idxs.forEach((slotIdx, i) => {
      coords[slotIdx] = { x: ((i + 1) / (idxs.length + 1)) * 100, y }
    })
  }
  return coords
}

/* ------------------------------------------------------------------ page */
export default function SquadDetail() {
  const { id } = useParams<{ id: string }>()
  const { gameVersion, notify } = useSession()
  const nav = useNavigate()
  const squad = useApi<SquadDetailData>(`/api/squads/${id}`, [id])
  const ref = useApi<ReferenceData>(`/api/meta/reference${qs({ game_version: gameVersion })}`, [gameVersion])
  const [evalData, setEvalData] = useState<SquadEvaluation | null>(null)
  const [pickerSlot, setPickerSlot] = useState<number | null>(null)
  const [replaceSlot, setReplaceSlot] = useState<number | null>(null)

  const layout = useMemo(() => {
    const f = squad.data?.formation
    return (f && ref.data?.formations?.[f]) || []
  }, [squad.data, ref.data])
  const coords = useMemo(() => slotCoords(layout), [layout])

  const reloadEval = async () => {
    if (!id) return
    try { setEvalData(await api.get<SquadEvaluation>(`/api/squads/${id}/evaluation`)) }
    catch { setEvalData(null) }
  }
  useEffect(() => { reloadEval() /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [id, squad.data])

  const slotsByIndex = useMemo(() => {
    const m = new Map<number, SquadSlot>()
    for (const s of squad.data?.slots ?? []) m.set(s.slot_index, s)
    return m
  }, [squad.data])

  async function assign(slotIndex: number, playerId: string | null) {
    if (!id) return
    try {
      await api.put(`/api/squads/${id}/slots/${slotIndex}`, {
        slot_index: slotIndex,
        slot_position: layout[slotIndex],
        game_player_id: playerId,
      })
      squad.reload()
      await reloadEval()
      setPickerSlot(null)
      notify('ok', playerId ? 'Slot assigned.' : 'Slot cleared.')
    } catch (e: any) {
      notify('bad', e.detail || 'Assignment failed.', e.requestId)
    }
  }

  async function removeSquad() {
    if (!id || !squad.data) return
    if (!window.confirm(`Delete squad “${squad.data.name}”?`)) return
    await api.del(`/api/squads/${id}`)
    notify('ok', 'Squad deleted.')
    nav('/squads')
  }

  if (squad.loading) return <Loading label="Loading squad" />
  if (squad.error) return (
    <div>
      <div className="page-head"><h1 className="mb0">Squad</h1></div>
      <ErrorBox error={squad.error} onRetry={squad.reload} />
    </div>
  )
  if (!squad.data) return null
  const sq = squad.data
  const versionMismatch = sq.game_version_code !== gameVersion

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="mb0">{sq.name}</h1>
          <div className="sub small">
            {sq.formation} · <span className="badge info">{sq.game_version_code}</span>{' '}
            {versionMismatch && (
              <span className="badge warn">you are browsing {gameVersion} — this squad is {sq.game_version_code} and only accepts its own version</span>)}
          </div>
        </div>
        <div className="spacer" />
        <Link className="btn ghost sm" to="/squads">← All squads</Link>
        <button className="btn ghost sm danger" onClick={removeSquad}>Delete</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 560px) 1fr', gap: '1rem', alignItems: 'start' }}
           className="recommend-layout">
        <div className="card" style={{ padding: '.6rem' }}>
          <div className="pitch" role="group" aria-label={`${sq.formation} squad pitch`}>
            <div className="midline" aria-hidden="true" />
            <div className="circle" aria-hidden="true" />
            {layout.map((pos, i) => {
              const s = slotsByIndex.get(i)
              const filled = !!s?.player_name
              const oop = filled && s?.position_primary && s.position_primary !== pos
              const c = coords[i] ?? { x: 50, y: 50 }
              return (
                <div className="slot" key={i}
                     style={{ left: `${c.x}%`, top: `${c.y}%` }}>
                  <button className={`slot-btn ${filled ? 'filled' : ''} ${oop ? 'oop' : ''}`}
                          onClick={() => setPickerSlot(i)}
                          aria-label={`Slot ${i + 1}: ${pos}${filled ? `, ${s?.player_name}` : ', empty'}`}>
                    <span>
                      <span className="o">{filled ? (s?.overall_rating ?? '–') : pos}</span>
                      <span className="p">{pos}</span>
                    </span>
                  </button>
                  <div className="slot-name" title={s?.player_name ?? ''}>
                    {filled ? s?.player_name : <span className="faint">empty</span>}
                  </div>
                </div>
              )
            })}
          </div>
          <div className="tiny faint mt1 center">
            Click a slot to assign, replace or clear. Orange ring = player is out of position
            for this slot (the API also refuses cross-position assignments).
          </div>
        </div>

        <div className="stack">
          <div className="card">
            <div className="section-title">Chemistry</div>
            {evalData ? (
              <div className="callout warn small mb0">
                <div className="t">{evalData.chemistry.status.replace(/_/g, ' ')}</div>
                {evalData.chemistry.reason}
              </div>
            ) : <div className="small unknown-val">{UNKNOWN_LABEL}</div>}
          </div>

          <div className="card">
            <div className="section-title">Link facts (verified)</div>
            {evalData ? (
              <>
                <div className="kv small">
                  <dt>Clubs</dt>
                  <dd>{(evalData.links.clubs as string[] | undefined)?.length
                    ? <div className="chips">{(evalData.links.clubs as string[]).map((c) => <span key={c} className="chip" style={{ cursor: 'default' }}>{c}</span>)}</div>
                    : <span className="unknown-val">none yet</span>}</dd>
                  <dt>Leagues</dt>
                  <dd>{(evalData.links.leagues as string[] | undefined)?.length
                    ? <div className="chips">{(evalData.links.leagues as string[]).map((c) => <span key={c} className="chip" style={{ cursor: 'default' }}>{c}</span>)}</div>
                    : <span className="unknown-val">none yet</span>}</dd>
                  <dt>Nations</dt>
                  <dd>{(evalData.links.nations as string[] | undefined)?.length
                    ? <div className="chips">{(evalData.links.nations as string[]).map((c) => <span key={c} className="chip" style={{ cursor: 'default' }}>{c}</span>)}</div>
                    : <span className="unknown-val">none yet</span>}</dd>
                  <dt>Filled</dt>
                  <dd className="mono">{String(evalData.links.filled_slots ?? 0)} / {String(evalData.links.total_slots ?? 11)}</dd>
                </div>
              </>
            ) : <Loading label="Loading evaluation" />}
          </div>

          <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
            <div className="section-title" style={{ padding: '1rem 1rem 0' }}>Position checks</div>
            <table className="data">
              <thead>
                <tr><th>Slot</th><th>Expected</th><th>Player</th><th>Plays</th><th>Status</th><th /></tr>
              </thead>
              <tbody>
                {(evalData?.position_checks ?? []).map((c) => {
                  const slot = slotsByIndex.get(c.slot_index)
                  return (
                    <tr key={c.slot_index}>
                      <td className="mono faint">{c.slot_index + 1}</td>
                      <td><Pos value={c.expected_position} /></td>
                      <td className="small">{slot?.player_name
                        ? <Link to={`/players/${slot.game_player_id}`}>{slot.player_name}</Link>
                        : <span className="unknown-val">empty</span>}</td>
                      <td>{slot?.position_primary ? <Pos value={slot.position_primary} /> : <span className="faint">–</span>}</td>
                      <td>
                        {!slot?.player_name ? <span className="badge">—</span>
                         : c.out_of_position ? <span className="badge warn">OUT OF POSITION</span>
                         : <span className="badge ok">IN POSITION</span>}
                      </td>
                      <td className="right nowrap">
                        <button className="btn ghost sm" onClick={() => setReplaceSlot(c.slot_index)}
                                title="Recommend replacements using the rest of the squad as context">
                          ⇄ Replace
                        </button>
                        {slot?.player_name && (
                          <button className="btn ghost sm" onClick={() => assign(c.slot_index, null)}>Clear</button>)}
                      </td>
                    </tr>)
                })}
                {!evalData && <tr><td colSpan={6}><Loading /></td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {pickerSlot !== null && (
        <SlotPickerModal
          slotIndex={pickerSlot}
          slotPosition={layout[pickerSlot]}
          gameVersion={sq.game_version_code}
          onClose={() => setPickerSlot(null)}
          onAssign={(pid) => assign(pickerSlot, pid)}
          current={slotsByIndex.get(pickerSlot)}
        />
      )}

      {replaceSlot !== null && (
        <ReplacementModal
          squadId={id!}
          slotIndex={replaceSlot}
          slotPosition={layout[replaceSlot]}
          onClose={() => setReplaceSlot(null)}
          onAssign={(pid) => assign(replaceSlot, pid)}
        />
      )}
    </div>
  )
}

/* ------------------------------------------------------- slot picker modal */
function SlotPickerModal({ slotIndex, slotPosition, gameVersion, onClose, onAssign, current }: {
  slotIndex: number
  slotPosition: string
  gameVersion: string
  onClose: () => void
  onAssign: (playerId: string | null) => void
  current?: SquadSlot
}) {
  const [q, setQ] = useState('')
  const [onlyPos, setOnlyPos] = useState(true)
  const [debounced, setDebounced] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 300)
    return () => clearTimeout(t)
  }, [q])
  const path = debounced.length >= 1
    ? `/api/players${qs({ game_version: gameVersion, q: debounced,
        position: onlyPos ? slotPosition : undefined, page_size: 12 })}`
    : null
  const results = useApi<{ items: PlayerListItem[] }>(path, [path])

  return (
    <Modal title={<span>Slot {slotIndex + 1} · <Pos value={slotPosition} /></span>} onClose={onClose}>
      {current?.player_name && (
        <div className="callout info small mb2">
          Currently assigned: <strong>{current.player_name}</strong>{' '}
          <button className="btn ghost sm" onClick={() => onAssign(null)}>
            Clear slot
          </button>
        </div>
      )}
      <div className="row mb1">
        <input className="input flex1" autoFocus placeholder={`Search ${slotPosition === 'GK' ? 'goalkeepers' : 'players'}…`}
               value={q} maxLength={80} onChange={(e) => setQ(e.target.value)} />
        <label className="checkbox nowrap">
          <input type="checkbox" checked={onlyPos} onChange={(e) => setOnlyPos(e.target.checked)} />
          {slotPosition} only
        </label>
      </div>
      <div className="tiny faint mb1">
        Assigning a player whose primary position differs from the slot is rejected by
        the API (secondary positions are not treated as verified slot fitness).
      </div>
      {!path ? <Empty title="Type to search" hint={`Only ${gameVersion} players can be assigned — versions are never mixed.`} />
       : results.loading ? <Loading label="Searching" />
       : <ErrorBox error={results.error} onRetry={results.reload} />}
      {results.data && (results.data.items.length === 0 ? (
        <Empty title="No matches" hint="Nothing was fabricated to fill this list." />
      ) : (
        <div className="col">
          {results.data.items.map((p) => (
            <button key={p.id} className="btn ghost" style={{ justifyContent: 'flex-start' }}
                    onClick={() => onAssign(p.id)}>
              <Ovr value={p.overall_rating} /> <Pos value={p.position_primary} />
              <span className="flex1 truncate" style={{ textAlign: 'left' }}>{p.display_name}</span>
              <span className="tiny faint truncate">{p.club ?? UNKNOWN_LABEL}</span>
            </button>
          ))}
        </div>
      ))}
    </Modal>
  )
}

/* --------------------------------------------------- replacement suggestions */
function ReplacementModal({ squadId, slotIndex, slotPosition, onClose, onAssign }: {
  squadId: string
  slotIndex: number
  slotPosition: string
  onClose: () => void
  onAssign: (playerId: string) => void
}) {
  const act = useAction(() => api.post<RecommendationResponse>(
    `/api/squads/${squadId}/recommend-replacement`, { slot_index: slotIndex }))
  useEffect(() => { act.run() /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [])
  const res = act.result

  return (
    <Modal title={<span>Replace slot {slotIndex + 1} · <Pos value={slotPosition} /></span>} onClose={onClose} wide>
      <div className="tiny faint mb1">
        Recommendations use the rest of your squad as context — team_fit evidence shows
        real shared club/league/nation links, never invented chemistry.
      </div>
      {act.pending && <Loading label="Scoring in squad context" />}
      <ErrorBox error={act.error} onRetry={() => act.run()} />
      {res && (
        <div className="col">
          {res.ranked.length === 0 && (
            <Empty title="No candidates pass" hint="The engine refuses to pad results." />
          )}
          {res.ranked.slice(0, 8).map((r, i) => (
            <div key={r.entity_id} className="card tight">
              <div className="row">
                <span className="mono faint">{i + 1}.</span>
                <span className="mono" style={{ color: 'var(--accent)', fontWeight: 700 }}>
                  {r.weighted_score?.toFixed(3) ?? UNKNOWN_LABEL}
                </span>
                <Link to={`/players/${r.entity_id}`} style={{ fontWeight: 650 }}>{r.name}</Link>
                <div className="spacer" />
                <button className="btn primary sm" onClick={() => { onAssign(r.entity_id); onClose() }}>
                  Assign
                </button>
              </div>
              {r.components.team_fit?.status === 'KNOWN' && (
                <div className="tiny faint mt1">
                  team_fit evidence: {r.components.team_fit.evidence.join(' · ')}
                </div>
              )}
              {r.components.team_fit?.status !== 'KNOWN' && (
                <div className="tiny faint mt1">
                  team_fit: {r.components.team_fit?.status.replace(/_/g, ' ') ?? UNKNOWN_LABEL}
                  {r.components.team_fit?.reason ? ` — ${r.components.team_fit.reason}` : ''}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Modal>
  )
}
