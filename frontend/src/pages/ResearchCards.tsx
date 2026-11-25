import { useState } from 'react'
import { Link } from 'react-router-dom'
import { DecisionRange, LeaderEvidence } from '../intelligence/DecisionEvidence'
import { api, qs } from '../api/client'
import { PlayerIdentity } from '../components/PlayerIdentity'
import { ErrorBox, Loading, Ovr, Pos } from '../components/common'
import { useAction, useApi } from '../lib/useApi'
import { POSITIONS, TACTICS } from '../intelligence/Intelligence'
import type { Entry, LeadingPair, PairwiseItem, RecommendationOptions, WhatIfResponse } from '../intelligence/types'

const base = '/api/research/fc27/cards'
type Item = { entity_id: string; source_item_id: string; name: string; rarity: string; positions: string[];
  overall: number | null; source_snapshot_id: string; playstyles: {base: string[]; plus: string[]} | null; base_identity_status: string; editorial_role_fit: string | null;
  position_issues: {value: string}[] }
type Ranked = Entry & { card: Item }
type Result = { request_id?:string; feedback_receipt?:string; ranked?: Ranked[]; players?: Ranked[]; pairwise?: PairwiseItem[]; leading_pair?: LeadingPair | null;
  counts?: {candidates: number; not_evaluable: number; excluded: number}; cards?: (Item & {attributes: Record<string,number>})[];
  excluded?: {name: string; reason: string}[]; outside_observed_position?: string[] }

