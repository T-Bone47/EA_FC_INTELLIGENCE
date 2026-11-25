import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, qs } from '../api/client'
import type {
  PlayerListItem, ReferenceData,
  SquadDetail as SquadDetailData, SquadSlot,
} from '../api/types'
import { useApi, useAction } from '../lib/useApi'
import { ResearchControl, useRelease } from '../components/Availability'
import { useSession } from '../state/session'
import { Empty, ErrorBox, Loading, Modal, Ovr, Pos } from '../components/common'
import { UNKNOWN_LABEL } from '../lib/format'
import { TACTICS } from '../intelligence/Intelligence'
import LineupOptimizer from './LineupOptimizer'
import type { Entry } from '../intelligence/types'

interface TacticalAnalysis {
  slots: { slot_index: number; slot: string; position: string; status: string;
    score: number | null; coverage: number | null }[]
  strong_slots: string[]
  weak_slots: string[]
  chemistry: { status: string; reason: string }
  budget: { status: string; reason: string }
}
interface TacticalReplacements {
  ranked: (Entry & { score_change: number | null })[]
}


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
  const release = useRelease('game_player')
  const base = useApi<SquadDetailData>(`/api/squads/${id}`)
  const research = base.data?.game_version_code === 'FC27' && release.active
  const scope = qs({ include_research_data: research || undefined })
  const scoped = useApi<SquadDetailData>(research ? `/api/squads/${id}${scope}` : null)
  const squad = research ? scoped : base
  const version = base.data?.game_version_code ?? gameVersion
  const ref = useApi<ReferenceData>(`/api/meta/reference${qs({ game_version: version, include_research_data: research || undefined })}`, [version])
  const analysis = useApi<TacticalAnalysis>(
    squad.data ? `/api/squads/${id}/tactical-analysis${scope}` : null, [squad.data])
  const evalData = analysis.data
  const saveTactic = useAction(async (tactic: string) => {
    await api.patch(`/api/squads/${id}`, { tactics: { ...squad.data?.tactics, tactical_profile: tactic } })
    squad.reload()
  })
  const [pickerSlot, setPickerSlot] = useState<number | null>(null)
  const [replaceSlot, setReplaceSlot] = useState<number | null>(null)

  const layout = useMemo(() => {
    const f = squad.data?.formation
    return (f && ref.data?.formations?.[f]) || []
  }, [squad.data, ref.data])
  const coords = useMemo(() => slotCoords(layout), [layout])

  const slotsByIndex = useMemo(() => {
    const m = new Map<number, SquadSlot>()
    for (const s of squad.data?.slots ?? []) m.set(s.slot_index, s)
    return m
  }, [squad.data])

  async function assign(slotIndex: number, playerId: string | null) {
    if (!id) return
    try {
      await api.put(`/api/squads/${id}/slots/${slotIndex}${scope}`, {
        slot_index: slotIndex,
        slot_position: layout[slotIndex],
        game_player_id: playerId,
      })
      squad.reload()
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

      {version === 'FC27' && <ResearchControl scope="game_player" label="Include FC27 research players" />}
      <label className="field mb2">
        Tactical style
        <select className="select" value={String(sq.tactics?.tactical_profile ?? 'BALANCED')}
                disabled={saveTactic.pending} onChange={e => void saveTactic.run(e.target.value)}>
          {TACTICS.map(tactic => <option key={tactic}>{tactic}</option>)}
        </select>
      </label>
      <ErrorBox error={saveTactic.error} />

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 560px) minmax(0, 1fr)', gap: '1rem', alignItems: 'start' }}
           className="recommend-layout squad-layout">
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

          <div className="card" style={{ overflowX: 'auto' }}>
            <h2 className="section-title">Tactical fit by slot</h2>
            <LineupOptimizer key={JSON.stringify([id,research,sq.formation,sq.tactics,sq.slots])} id={id!} research={research}/>
            {research && <p className="tiny faint">FC27 player ratings snapshot · research only</p>}
            {analysis.loading && <Loading label="Evaluating squad" />}
            <ErrorBox error={analysis.error} onRetry={analysis.reload} />
            {evalData && <>
              {evalData.strong_slots.length > 0 && <p>Strongest assignments: {evalData.strong_slots.join(', ')}</p>}
              {evalData.weak_slots.length > 0 && <p>Review assignments: {evalData.weak_slots.join(', ')}</p>}
              <table className="data">
                <thead><tr><th>Slot</th><th>Player</th><th>Fit</th><th>Coverage</th><th /></tr></thead>
                <tbody>
                  {evalData.slots.map(c => {
                    const slot = slotsByIndex.get(c.slot_index)
                    return <tr key={c.slot_index}>
                      <td>{c.slot}</td>
                      <td>{slot?.player_name ?? (slot?.ut_card_id ? 'UT card' : 'Empty')}</td>
                      <td>{c.score?.toFixed(3) ?? (c.status === 'EMPTY' ? '—' : 'Unavailable')}</td>
                      <td>{c.coverage == null ? '—' : `${Math.round(c.coverage * 100)}%`}</td>
                      <td><button className="btn ghost sm" onClick={() => setReplaceSlot(c.slot_index)}>
                        {slot ? 'Find replacement' : 'Find player'}
                      </button></td>
                    </tr>
                  })}
                </tbody>
              </table>
              <p className="tiny faint mt1">{evalData.budget.reason}</p>
            </>}
          </div>
        </div>
      </div>

      {pickerSlot !== null && (
        <SlotPickerModal
          slotIndex={pickerSlot}
          slotPosition={layout[pickerSlot]}
          gameVersion={sq.game_version_code}
          research={research}
          onClose={() => setPickerSlot(null)}
          onAssign={(pid) => assign(pickerSlot, pid)}
          current={slotsByIndex.get(pickerSlot)}
        />
      )}

      {replaceSlot !== null && (
        <ReplacementModal
          squadId={id!}
          gameVersion={sq.game_version_code}
          research={research}
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
function SlotPickerModal({ slotIndex, slotPosition, gameVersion, research, onClose, onAssign, current }: {
  slotIndex: number
  slotPosition: string
  gameVersion: string
  research: boolean
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
    ? `/api/players${qs({ game_version: gameVersion, include_research_data: research || undefined, q: debounced,
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
function ReplacementModal({ squadId, slotIndex, slotPosition, gameVersion, research, onClose, onAssign }: {
  squadId: string
  slotIndex: number
  slotPosition: string
  gameVersion: string
  research: boolean
  onClose: () => void
  onAssign: (playerId: string) => void
}) {
  const scope = qs({ include_research_data: research || undefined })
  const result = useApi<TacticalReplacements>(`/api/squads/${squadId}/tactical-replacements/${slotIndex}${scope}`)
  return (
    <Modal title={<span>Options for slot {slotIndex + 1} <Pos value={slotPosition} /></span>} onClose={onClose} wide>
      {result.loading && <Loading label="Scoring slot fit" />}
      <ErrorBox error={result.error} onRetry={result.reload} />
      {result.data?.ranked.length === 0 && <Empty title="No better eligible players found" />}
      {result.data?.ranked.map(player => (
        <div key={player.entity_id} className="card tight mb1">
          <div className="row">
            <Link to={`/players/${player.entity_id}${qs({game_version: gameVersion, include_research_data: research || undefined})}`}>
              {player.name}
            </Link>
            <span className="mono">Fit {player.score.toFixed(3)}</span>
            {player.score_change != null && <span>+{player.score_change.toFixed(3)}</span>}
            <div className="spacer" />
            <button className="btn primary sm" onClick={() => { onAssign(player.entity_id); onClose() }}>
              Assign
            </button>
          </div>
          {player.explanation?.reasons?.[0] && <p className="tiny faint">{player.explanation.reasons[0]}</p>}
        </div>
      ))}
    </Modal>
  )
}
