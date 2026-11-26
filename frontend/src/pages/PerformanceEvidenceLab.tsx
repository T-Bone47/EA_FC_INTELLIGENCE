import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, qs } from '../api/client'
import { ErrorBox, Loading } from '../components/common'
import { TACTICS } from '../intelligence/Intelligence'
import { useAction, useApi } from '../lib/useApi'
import { ResearchControl, useRelease } from '../components/Availability'
import { EvidenceBadge } from '../components/Visualizations'
import { useSession } from '../state/session'
import './PerformanceEvidenceLab.css'

const root = '/api/research/fc27/performance'
const optIn = { include_research_data: true }
const metrics = ['goals','assists','shots','shots_on_target','passes_completed','passes_attempted','tackles_won','interceptions','saves','shots_faced']
const label = (value: string) => value.replace(/_/g, ' ').toLowerCase()

type Card = { card_item_id: string; source_item_id: string; name: string; rank: number; cohort: string
  overall: number; primary_position: string; positions: string[]; identity_status: string; reviewed_match_count: number; reviewed_note_count: number }
type Source = { source_key: string; title: string; observation_type: string; source_url: string; access: string; disposition: string }
type Context = { game_patch: string; formation: string; slot: string; position: string; role: string
  tactical_profile: string; game_mode: string; controller: string }
type Entry = { id: string; review_status: string; observation_type: string; source_key: string; source_url: string|null
  source_author: string|null; note: string|null; patch_compatibility: string; age_days: number|null; context: Partial<Context>
  match: { match_date: string; minutes: number|null; metrics: Record<string, number|null> }|null; review_reason?: string|null }
type Dataset = { cards: Card[]; sources: Source[]; manifest: {version:string; top_100:number; position_control:number}
  formations: Record<string, {slot:string;position:string}[]> }
type Detail = { card: Card & { attributes:Record<string, number|null>; snapshot_date:string|null; base_player_id:string|null
  candidate_base_player_id:string; playstyles:{base:string[];plus:string[]}|null; editorial_role_fit:string|null }
  official_ratings_reference:{source_url:string;accessed_on:string;rating:string;primary_position:string}|null
  reviewed_evidence: Entry[]; compatible_match_count: number; disputes: unknown[]
  opinion_groups: {topic:string;status:string;supporting_origins:number;contradicting_origins:number}[]; discovery_queries:string[] }
type Comparison = { predictions: Record<string, {score:number; coverage:number;strengths:{attribute:string}[]}>
  observed:{complete_pairs:number;status:string;observed_per_90:Record<string,number>|null;paired_difference_per_90:number|null}
  direction_agreement:string|null }

