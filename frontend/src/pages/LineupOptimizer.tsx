import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, qs } from '../api/client'
import { Loading, ErrorBox } from '../components/common'
import { useAction } from '../lib/useApi'

type Plan = {receipt: string; filled: number; total_fit: number; slots: {
  slot_index: number; slot: string; player: {name: string; score: number; coverage: number} | null}[]}

export default function LineupOptimizer({id, research}: {id: string; research: boolean}) {
  const [pool,setPool] = useState('squad')
  return <section aria-label="Lineup optimizer" className="card tight">
    <h2>Optimize lineup</h2>
    <label>Player pool <select value={pool} onChange={e=>setPool(e.target.value)}>
      <option value="squad">Players in this squad</option><option value="catalogue">Available player catalogue</option>
    </select></label>
    <p>Fill the most slots, then maximize total tactical fit. Each player can occupy one slot. Prices and chemistry are unavailable.</p>
    <Preview key={pool} id={id} pool={pool} research={research}/>
  </section>
}

function Preview({id,pool,research}: {id: string; pool:string; research:boolean}) {
  const path = '/api/squads/'+id+'/optimal-lineup'
  const query = {include_research_data: research || undefined}
  const preview = useAction(() => api.get<Plan>(path+qs({...query,pool})))
  const [name,setName] = useState('')
  const save = useAction(() => api.post<{id:string}>(path+qs(query),{pool,receipt:preview.result?.receipt,name}))
  return <div><button className="btn" disabled={preview.pending || save.pending} onClick={() => {save.clear(); void preview.run()}}>Preview lineup</button>
    {preview.pending && <Loading label="Optimizing formation" />}<ErrorBox error={preview.error} />
    {!preview.pending && !preview.error && preview.result && <>
      <p>{preview.result.filled} filled · total fit {preview.result.total_fit.toFixed(4)}</p>
      <ul>{preview.result.slots.map(s=><li key={s.slot_index}>{s.slot} · {s.player ? s.player.name+' · '+s.player.score.toFixed(4) : 'Unfilled'}</li>)}</ul>
      <label>New squad name <input value={name} maxLength={80} onChange={e=>setName(e.target.value)}/></label>
      <button className="btn" disabled={!preview.result.filled || !name.trim() || save.pending || !!save.result}
        onClick={() => void save.run()}>Save as new squad</button>
      <ErrorBox error={save.error} />{save.result && <Link to={'/squads/'+save.result.id}>Open optimized squad</Link>}
    </>}
  </div>
}