export default function ResearchCards({ comparison = false }: { comparison?: boolean }) {
  const [name, setName] = useState('')
  const [offset, setOffset] = useState(0)
  const [positionFilter, setPositionFilter] = useState('')
  const [rating, setRating] = useState('')
  const [rarity, setRarity] = useState('')
  const [playstyle, setPlaystyle] = useState('')
  const [view, setView] = useState<'grid' | 'table'>('grid')
  const [opened, setOpened] = useState<Item | null>(null)
  const [selected, setSelected] = useState<Item[]>([])
  const [position, setPosition] = useState('RW')
  const [tactic, setTactic] = useState('BALANCED')
  const [plus, setPlus] = useState('')
  const [formation, setFormation] = useState('')
  const [slot, setSlot] = useState('')
  const options = useApi<RecommendationOptions>('/api/v3/options')
  const items = useApi<{total: number; items: Item[]}>(base + qs({include_research_data: true, q: name, offset, position: positionFilter, ovr_min: rating, rarity, playstyle}))
  const slots = options.data?.formations[formation] ?? []
  const request = {game_version: 'FC27', entity_scope: 'ut_card', include_research_data: true, position,
    tactical_profile: tactic, limit: 8, desired_playstyles_plus: plus.trim() ? [plus.trim()] : [],
    ...(formation ? {formation, slot} : {})}
  return <section className="stack" aria-label="FC27 card research">
    <h2>FC27 card research</h2>
    <div className="row">
      <Link className="btn ghost sm" to="/cards/squad-lab">Open Ultimate Team Squad Lab</Link>
      <Link className="btn ghost sm" to="/cards/performance">Performance Evidence Lab</Link>
    </div>
    <p>Local item observations. Market prices, official role tiers and chemistry are unavailable.</p>
    <div className="discovery-layout">
    <section className="card workspace-rail discovery-rail"><h3>Card filters</h3>
    <label>Find a card by name or item ID <input className="input" value={name} maxLength={80}
      onChange={e => { setName(e.target.value); setOffset(0) }} /></label>
    <label>Observed position <select value={positionFilter} onChange={e => { setPositionFilter(e.target.value); setOffset(0) }}>
      <option value="">Any observed position</option>{POSITIONS.map(p => <option key={p}>{p}</option>)}</select></label>
    <label>Minimum item overall <input type="number" min={1} max={99} value={rating} onChange={e => { setRating(e.target.value); setOffset(0) }} /></label>
    <label>Rarity <input maxLength={80} value={rarity} onChange={e => { setRarity(e.target.value); setOffset(0) }} /></label>
    <label>Published PlayStyle <input maxLength={60} value={playstyle} onChange={e => { setPlaystyle(e.target.value); setOffset(0) }} /></label>
    <p className="muted small mb0">Source: pinned FC27 local item release</p></section>
    <section className="stack" aria-label="Matching card versions">
    <div className="stadium-tabs" role="group" aria-label="Research card view">
      <button type="button" aria-pressed={view === 'grid'} onClick={() => setView('grid')}>Grid</button>
      <button type="button" aria-pressed={view === 'table'} onClick={() => setView('table')}>List</button>
    </div>
    <ErrorBox error={items.error} onRetry={items.reload} />
    {items.loading && <Loading label="Finding card versions" />}
    {items.data && <>
      <p>{items.data.total} matching items</p>
      <div className={view === 'grid' ? 'discovery-tiles' : 'col'}>{items.data.items.map(c => <div className="card discovery-tile" key={c.entity_id}>
        {view === 'grid' && <PlayerIdentity name={c.name} />}
        <div className="row"><Ovr value={c.overall} />{c.positions.map(pos => <Pos key={pos} value={pos} />)}</div>
        <h3>{c.name}</h3><p className="muted small mb0">{c.rarity} · Item {c.source_item_id}</p>
        <label><input type="checkbox" aria-label={`Compare ${c.name}, ${c.rarity}, item ${c.source_item_id}`}
          checked={selected.some(s => s.entity_id === c.entity_id)}
          disabled={selected.length === 2 && !selected.some(s => s.entity_id === c.entity_id)}
          onChange={e => setSelected(e.target.checked ? [...selected,c] : selected.filter(s => s.entity_id !== c.entity_id))} /> Compare</label>
        <div className="row">
          <button className="btn ghost sm" type="button" onClick={() => setOpened(opened?.entity_id === c.entity_id ? null : c)}
            aria-expanded={opened?.entity_id === c.entity_id}>Item details</button>
          <Link to={`/cards/squad-lab${qs({ item: c.source_item_id })}`} className="btn ghost sm">Open in Squad Lab</Link>
        </div>
        {opened?.entity_id === c.entity_id && <ItemDetails item={c} />}
      </div>)}</div>
      <div className="row"><button className="btn ghost" disabled={offset === 0} onClick={() => setOffset(offset-25)}>Previous items</button>
      <button className="btn ghost" disabled={offset+25 >= items.data.total} onClick={() => setOffset(offset+25)}>Next items</button></div>
    </>}
    </section></div>
    {selected.length > 0 && <p>Selected: {selected.map(c => c.name+' '+c.rarity).join(' / ')} <button className="btn ghost" onClick={() => setSelected([])}>Clear</button></p>}
    <section className="card stack"><h3>{comparison ? 'Comparison context' : 'Tactical evaluation'}</h3><div className="row">
      <label>Formation <select aria-label="Formation" value={formation} onChange={e => {setFormation(e.target.value); setSlot('')}}>
        <option value="">Any</option>{Object.keys(options.data?.formations ?? {}).map(s => <option key={s}>{s}</option>)}</select></label>
      {formation && <label>Formation slot <select aria-label="Formation slot" value={slot} onChange={e => {setSlot(e.target.value)
        const s = slots.find(s => s.slot === e.target.value); if(s) setPosition(s.position)}}>
        <option value="">Select slot</option>{slots.map(s => <option key={s.slot}>{s.slot}</option>)}</select></label>}
      <label>Card position <select value={position} disabled={!!formation} onChange={e => setPosition(e.target.value)}>
        {POSITIONS.map(s => <option key={s}>{s}</option>)}</select></label>
      <label>Card tactics <select value={tactic} onChange={e => setTactic(e.target.value)}>
        {TACTICS.map(s => <option key={s}>{s}</option>)}</select></label>
      <label>Preferred PlayStyle+ <input value={plus} maxLength={60} onChange={e => setPlus(e.target.value)}/></label>
    </div>
    <CardResults key={JSON.stringify([request,selected.map(c=>c.entity_id)])} request={request}
      ready={!!items.data && (!formation || !!slot)} ids={selected.map(c => c.entity_id)} comparison={comparison} />
    {!!items.data && (!formation || !!slot) && <TacticalChange key={JSON.stringify(request)} request={request} tactic={tactic}/>}
    </section>
  </section>
}