export default function PerformanceEvidenceLab() {
  const { gameVersion, setGameVersion, setResearchOptIn } = useSession()
  const { active: enabled, canOptIn, status } = useRelease('ut_card')
  const dataset = useApi<Dataset>(enabled ? root + qs(optIn) : null)
  return <div className="evidence-lab">
    <header className="card evidence-header">
      <span className="badge info">FC27 · Research only</span>
      <h1>Performance Evidence Lab</h1>
      <p className="muted mb0">Compare FC27 card suitability with reviewed match reports in the same tactical context.</p>
    </header>

    {/* Phase 35 Epistemic Honesty & Empirical Evidence Status Banner */}
    <section className="card p1" style={{ border: '1px solid rgba(103, 200, 242, 0.30)', background: 'rgba(103, 200, 242, 0.05)', marginTop: '0.75rem', marginBottom: '0.75rem' }}>
      <div className="row space-between align-center mb03">
        <div className="row align-center gap05">
          <span className="badge sm cyan">Staging Database Status</span>
          <strong style={{ fontSize: '0.88rem' }}>Accepted Live Match Observations: 0 records</strong>
        </div>
        <span className="badge sm outline" style={{ color: 'var(--accent-lime)', borderColor: 'var(--accent-lime)' }}>
          V3.2.1 Deterministic Core Active
        </span>
      </div>
      <p className="tiny text-secondary mb02" style={{ maxWidth: '64ch' }}>
        Evidence Policy: Zero approved live match observations are recorded yet. Tactical suitability weights remain calibrated heuristics until N ≥ 30 paired sessions meet completion, Tactical Defending, Latency (≤ 80ms), and checksum integrity gates.
      </p>
      <div className="row gap05 flex-wrap tiny">
        <span className="badge sm outline">Quality Gate: ≥75 Min Completed</span>
        <span className="badge sm outline">Tactical Defending Forced</span>
        <span className="badge sm outline">Latency Ping ≤ 80ms</span>
        <span className="badge sm outline">SHA-256 Digest Integrity</span>
      </div>
    </section>
    <ResearchControl scope="ut_card" label="Enable local FC27 performance research" />
    {dataset.loading && <Loading label="Loading research cohort" />}
    <ErrorBox error={dataset.error} onRetry={dataset.reload} />
    {dataset.data?.cards.length ? <Workspace dataset={dataset.data} /> : !dataset.loading && !dataset.error && (
      <section className="card">
        <div className="row space-between align-center flex-wrap gap05">
          <div>
            <h2>Gameplay evidence workspace</h2>
            <p className="muted mb0">
              {gameVersion !== 'FC27'
                ? 'Switch to FC27 and enable local card research to inspect the cohort, source ledger and submitted match observations.'
                : canOptIn
                  ? 'Enable local FC27 research to inspect the cohort, source ledger and available observations.'
                  : `FC27 research dataset status: ${status}.`}
            </p>
          </div>
          {gameVersion !== 'FC27' ? (
            <button type="button" className="btn primary sm" onClick={() => setGameVersion('FC27')}>
              Switch to FC27
            </button>
          ) : canOptIn ? (
            <button type="button" className="btn primary sm" onClick={() => setResearchOptIn(true)}>
              Enable local research
            </button>
          ) : null}
        </div>
      </section>
    )}
  </div>
}

