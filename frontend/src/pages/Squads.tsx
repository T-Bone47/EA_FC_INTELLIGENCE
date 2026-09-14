import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, qs } from '../api/client'
import type { ReferenceData, SquadSummary } from '../api/types'
import { useApi, useAction } from '../lib/useApi'
import { useSession } from '../state/session'
import { Empty, ErrorBox, Field, Loading } from '../components/common'

export default function Squads() {
  const { gameVersion, notify } = useSession()
  const squads = useApi<SquadSummary[]>('/api/squads')
  const ref = useApi<ReferenceData>(`/api/meta/reference${qs({ game_version: gameVersion })}`, [gameVersion])
  const [name, setName] = useState('')
  const [formation, setFormation] = useState('')
  const [showForm, setShowForm] = useState(false)

  const create = useAction(async () => {
    const s = await api.post<SquadSummary>('/api/squads', {
      name: name.trim(), formation, game_version: gameVersion })
    setName(''); setFormation(''); setShowForm(false)
    squads.reload()
    notify('ok', `Squad “${s.name}” created with ${formation} slots.`)
    return s
  })

  async function remove(s: SquadSummary) {
    if (!window.confirm(`Delete squad “${s.name}”? This cannot be undone.`)) return
    try {
      await api.del(`/api/squads/${s.id}`)
      squads.reload()
      notify('ok', `Deleted “${s.name}”.`)
    } catch (e: any) {
      notify('bad', e.detail || 'Delete failed.', e.requestId)
    }
  }

  const formations = Object.keys(ref.data?.formations ?? {})

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="mb0">Squad builder</h1>
          <div className="sub small">
            Squads are version-scoped: a {gameVersion} squad only accepts {gameVersion} players.
            Link facts are real; chemistry stays UNKNOWN until rules are verified.
          </div>
        </div>
        <button className="btn primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Close' : '+ New squad'}
        </button>
      </div>

      {showForm && (
        <div className="card mb2">
          <div className="row" style={{ alignItems: 'flex-end' }}>
            <div className="field flex1" style={{ maxWidth: 320 }}>
              <label>Squad name</label>
              <input className="input" maxLength={60} value={name}
                     onChange={(e) => setName(e.target.value)} placeholder="My Squad" />
            </div>
            <Field label={`Formation (${gameVersion})`}>
              <select className="select" value={formation} onChange={(e) => setFormation(e.target.value)}>
                <option value="">select…</option>
                {formations.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            </Field>
            <button className="btn primary" disabled={create.pending || !name.trim() || !formation}
                    onClick={() => create.run()}>
              {create.pending ? 'Creating…' : 'Create'}
            </button>
          </div>
          <ErrorBox error={create.error} />
        </div>
      )}

      <ErrorBox error={squads.error} onRetry={squads.reload} />

      {squads.loading ? <Loading label="Loading squads" /> :
       (squads.data?.length ?? 0) === 0 ? (
        <div className="card">
          <Empty title="No squads yet"
                 hint="Create a squad to assign players to formation slots, inspect real club/league/nation links and get slot-level replacement recommendations." />
        </div>
      ) : (
        <div className="grid g3">
          {squads.data!.map((s) => (
            <div key={s.id} className="card hover">
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <Link to={`/squads/${s.id}`} style={{ fontWeight: 650 }}>{s.name}</Link>
                <span className={`badge ${s.game_version === gameVersion ? 'info' : 'warn'}`}>
                  {s.game_version}
                </span>
              </div>
              <div className="small muted mt1">
                {s.formation} · {s.filled_slots}/11 slots filled
              </div>
              <div className="bar mt1">
                <span style={{ width: `${(s.filled_slots / 11) * 100}%` }} />
              </div>
              <div className="row mt2">
                <Link className="btn sm" to={`/squads/${s.id}`}>Open</Link>
                <div className="spacer" />
                <button className="btn ghost sm danger" onClick={() => remove(s)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