function ItemDetails({ item }: { item: Item }) {
  const result = useApi<Item & { attributes: Record<string, number> }>(base + '/items/' + item.entity_id + qs({ include_research_data: true }))
  const data = result.data
  return <div className="stack">
    {result.loading && <Loading label="Loading exact item attributes" />}
    <ErrorBox error={result.error} onRetry={result.reload} />
    {data && <>
      <p className="muted mb0">Snapshot {data.source_snapshot_id} · Base link {data.base_identity_status}</p>
      <p className="mb0">PlayStyles: {data.playstyles?.base.join(', ') || 'Unavailable'}<br />
        PlayStyles+: {data.playstyles?.plus.join(', ') || 'Unavailable'}</p>
      <p className="muted mb0">Editorial role observation: {data.editorial_role_fit || 'Unavailable'}</p>
      <details><summary>Published attributes</summary>
        {Object.keys(data.attributes).length ? <dl className="kv">{Object.entries(data.attributes).map(([name, value]) =>
          <div className="attribute-pair" key={name}><dt>{name.replace(/_/g, ' ')}</dt><dd>{value}</dd></div>)}</dl>
          : <p>No published attributes.</p>}
      </details>
    </>}
  </div>
}

function ItemFeedback({receipt,requestId,item}:{receipt:string;requestId:string;item:string}) {
  const action = useAction((choice:string)=>api.post<{status:string}>(base+'/feedback',
    {include_research_data:true,receipt,recommendation_id:requestId,card_item_id:item,action:choice}))
  return <div>{action.result ? <span role="status">Card feedback recorded</span> : <>
    <button className="btn ghost" disabled={action.pending} onClick={()=>void action.run('SELECTED')}>Useful fit</button>
    <button className="btn ghost" disabled={action.pending} onClick={()=>void action.run('REJECTED')}>Poor fit</button>
    </>}<ErrorBox error={action.error}/></div>
}

function Stability({request,cards}:{request:object;cards:Item[]}) {
  const work = useAction(()=>api.post<{outcomes:{profile:string;leader:string|null;scores:Record<string,number>}[];
    position_fits:Record<string,Record<string,{score:number;coverage:number}>>}>(
    base+'/compare-tactics',{request,card_ids:cards.map(c=>c.entity_id),profiles:TACTICS}))
  return <section><button className="btn" disabled={work.pending} onClick={()=>void work.run()}>Compare across six tactics</button>
    {work.pending && <Loading label="Testing tactical stability"/>}<ErrorBox error={work.error}/>
    {work.result?.outcomes.map(o=><p key={o.profile}>{o.profile} · {cards.map(c=>c.rarity+' '+(o.scores[c.entity_id]?.toFixed(4)??'Unavailable')).join(' / ')}
      {' · '}{o.leader?'Clear lead: '+cards.find(c=>c.entity_id===o.leader)?.source_item_id:'No clear lead'}</p>)}
    {work.result && <details><summary>Observed positions under the selected tactic</summary>
      {Object.entries(work.result.position_fits).map(([p,rows])=><p key={p}>{p} · {cards.map(c=>c.rarity+' '+(rows[c.entity_id]?.score.toFixed(4)??'Unavailable')).join(' / ')}</p>)}</details>}</section>
}

function TacticalChange({request,tactic}: {request: object; tactic: string}) {
  const [other,setOther] = useState(TACTICS.find(t => t !== tactic)!)
  return <section><label>Alternative tactics <select value={other} onChange={e=>setOther(e.target.value)}>
    {TACTICS.filter(t=>t !== tactic).map(t=><option key={t}>{t}</option>)}</select></label>
    <Scenario key={other} other={other} request={request}/></section>
}