function Workspace({dataset}:{dataset:Dataset}) {
  const {user} = useSession()
  const [group, setGroup] = useState('TOP_100')
  const [query, setQuery] = useState('')
  const [chosen, setChosen] = useState(dataset.cards[0].card_item_id)
  const [other, setOther] = useState('')
  const [metric, setMetric] = useState('goals')
  const [context, setContext] = useState<Context>({game_patch:'',formation:'4-3-3',slot:'',position:dataset.cards[0].primary_position,
    role:'',tactical_profile:'BALANCED',game_mode:'',controller:''})
  const card = dataset.cards.find(item=>item.card_item_id===chosen)!
  const opponent = dataset.cards.find(item=>item.card_item_id===other)
  const detail = useApi<Detail>(root + '/items/' + chosen + qs({...optIn,patch:context.game_patch}))
  const filtered = dataset.cards.filter(item=>item.cohort===group &&
    (item.name.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()) || item.source_item_id===query.trim()))
  function select(id: string) {
    const item = dataset.cards.find(row=>row.card_item_id===id)
    if (!item) return
    setChosen(id); setOther(''); setContext({...context,position:item.primary_position,slot:''})
  }
  const comparisonBody = {...optIn,game_version:'FC27',card_ids:[chosen,other],
    context:Object.fromEntries(Object.entries(context).map(([key,value])=>[key,value.trim() || null])),metric}
  return <>
    <div className="overview-detail evidence-overview">
    <div className="card">
      <h2>Research cohort</h2>
      <p>{dataset.manifest.top_100} base-item candidates and {dataset.manifest.position_control} position controls. The archive uses the label Rare. Base-footballer links remain provisional or unresolved.</p>
      <div className="evidence-fields">
        <label>Cohort<select aria-label="Cohort" value={group} onChange={e=>setGroup(e.target.value)}><option value="TOP_100">Top 100</option>
          <option value="POSITION_CONTROL">Position controls</option></select></label>
        <label>Find a card<input value={query} onChange={e=>setQuery(e.target.value)} /></label>
        <label>Research card<select aria-label="Research card" value={filtered.some(row=>row.card_item_id===chosen) ? chosen : ''} onChange={e=>select(e.target.value)}>
          <option value="">Choose a card</option>{filtered.map(row=><option key={row.card_item_id} value={row.card_item_id}>
            {row.rank}. {row.name} · {row.overall} · {row.primary_position} · {row.reviewed_match_count} matches · {row.reviewed_note_count} notes</option>)}</select></label>
      </div>
      {!filtered.length && <p>No cohort members match this search.</p>}
    </div>
    <div className="card">
      <h2>{card.name} · Item {card.source_item_id}</h2>
      <div className="row" style={{ alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
        <span>{card.positions.join(' / ')} · Archived card rating {card.overall} · Base identity:</span>
        <EvidenceBadge status={card.identity_status} label={label(card.identity_status)} />
      </div>
      {detail.loading && <Loading label="Loading player evidence" />}<ErrorBox error={detail.error} />
      {detail.data && <EvidenceDetail data={detail.data} sources={dataset.sources} />}
    </div>
    </div>
    <div className="card">
      <h2>Compare prediction and observation</h2>
      <div className="evidence-fields">
        <label>Formation<select value={context.formation} onChange={e=>setContext({...context,formation:e.target.value,slot:''})}>
          {Object.keys(dataset.formations).map(value=><option key={value}>{value}</option>)}</select></label>
        <label>Formation slot<select aria-label="Formation slot" value={context.slot} onChange={e=>{
          const slot = dataset.formations[context.formation].find(row=>row.slot===e.target.value)
          setOther(''); setContext({...context,slot:slot?.slot??'',position:slot?.position??card.primary_position})
        }}><option value="">Generic position</option>{dataset.formations[context.formation].filter(slot=>card.positions.includes(slot.position))
          .map(slot=><option key={slot.slot}>{slot.slot}</option>)}</select></label>
        <label>Position<select disabled={!!context.slot} value={context.position} onChange={e=>{
          setOther('');setContext({...context,position:e.target.value})
        }}>{card.positions.map(value=><option key={value}>{value}</option>)}</select></label>
        <label>Tactical profile<select value={context.tactical_profile} onChange={e=>setContext({...context,tactical_profile:e.target.value})}>
          {TACTICS.map(value=><option key={value}>{value}</option>)}</select></label>
        <label>Game patch<input value={context.game_patch} placeholder="1.2.0" onChange={e=>setContext({...context,game_patch:e.target.value})} /></label>
        <label>Assigned role<input value={context.role} onChange={e=>setContext({...context,role:e.target.value})} /></label>
        <label>Game mode<input value={context.game_mode} onChange={e=>setContext({...context,game_mode:e.target.value})} /></label>
        <label>Controller<select value={context.controller} onChange={e=>setContext({...context,controller:e.target.value})}>
          <option value="">Unknown</option><option value="HUMAN">Human</option><option value="AI">AI</option><option value="MIXED">Mixed</option>
        </select></label>
        <label>Outcome metric<select value={metric} onChange={e=>setMetric(e.target.value)}>
          {metrics.map(value=><option key={value} value={value}>{label(value)}</option>)}</select></label>
        <label>Second card<select aria-label="Second card" value={other} onChange={e=>setOther(e.target.value)}><option value="">Choose a comparable card</option>
          {dataset.cards.filter(item=>item.card_item_id!==chosen && item.positions.includes(context.position)).map(item=>
            <option key={item.card_item_id} value={item.card_item_id}>{item.name} · {item.source_item_id}</option>)}</select></label>
      </div>
      {opponent && <Compare key={JSON.stringify(comparisonBody)} body={comparisonBody} cards={[card,opponent]} />}
    </div>
    <details className="card"><summary>Research source registry</summary><ul>
      {dataset.sources.map(source=><li key={source.source_key}>
        {source.source_url ? <a href={source.source_url} rel="noreferrer" target="_blank">{source.title}</a> : source.title}
        {' · '}{source.disposition}</li>)}
    </ul></details>
    {user ? <Intake key={JSON.stringify([user.id, chosen, context])} card={card} context={comparisonBody.context}
      sources={dataset.sources} isAdmin={user.role==='admin'} updated={detail.reload} />
      : <p><Link to="/login">Sign in</Link> to record a match or cite a review.</p>}
  </>
}

function EvidenceDetail({data,sources}:{data:Detail;sources:Source[]}) {
  return <>
    <p>{data.compatible_match_count ? data.compatible_match_count + ' reviewed matches in this patch filter.' : 'Insufficient gameplay evidence'}</p>
    {data.disputes.length>0 && <p>{data.disputes.length} disputed match records excluded from aggregation.</p>}
    {data.official_ratings_reference && <p>EA ratings cross-check · {data.official_ratings_reference.rating} OVR · {data.official_ratings_reference.primary_position} ·
      {' '}<a href={data.official_ratings_reference.source_url} rel="noreferrer" target="_blank">Ratings page checked {data.official_ratings_reference.accessed_on}</a></p>}
    <details><summary>Archived attributes, PlayStyles and roles</summary>
      <p>Card snapshot date {data.card.snapshot_date??'unavailable'} · Confirmed base ID {data.card.base_player_id??'unavailable'} · Candidate ratings ID {data.card.candidate_base_player_id}</p>
      <p>PlayStyles {data.card.playstyles?.base.join(', ')||'unavailable'}. PlayStyles+ {data.card.playstyles?.plus.join(', ')||'unavailable'}.</p>
      <p>Editorial role fit {data.card.editorial_role_fit??'unavailable'}. Official item roles unavailable.</p>
      <dl className="evidence-attributes">{Object.entries(data.card.attributes).map(([key,value])=>
        <div key={key}><dt>{label(key)}</dt><dd>{value??'Unavailable'}</dd></div>)}</dl>
    </details>
    {data.opinion_groups.map((group,index)=><p key={index}>{label(group.topic)} · {label(group.status)} · {group.supporting_origins} supporting and {group.contradicting_origins} opposing source families</p>)}
    {data.reviewed_evidence.map(entry=><article key={entry.id}>
      <h3>{label(entry.observation_type)}</h3>
      <p>{entry.source_url ? <a href={entry.source_url} target="_blank" rel="noreferrer">{entry.source_author??sources.find(x=>x.source_key===entry.source_key)?.title??'Source'}</a> :
        sources.find(x=>x.source_key===entry.source_key)?.title} · {label(entry.patch_compatibility)} · {entry.age_days??'Unknown'} days since source or match</p>
      <p>{[entry.context.game_patch,entry.context.formation,entry.context.position,entry.context.role,entry.context.tactical_profile].filter(Boolean).join(' · ')}</p>
      {entry.note && <p>{entry.note}</p>}
      {entry.match && <p>{entry.match.match_date} · {entry.match.minutes??'Unknown'} minutes · {Object.entries(entry.match.metrics)
        .map(([key,value])=>label(key)+' '+(value??'unavailable')).join(', ')||'No metrics reported'}</p>}
    </article>)}
    <details><summary>Discovery queries for this card</summary><ul>{data.discovery_queries.map(query=><li key={query}>{query}</li>)}</ul></details>
  </>
}

function Compare({body,cards}:{body:object;cards:Card[]}) {
  const compare = useAction(()=>api.post<Comparison>(root+'/compare',body))
  const result = compare.result
  return <>
    <button className="btn primary" onClick={()=>void compare.run()} disabled={compare.pending}>Run comparison</button>
    <ErrorBox error={compare.error} />
    {result && <div aria-live="polite">
      <p>V3.2 uses the position, selected formation slot, and tactic. The selected patch, role, mode, and controller filter match evidence.</p>
      <table className="data"><thead><tr><th scope="col">Card</th><th scope="col">V3.2 fit</th><th scope="col">Observed per 90</th></tr></thead>
        <tbody>{cards.map(card=>{
          const prediction=result.predictions[card.card_item_id]
          return <tr key={card.card_item_id}><th scope="row">{card.name}</th>
            <td>{prediction ? <>{prediction.score.toFixed(3)}<small> · {prediction.strengths.slice(0,2).map(x=>label(x.attribute)).join(', ')}</small></> : 'Unavailable'}</td>
            <td>{result.observed.observed_per_90?.[card.card_item_id]??'Unavailable'}</td></tr>
        })}</tbody></table>
      <p>{result.observed.status==='INSUFFICIENT_GAMEPLAY_EVIDENCE' ? 'Insufficient gameplay evidence' :
        'Descriptive difference per 90 '+result.observed.paired_difference_per_90} · {result.observed.complete_pairs} complete pairs</p>
      {result.direction_agreement && <p>{label(result.direction_agreement)} in the reviewed matches.</p>}
    </div>}
  </>
}

function Intake({card, context, sources, isAdmin, updated}:{card:Card;context:Record<string,string|null>;sources:Source[];isAdmin:boolean;updated:()=>void}) {
  const [sourceKey, setSource] = useState('volunteer')
  const [batch, setBatch] = useState('')
  const [reason,setReason] = useState('')
  const mine = useApi<{items:Entry[]}>(root+'/submissions'+qs(optIn))
  const queue = useApi<{items:Entry[]}>(isAdmin ? root+'/review'+qs(optIn) : null)
  const refresh = () => { mine.reload();queue.reload();updated() }
  const intake = useAction((records:unknown[])=>api.post<{ids:string[]}>(root+'/submissions',{...optIn,records}))
  const feedback = useAction((id:string, decision:string)=>api.post(root+'/review/'+id,
    {...optIn,decision,reason:decision==='WITHDRAWN'?'Withdrawn by submitter':reason}))
  const [importError,setImportError] = useState('')
  const source = sources.find(row=>row.source_key===sourceKey)!
  const isMatch = source.access==='PERMITTED_SUBMISSION'
  const availableSources = sources.filter(row=>row.source_key!=='controlled' &&
    (['volunteer','community','creator','ea-forums','futgg','fctactics','unverified'].includes(row.source_key) ||
      isAdmin && (row.source_key==='owner' || row.access==='REFERENCE_ONLY' && row.observation_type.startsWith('OFFICIAL'))))
  return <div className="card">
    <h2>Submit evidence</h2>
    <p>The selected card and tactical context apply to this report. Check the patch and role before saving.</p>
    <label>Intake source<select value={sourceKey} onChange={e=>setSource(e.target.value)}>
      {availableSources.map(row=><option key={row.source_key} value={row.source_key}>{row.title}</option>)}</select></label>
    <form key={sourceKey} onSubmit={async e=>{
      e.preventDefault()
      const input = new FormData(e.currentTarget)
      const value = (key:string)=>String(input.get(key)??'').trim()||null
      const count = (key:string)=>value(key)===null?null:Number(value(key))
      const match = isMatch ? { match_date:value('match_date'),match_key:value('match_key'),minutes:count('minutes'),
        platform:value('platform'),opponent_context:value('opponent'),skill_context:value('skill'),
        metrics:Object.fromEntries(metrics.map(key=>[key,count(key)])) } : null
      if (await intake.run([{game_version:'FC27',card_item_id:card.card_item_id,observation_type:source.observation_type,
        source_key:source.source_key,source_url:value('url'),source_date:value('source_date'),source_author:value('author'),
        evidence_locator:value('locator'),context,topic:value('topic'),stance:value('stance'),note:value('note'),match,
        rights_attested:input.has('rights'),share_for_research:input.has('share')}])) refresh()
    }}>
      <div className="evidence-fields">
        {isMatch ? <>
          <label>Match date<input name="match_date" type="date" required /></label>
          <label>Match key<input name="match_key" required placeholder="match-001" /></label>
          <label>Minutes played<input name="minutes" type="number" min="1" max="120" /></label>
          <label>Platform<input name="platform" /></label>
          <label>Opponent context<input name="opponent" placeholder="Difficulty or anonymized bracket" /></label>
          <label>Skill context<input name="skill" placeholder="Division or difficulty" /></label>
          {metrics.map(key=><label key={key}>{label(key)}<input name={key} type="number" min="0" max="1000" /></label>)}
        </> : <>
          <label>Original permalink<input name="url" type="url" required defaultValue={source.source_url} /></label>
          <label>Source date<input name="source_date" type="date" /></label>
          <label>Original author<input name="author" required={['CREATOR_OBSERVATION','COMMUNITY_OPINION'].includes(source.observation_type)} /></label>
          <label>Claim topic<input name="topic" required placeholder="high-press-recovery" /></label>
          <label>Claim stance<select name="stance"><option value="">Unspecified</option><option value="SUPPORTS">Supports</option><option value="CONTRADICTS">Contradicts</option></select></label>
        </>}
        <label>Evidence locator<input name="locator" placeholder="Timestamp or local report reference" /></label>
        <label>{isMatch?'Match notes':'Paraphrase in your own words'}<textarea name="note" maxLength={1000} required={!isMatch} /></label>
      </div>
      <p><label><input name="rights" type="checkbox" required /> I recorded this match or have permission to submit it. Any cited notes are in my own words.</label></p>
      <p><label><input name="share" type="checkbox" /> Share with local research after approval</label></p>
      <button className="btn primary" disabled={intake.pending}>Submit report</button>
    </form>
    <details><summary>Import structured reports or controlled comparisons</summary>
      <p>Paste an array of up to 50 structured evidence records. Controlled experiments use two independent counterbalanced sessions with explicit protocol, block and setup keys.</p>
      <label>Evidence JSON<textarea value={batch} onChange={e=>setBatch(e.target.value)} rows={6} /></label>
      <button className="btn" disabled={intake.pending} onClick={async()=>{
        setImportError('')
        try {
          const records:unknown=JSON.parse(batch)
          if (!Array.isArray(records)) throw new Error('Expected an array of evidence records.')
          if (await intake.run(records)) refresh()
        } catch (error) { setImportError(error instanceof Error?error.message:'Invalid evidence JSON') }
      }}>Import reports</button>
      {importError && <p role="alert">{importError}</p>}
    </details>
    <ErrorBox error={intake.error} />
    {intake.result && <p role="status">{intake.result.ids.length} report(s) saved.</p>}
    <h3>My submissions</h3>
    <ErrorBox error={mine.error} />
    {mine.data?.items.map(entry=><p key={entry.id}>{label(entry.observation_type)} · {label(entry.review_status)} {entry.review_reason}
      {entry.review_status!=='WITHDRAWN' && <button className="btn" disabled={feedback.pending} onClick={async()=>{
        if(await feedback.run(entry.id,'WITHDRAWN')) refresh()
      }}>Withdraw report</button>}</p>)}
    {isAdmin && <><h3>Review shared submissions</h3><ErrorBox error={queue.error} />
      <label>Decision reason<input value={reason} onChange={e=>setReason(e.target.value)} maxLength={500} /></label>
      {queue.data?.items.map(entry=><details key={entry.id}><summary>{label(entry.observation_type)} · {entry.id}</summary>
        <pre className="evidence-review">{JSON.stringify((entry as Entry & {payload:unknown}).payload,null,2)}</pre>
        {['ACCEPTED','REJECTED'].map(decision=><button className="btn" key={decision} disabled={!reason.trim()||feedback.pending} onClick={async()=>{
          if(await feedback.run(entry.id,decision)) refresh()
        }}>{decision==='ACCEPTED'?'Accept evidence':'Reject evidence'}</button>)}</details>)}</>}
    <ErrorBox error={feedback.error} />
  </div>
}