function Scenario({request,other}: {request:object; other:string}) {
  const action = useAction(()=>api.post<WhatIfResponse>(base+'/what-if'+qs({tactical_profile:other}),request))
  return <><button className="btn" disabled={action.pending} onClick={()=>void action.run()}>Test tactical change</button>
    {action.pending && <Loading label="Comparing tactics"/>}<ErrorBox error={action.error}/>
    {action.result?.variants.map(v=><div key={v.label}><strong>{v.label}</strong>
      {v.error && <p>{v.detail}</p>}
      {v.tracked_from_base?.map(r=><p key={r.entity_id}>{r.item_label ?? r.name} · rank {r.base_rank} → {r.new_rank ?? 'outside tracked depth'} · fit {r.base_score?.toFixed(4)} → {r.new_score?.toFixed(4) ?? 'Unavailable'}</p>)}
    </div>)}</>
}

function CardResults({request, ready, ids, comparison}: {request: object; ready: boolean; ids: string[]; comparison: boolean}) {
  const work = useAction((compare: boolean) => api.post<Result>(base + (compare ? '/compare' : '/recommendations'),
    compare ? {request, card_ids: ids} : request))
  const result = work.result
  const cards = result?.cards ?? []
  const attributes = [...new Set(cards.flatMap(c => Object.keys(c.attributes)))].sort()
  return <div>
    {!comparison && <button className="btn primary" disabled={!ready || work.pending} onClick={() => void work.run(false)}>Rank research cards</button>}
    <button className="btn" disabled={!ready || work.pending || ids.length !== 2} onClick={() => void work.run(true)}>Compare selected versions</button>
    {work.pending && <Loading label="Scoring card evidence" />}<ErrorBox error={work.error} />
    {result?.counts && <p>{result.counts.candidates} items checked · {result.counts.excluded} excluded by eligibility rules · {result.counts.not_evaluable} below the evidence threshold</p>}
    {(result?.ranked ?? result?.players ?? []).map(r => <article key={r.entity_id} className="card tight">
      <strong>{r.name} · {r.card.rarity}</strong> · fit {r.score.toFixed(4)} · coverage {Math.round(r.coverage*100)}%
      <p>{r.explanation.reasons.join('. ')}</p>
      {result?.feedback_receipt && result.request_id && <ItemFeedback key={result.request_id} receipt={result.feedback_receipt}
        requestId={result.request_id} item={r.entity_id}/>}
      <details><summary>Item evidence</summary>
        <p>Item {r.card.source_item_id} · base link {r.card.base_identity_status}</p>
        <p>PlayStyles: {r.card.playstyles?.base.join(', ') || 'Unavailable'} · Plus: {r.card.playstyles?.plus.join(', ') || 'Unavailable'}</p>
        <p>Editorial role fit: {r.card.editorial_role_fit || 'Unavailable'}</p>
        <p>{[...r.explanation.trade_offs, ...r.explanation.unknowns].join('. ')}</p>
      </details></article>)}
    {result?.leading_pair && <LeaderEvidence pair={result.leading_pair} />}
    {result?.pairwise?.map((p,i) => <p key={i}><strong>Why the higher item leads · gap {p.score_gap}</strong> {p.why.join('. ')}
      {p.decision_evidence && <><br /><DecisionRange evidence={p.decision_evidence} /></>}</p>)}
    {cards.length > 0 && <>
      <Stability request={request} cards={cards}/>
      {cards.map(c=><p key={c.entity_id}>{c.name} · {c.source_item_id} · observed positions {c.positions.join('/')}
        {c.position_issues.length > 0 && ' · flagged source positions '+c.position_issues.map(i=>i.value).join(', ')}</p>)}
      {result?.excluded?.map((r,i) => <p key={i}>{r.name} · {r.reason}</p>)}
      {!!result?.outside_observed_position?.length && <p>Selected item outside its observed positions.</p>}
      <div className="scroll-table"><table className="data"><thead><tr><th>Published attribute</th>{cards.map(c=><th key={c.entity_id}>{c.rarity} {c.source_item_id}</th>)}</tr></thead>
        <tbody>{attributes.map(k=><tr key={k}><th scope="row">{k.replace(/_/g,' ')}</th>{cards.map(c=><td key={c.entity_id}>{c.attributes[k] ?? 'Unknown'}</td>)}</tr>)}</tbody>
      </table></div></>}
  </div>
}
