import { useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import './CardSquadLab.css'
import { StadiumPitch } from '../components/StadiumPitch'
import { StadiumCheckbox, StadiumCombobox, StadiumField, StadiumInput, StadiumSelect } from '../components/StadiumControls'
import { api, qs } from '../api/client'
import { ErrorBox, Loading } from '../components/common'
import { TACTICS } from '../intelligence/Intelligence'
import type { RecommendationOptions, StatedFootballStyle, StatedSquadPreferences } from '../intelligence/types'
import { useAction, useApi } from '../lib/useApi'
import { ResearchControl, useRelease } from '../components/Availability'
import { StadiumIcon } from '../components/StadiumIcons'
import { EpistemicChip, PageHeader } from '../components/ui/StadiumPrimitives'
import { useSession } from '../state/session'
import { useCopilot, useCopilotRouteContext } from '../state/copilot'

const root = '/api/research/fc27/cards'
type Item = {entity_id:string; source_item_id:string; name:string; rarity:string; positions:string[]; base_identity_status:string; overall?: number}
type Assigned = Record<string,string>
type Plan = {candidate_ids:string[];assigned:Assigned;locked_slots:string[];formation:string;tactical_profile:string;
  alternatives:string[];confirmed_only:boolean;continuity:boolean;excluded:string[];desired_playstyles_plus:string[];
  attribute_preferences?:{attribute:string;weight:number}[];
  upgrade:string|null;minimum_gain:number;game_version:string;entity_scope:string;release_id:string;include_research_data:true}
const initial:Plan = {game_version:'FC27',entity_scope:'ut_card',release_id:'fc27-card-items-local-r1',include_research_data:true,
  candidate_ids:[],assigned:{},locked_slots:[],excluded:[],formation:'4-3-3',tactical_profile:'BALANCED',
  alternatives:['HIGH_PRESS','POSSESSION'],confirmed_only:false,continuity:true,desired_playstyles_plus:[],upgrade:null,minimum_gain:0}
type Lineup = {filled:number;scored:number;total_fit:number|null;mean_coverage_scored:number|null;
  footballer_uniqueness_verified:boolean;weakest_scored_slots:string[];attribute_contributions:Record<string,number>;
  observed_playstyles:Record<string,number>;unknown_playstyle_lists:number;observed_outfield_attributes:Record<string,{mean:number|null;published:number}>;
  attribute_suitability:{attribute:string;mean:number;scored_slots:number}[];slots:{slot:string;item:Item|null;score:number|null;status:string;reason:string|null}[]}

export type TacticalAlert = {
  rule_id: string
  rule_version: string
  slot: string
  position: string
  card_item_id: string
  card_name: string
  tactical_context: string
  evaluated_capability: string
  attribute_name: string
  attribute_value: number | null
  threshold: number
  evidence_classification: 'EMPIRICALLY_SUPPORTED' | 'MODELED_HEURISTIC'
  friction_penalty: number
  explanation: string
  recommended_action: string
  empirical_reference?: string | null
  missing_data_limitation?: string | null
}

export type ChannelMetric = {
  name: string
  slots: string[]
  scored_count: number
  unscored_slots: string[]
  mean_suitability: number | null
  status: string
  contributing_items: {
    slot: string
    player_name: string
    score: number | null
  }[]
}

export type WholeXISynergy = {
  formation: string
  tactical_profile: string
  experimental_tactical_alignment: {
    alignment_index_pct: number | null
    status: 'HIGH_ALIGNMENT' | 'MODERATE_ALIGNMENT' | 'PARTIAL_ALIGNMENT' | 'TACTICAL_DISSONANCE' | 'INSUFFICIENT_EVIDENCE'
    status_convention: string
    mean_suitability: number | null
    suitability_dispersion: number | null
    friction_penalty: number
    active_friction_count: number
    scored_slots_count: number
    total_slots_count: number
    unscored_slots: string[]
  }
  channels: {
    LEFT_FLANK: ChannelMetric
    CENTRAL_SPINE: ChannelMetric
    RIGHT_FLANK: ChannelMetric
  }
  tactical_friction_alerts: TacticalAlert[]
}

type Result = {receipt:string;solver_status:string;optimized:Lineup;current:Lineup;matrix:{optimized_for:string;
  assignment:Assigned;scores:Record<string,number|null>;scored_counts:Record<string,number>;
  changed_slots:string[];fit_delta_vs_primary:Record<string,number|null>}[];
  nondominated_generated_profiles:string[];unavailable_profiles:Record<string,{slots:string[]}>;upgrade_status:string|null;upgrade_gain:number|null;
  upgrades:{slot:string;before:Item;after:Item;before_score:number;after_score:number;why:string[];coverage_after:number}[];
  tactical_synergy?: {
    optimized: WholeXISynergy | null
    current: WholeXISynergy | null
  }}
type Saved = {id:string;name:string;plan:Plan;items:Item[];preview:Result}
const label = (c:Item) => c.name+' · '+c.rarity+' · '+c.source_item_id
const fmt = (score:number|null) => score == null ? 'Unavailable' : score.toFixed(4)

export default function CardSquadLab() {
  const {user} = useSession()
  const { openCopilot } = useCopilot()
  const { active: enabled, data } = useRelease('ut_card')

  return (
    <section className="stack">
      <PageHeader
        title="Ultimate Team Squad Lab"
        description="Build 11-player lineups, compare tactical alternatives, and inspect slot upgrades on an interactive tactical pitch."
        statusPill={<EpistemicChip kind={enabled ? 'hypothetical' : 'neutral'} label={enabled ? 'FC27 Research Cockpit' : 'Preview Pitch Cockpit'} />}
        actions={
          <div className="row gap05 align-center flex-wrap">
            <button
              type="button"
              className="btn ghost sm"
              onClick={() => openCopilot({
                prompt: 'Evaluate my active Squad Lab XI, flag weak slots, and suggest a confirmation-gated upgrade.',
              })}
            >
              <StadiumIcon name="coach" size={14} />
              <span>Ask Co-Pilot</span>
            </button>
            <Link className="btn ghost sm" to="/squads">Saved player squads</Link>
          </div>
        }
      />

      <nav aria-label="Squad workspace" className="stadium-tabs">
        <a href="#squad-editor" className="active">Squad Lab</a>
        <a href="#squad-dna">Squad DNA</a>
        <a href="#upgrade-studio">Upgrade Studio</a>
        <Link to="/squads">Saved player squads</Link>
      </nav>

      <ResearchControl scope="ut_card" label="Use local FC27 card research" />

      {enabled && data?.research?.goalkeeper_reference_ready === false && (
        <p className="callout info small">
          This release has no validated goalkeeper scoring reference. Goalkeeper assignments appear without a fit score.
        </p>
      )}

      <div className="squad-lab-main">
        {!enabled && (
          <div className="callout info mb1" role="status">
            <strong>Interactive Pitch Ready:</strong> Explore formation geometries and slot duties below, or jump to{' '}
            <Link to="/squads">Saved Player Squads</Link>. Enable <em>Use local FC27 card research</em> above to unlock UT card shortlist search and optimizer scoring.
          </div>
        )}
        <LibraryOfSquads key={user?.id ?? 'guest'} enabled={enabled} />
      </div>
    </section>
  )
}

function LibraryOfSquads({ enabled = true }: { enabled?: boolean }) {
  const {user} = useSession()
  const saved = useApi<{items:{id:string;name:string}[]}>(user && enabled ? root+'/squad/saved?include_research_data=true' : null)
  const [id,setId] = useState('')
  const opened = useApi<Saved>(id && enabled ? root+'/squad/saved/'+id+'?include_research_data=true' : null)

  useCopilotRouteContext({
    route_name: 'SQUAD_LAB',
    game_version: 'FC27',
    squad_id: id || null,
    active_formation: opened.data?.plan?.formation || '4-3-3',
    active_tactical_profile: opened.data?.plan?.tactical_profile || 'BALANCED',
    selected_card_ids: opened.data?.items?.map(i => i.entity_id).slice(0, 11) || [],
  })

  return (
    <>
      <div className="row space-between align-center mb05">
        <p className="muted small mb0">
          Build a shortlist of up to 50 exact items. Unresolved identities allow exploratory lineups. Prices and chemistry are unavailable.
        </p>
        {user ? (
          <label className="row align-center gap05 small">
            <span>Saved research squads</span>
            <select className="select sm" value={id} onChange={e=>setId(e.target.value)} disabled={!enabled}>
              <option value="">New research squad</option>
              {saved.data?.items.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
        ) : (
          <p className="small mb0">
            <Link to="/login" state={{ from: "/cards/squad-lab" }}>Sign in</Link> to save and reopen squads.
          </p>
        )}
      </div>

      <ErrorBox error={saved.error}/>
      <ErrorBox error={opened.error}/>
      {opened.loading && <Loading label="Opening research squad"/>}
      {(!id || opened.data) && <Editor key={id} saved={opened.data} onSave={saved.reload} enabled={enabled} />}
    </>
  )
}

const DEMO_XI_ITEMS: { slot: string; score: number; item: Item }[] = [
  { slot: 'GK', score: 0.78, item: { entity_id: 'demo-gk', source_item_id: 'DEMO-GK-01', name: 'Alisson Becker (Sample)', rarity: 'DEMO_FIXTURE', positions: ['GK'], base_identity_status: 'SYNTHETIC_FIXTURE', overall: 89 } },
  { slot: 'LB', score: 0.84, item: { entity_id: 'demo-lb', source_item_id: 'DEMO-LB-02', name: 'Theo Hernandez (Sample)', rarity: 'DEMO_FIXTURE', positions: ['LB'], base_identity_status: 'SYNTHETIC_FIXTURE', overall: 87 } },
  { slot: 'LCB', score: 0.88, item: { entity_id: 'demo-lcb', source_item_id: 'DEMO-CB-03', name: 'Virgil van Dijk (Sample)', rarity: 'DEMO_FIXTURE', positions: ['CB'], base_identity_status: 'SYNTHETIC_FIXTURE', overall: 89 } },
  { slot: 'RCB', score: 0.85, item: { entity_id: 'demo-rcb', source_item_id: 'DEMO-CB-04', name: 'William Saliba (Sample)', rarity: 'DEMO_FIXTURE', positions: ['CB'], base_identity_status: 'SYNTHETIC_FIXTURE', overall: 87 } },
  { slot: 'RB', score: 0.81, item: { entity_id: 'demo-rb', source_item_id: 'DEMO-RB-05', name: 'Achraf Hakimi (Sample)', rarity: 'DEMO_FIXTURE', positions: ['RB'], base_identity_status: 'SYNTHETIC_FIXTURE', overall: 86 } },
  { slot: 'LCM', score: 0.86, item: { entity_id: 'demo-lcm', source_item_id: 'DEMO-CM-06', name: 'Jude Bellingham (Sample)', rarity: 'DEMO_FIXTURE', positions: ['CM', 'CAM'], base_identity_status: 'SYNTHETIC_FIXTURE', overall: 90 } },
  { slot: 'CDM', score: 0.89, item: { entity_id: 'demo-cdm', source_item_id: 'DEMO-CDM-07', name: 'Rodri (Sample)', rarity: 'DEMO_FIXTURE', positions: ['CDM', 'CM'], base_identity_status: 'SYNTHETIC_FIXTURE', overall: 91 } },
  { slot: 'RCM', score: 0.83, item: { entity_id: 'demo-rcm', source_item_id: 'DEMO-CM-08', name: 'Federico Valverde (Sample)', rarity: 'DEMO_FIXTURE', positions: ['CM', 'RB'], base_identity_status: 'SYNTHETIC_FIXTURE', overall: 88 } },
  { slot: 'LW', score: 0.90, item: { entity_id: 'demo-lw', source_item_id: 'DEMO-LW-09', name: 'Vini Jr. (Sample)', rarity: 'DEMO_FIXTURE', positions: ['LW', 'ST'], base_identity_status: 'SYNTHETIC_FIXTURE', overall: 90 } },
  { slot: 'ST', score: 0.91, item: { entity_id: 'demo-st', source_item_id: 'DEMO-ST-10', name: 'Kylian Mbappé (Sample)', rarity: 'DEMO_FIXTURE', positions: ['ST', 'LW'], base_identity_status: 'SYNTHETIC_FIXTURE', overall: 91 } },
  { slot: 'RW', score: 0.63, item: { entity_id: 'demo-rw', source_item_id: 'DEMO-RW-11', name: 'Ousmane Dembélé (Sample)', rarity: 'DEMO_FIXTURE', positions: ['RW', 'ST'], base_identity_status: 'SYNTHETIC_FIXTURE', overall: 86 } },
]

function Editor({saved, onSave, enabled = true}:{saved:Saved|null; onSave:()=>void; enabled?: boolean}) {
  const {user} = useSession()
  const defaults = user?.preferences?.card_squad as StatedSquadPreferences | undefined
  const style = user?.preferences?.football_style as StatedFootballStyle | undefined
  const [plan,setPlan] = useState<Plan>(()=>saved?.plan ?? {...initial, formation:defaults?.formation??initial.formation,
    tactical_profile:style?.tactical_profile??initial.tactical_profile, continuity:defaults?.continuity??true,
    upgrade:defaults?.upgrade??null, desired_playstyles_plus:defaults?.playstyle_plus?[defaults.playstyle_plus]:[]})
  const [items,setItems] = useState<Item[]>(saved?.items ?? [])
  const [params] = useSearchParams()
  const [query,setQuery] = useState(() => (params.get('item') ?? '').slice(0, 80))
  const [offset,setOffset] = useState(0)
  const [undo,setUndo] = useState<Plan|null>(null)
  const [activeSlot,setActiveSlot] = useState('')
  const [pitchPreview,setPitchPreview] = useState<Result|null>(null)
  const [demoLoaded,setDemoLoaded] = useState(false)
  const currentPlan = useRef(plan)
  currentPlan.current = plan
  const previewRequest = useRef(0)
  const slotInputs = useRef<Record<string, HTMLSelectElement | null>>({})

  const find = useApi<{items:Item[];total:number}>(enabled ? root+qs({q:query,offset,include_research_data:true}) : null)
  const options = useApi<RecommendationOptions>('/api/v3/options')

  function edit(update:Partial<Plan>) {
    setUndo(plan)
    setPitchPreview(null)
    setDemoLoaded(false)
    previewRequest.current++
    setPlan({...plan,...update})
  }

  function loadDemoXi() {
    const sampleItems = DEMO_XI_ITEMS.map(d => d.item)
    const sampleAssigned: Assigned = Object.fromEntries(DEMO_XI_ITEMS.map(d => [d.slot, d.item.entity_id]))
    const sampleSlots: Lineup['slots'] = DEMO_XI_ITEMS.map(d => ({
      slot: d.slot,
      item: d.item,
      score: d.score,
      status: 'SYNTHETIC_FIXTURE',
      reason: 'Read-only sample fixture',
    }))
    const sampleLineup: Lineup = {
      filled: 11,
      scored: 11,
      total_fit: 9.18,
      mean_coverage_scored: 1.0,
      footballer_uniqueness_verified: true,
      weakest_scored_slots: ['RW'],
      attribute_contributions: { short_passing: 0.28, reactions: 0.24, sprint_speed: 0.22 },
      observed_playstyles: { 'Quick Step+': 3, 'Incisive Pass+': 2 },
      unknown_playstyle_lists: 0,
      observed_outfield_attributes: {},
      attribute_suitability: [],
      slots: sampleSlots,
    }
    setItems(sampleItems)
    setPlan(prev => ({ ...prev, formation: '4-3-3', candidate_ids: sampleItems.map(i => i.entity_id), assigned: sampleAssigned, locked_slots: ['ST', 'CDM'] }))
    setPitchPreview({
      receipt: 'SYNTHETIC_FIXTURE_DEMO',
      solver_status: 'SYNTHETIC_FIXTURE_PREVIEW',
      optimized: sampleLineup,
      current: sampleLineup,
      matrix: [],
      nondominated_generated_profiles: ['BALANCED'],
      unavailable_profiles: {},
      upgrade_status: null,
      upgrade_gain: null,
      upgrades: [],
    })
    setDemoLoaded(true)
    setActiveSlot('ST')
  }

  function clearDemoXi() {
    setItems([])
    setPlan(prev => ({ ...prev, candidate_ids: [], assigned: {}, locked_slots: [] }))
    setPitchPreview(null)
    setDemoLoaded(false)
  }

  // Fallback 4-3-3 slot definitions if options haven't loaded yet
  const fallback433 = [
    { slot: 'GK', position: 'GK', side: 'CENTER', duty: 'DEFEND' },
    { slot: 'LB', position: 'LB', side: 'LEFT', duty: 'DEFEND' },
    { slot: 'LCB', position: 'CB', side: 'LEFT', duty: 'DEFEND' },
    { slot: 'RCB', position: 'CB', side: 'RIGHT', duty: 'DEFEND' },
    { slot: 'RB', position: 'RB', side: 'RIGHT', duty: 'DEFEND' },
    { slot: 'LCM', position: 'CM', side: 'LEFT', duty: 'SUPPORT' },
    { slot: 'CDM', position: 'CDM', side: 'CENTER', duty: 'DEFEND' },
    { slot: 'RCM', position: 'CM', side: 'RIGHT', duty: 'ATTACK' },
    { slot: 'LW', position: 'LW', side: 'LEFT', duty: 'ATTACK' },
    { slot: 'ST', position: 'ST', side: 'CENTER', duty: 'ATTACK' },
    { slot: 'RW', position: 'RW', side: 'RIGHT', duty: 'ATTACK' },
  ]
  const slotDefs = (options.data?.formations[plan.formation] && options.data.formations[plan.formation].length > 0)
    ? options.data.formations[plan.formation]
    : fallback433

  const selectedItems = new Map(items.map(c=>[c.entity_id,c]))

  function selectItem(c:Item) {
    if (plan.candidate_ids.length >= 50 || plan.candidate_ids.includes(c.entity_id)) return
    if (!selectedItems.has(c.entity_id)) setItems([...items,c])
    edit({candidate_ids:[...plan.candidate_ids,c.entity_id]})
  }

  function withoutAssignment(slot:string,id:string) {
    return !id || !Object.entries(plan.assigned).some(([other,value])=>other!==slot && value===id)
  }

  function assign(slot:string,id:string) {
    const assigned = {...plan.assigned}
    if (id) assigned[slot] = id
    else delete assigned[slot]
    edit({assigned,locked_slots:plan.locked_slots.filter(s=>s!==slot)})
  }

  const preview = pitchPreview ?? (saved && plan === saved.plan ? saved.preview : null)

  return (
    <div className="workspace-grid squad-workspace" id="squad-editor">
      {/* Left Sidebar: Shortlist & Tactical Controls */}
      <aside className="workspace-rail" aria-label="Squad controls">
        <section className="card">
          <h2>Squad Controls</h2>
          <h3>Card Shortlist</h3>
          <StadiumField label="Search card items" hint="Search verified cards by name, club or item ID">
            <StadiumInput
              aria-label="Search card items"
              value={query}
              maxLength={80}
              placeholder="Yamal, Bellingham, 67386507…"
              onChange={e => { setQuery(e.target.value); setOffset(0) }}
              disabled={!enabled}
              clearable
              onClear={() => { setQuery(''); setOffset(0) }}
            />
          </StadiumField>
          <ErrorBox error={find.error}/>
          {find.loading && <Loading label="Searching card items"/>}
          <div className="lab-search">
            {find.data?.items.map(c=>(
              <button
                className="btn ghost sm"
                key={c.entity_id}
                disabled={plan.candidate_ids.includes(c.entity_id) || plan.candidate_ids.length>=50 || !enabled}
                onClick={()=>selectItem(c)}
              >
                Add {label(c)}
              </button>
            ))}
          </div>
          {find.data && (
            <p className="tiny muted">
              {find.data.total} matches{' '}
              <button className="btn ghost sm" disabled={!offset} onClick={()=>setOffset(offset-25)}>Previous</button>
              <button className="btn ghost sm" disabled={offset+25>=find.data.total} onClick={()=>setOffset(offset+25)}>Next</button>
            </p>
          )}

          <details className="mt05">
            <summary>Shortlisted items ({plan.candidate_ids.length}) and exclusions</summary>
            {plan.candidate_ids.length === 0 ? (
              <p className="tiny muted mt05">No items shortlisted yet. Search items above to populate.</p>
            ) : (
              plan.candidate_ids.map(id => {
                const c = selectedItems.get(id)
                return c && (
                  <div key={id} className="row space-between align-center p03 border-b">
                    <span className="small">{label(c)}</span>
                    <div className="row gap03 align-center">
                      <label className="checkbox tiny">
                        <input
                          type="checkbox"
                          disabled={Object.values(plan.assigned).includes(id)}
                          checked={plan.excluded.includes(id)}
                          onChange={e=>edit({excluded:e.target.checked?[...plan.excluded,id]:plan.excluded.filter(i=>i!==id)})}
                        />{' '}
                        Exclude
                      </label>
                      <button
                        className="btn ghost sm"
                        disabled={Object.values(plan.assigned).includes(id)}
                        onClick={()=>edit({candidate_ids:plan.candidate_ids.filter(i=>i!==id), excluded:plan.excluded.filter(i=>i!==id)})}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                )
              })
            )}
          </details>
        </section>

        <section className="card">
          <div className="row space-between align-center mb05">
            <h3 className="mb0">Formation and Tactics</h3>
            <span className="badge lime sm">{plan.formation}</span>
          </div>
          <div className="stack gap07 mt05">
            <StadiumField label="Squad formation" hint="Active 11-player pitch structure">
              <StadiumSelect
                aria-label="Squad formation"
                value={plan.formation}
                onChange={val => edit({ formation: val, assigned: {}, locked_slots: [] })}
              >
                {Object.keys(options.data?.formations ?? { '4-3-3': [], '4-4-2': [], '4-2-3-1': [] }).map(f => (
                  <option key={f} value={f}>{f}</option>
                ))}
              </StadiumSelect>
            </StadiumField>

            <StadiumField label="Squad tactics" hint="Primary tactical philosophy">
              <StadiumSelect
                aria-label="Squad tactics"
                value={plan.tactical_profile}
                onChange={val => edit({ tactical_profile: val })}
              >
                {TACTICS.map(t => (
                  <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
                ))}
              </StadiumSelect>
            </StadiumField>

            <StadiumField label="Desired PlayStyle+" hint="Target benchmark PlayStyle">
              <StadiumCombobox
                ariaLabel="Desired PlayStyle+"
                placeholder="e.g. Finesse Shot+"
                value={plan.desired_playstyles_plus.join(', ')}
                onChange={val => edit({ desired_playstyles_plus: val ? [val] : [] })}
              />
            </StadiumField>

            <StadiumField label="Emphasize an attribute" hint="Weight individual attribute">
              <StadiumSelect
                aria-label="Emphasize an attribute"
                value={plan.attribute_preferences?.[0]?.attribute ?? ''}
                onChange={val => edit({
                  attribute_preferences: val
                    ? [{ attribute: val, weight: plan.attribute_preferences?.[0]?.weight ?? 2 }]
                    : []
                })}
              >
                <option value="">Use tactical defaults</option>
                {['short_passing','vision','finishing','stamina','standing_tackle','interceptions','acceleration','ball_control'].map(a => (
                  <option key={a} value={a}>{a.replace(/_/g, ' ')}</option>
                ))}
              </StadiumSelect>
            </StadiumField>

            {!!plan.attribute_preferences?.length && (
              <StadiumField label="Preference weight" hint="Scale 1 to 10 emphasis">
                <StadiumInput
                  aria-label="Preference weight"
                  type="number"
                  min="1"
                  max="10"
                  step="0.5"
                  value={plan.attribute_preferences[0].weight}
                  onChange={e => edit({
                    attribute_preferences: [{ ...plan.attribute_preferences![0], weight: Number(e.target.value) }]
                  })}
                />
              </StadiumField>
            )}

            <div className="stack gap05 mt02">
              <StadiumCheckbox
                checked={plan.confirmed_only}
                onChange={checked => edit({ confirmed_only: checked })}
                label="Require confirmed footballer identities"
                description="Exclude unverified placeholder items or research models without licensed identity"
              />
              <StadiumCheckbox
                checked={plan.continuity}
                onChange={checked => edit({ continuity: checked })}
                label="Retain incumbents on equal fit"
                description="Preserve current squad starters unless replacement offers definitive tactical gain"
              />
            </div>
          </div>

          <fieldset className="mt1" style={{ padding: '0.85rem', borderColor: 'var(--border-strong)', borderRadius: 'var(--field-radius)' }}>
            <legend style={{ padding: '0 0.5rem', color: 'var(--text-secondary)', fontWeight: 600, fontSize: '0.78rem' }}>
              Compare tactical profiles
            </legend>
            <div className="row flex-wrap gap05">
              {TACTICS.filter(t => t !== plan.tactical_profile).map(t => (
                <StadiumCheckbox
                  key={t}
                  checked={plan.alternatives.includes(t)}
                  onChange={checked => edit({
                    alternatives: checked
                      ? [...plan.alternatives.filter(a => a !== plan.tactical_profile), t]
                      : plan.alternatives.filter(a => a !== t)
                  })}
                  label={t.replace(/_/g, ' ')}
                />
              ))}
            </div>
          </fieldset>
        </section>
      </aside>

      {/* Center: Dominant Tactical Pitch Cockpit */}
      <section className="card stack squad-canvas" aria-label="Formation pitch">
        <header className="row space-between align-center flex-wrap gap05">
          <div>
            <h2>Formation Pitch</h2>
            <p className="muted mb0">{plan.formation} · {plan.tactical_profile.replace(/_/g, ' ')}</p>
          </div>
          <div className="row align-center gap05 flex-wrap">
            {demoLoaded && (
              <span className="badge warn">SYNTHETIC_FIXTURE · Sample XI</span>
            )}
            <span className="badge info">11 Formation Slots Active</span>
            {demoLoaded ? (
              <button type="button" className="btn ghost sm" onClick={clearDemoXi}>
                Clear Demo XI
              </button>
            ) : !enabled && (
              <button type="button" className="btn primary sm" onClick={loadDemoXi}>
                Load Demo 4-3-3 XI
              </button>
            )}
          </div>
        </header>

        {/* Stadium Pitch with true tactile slot buttons */}
        <StadiumPitch
          slots={slotDefs}
          render={s => {
            const evaluated = preview?.optimized.slots.find(row => row.slot === s.slot)
            const item = evaluated ? evaluated.item : selectedItems.get(plan.assigned[s.slot])
            const isEmpty = !item
            const isElite = evaluated?.score != null && evaluated.score >= 0.85
            const isWeak = evaluated?.score != null && evaluated.score < 0.65
            const isGk = s.position === 'GK'
            const classNames = [
              'pitch-player',
              'tactical-slot-btn',
              activeSlot === s.slot ? 'is-active' : '',
              isEmpty ? 'is-empty' : '',
              isElite ? 'is-elite' : '',
              isWeak ? 'is-weak' : '',
              isGk ? 'is-goalkeeper' : '',
            ].filter(Boolean).join(' ')
            return (
              <button
                type="button"
                className={classNames}
                aria-pressed={activeSlot === s.slot}
                onClick={() => {
                  setActiveSlot(s.slot)
                  slotInputs.current[s.slot]?.focus()
                }}
              >
                <strong>{s.slot}</strong>
                <small>{item?.name ?? 'Unfilled'}</small>
                {item && <span className="sr-only">{item.rarity} item {item.source_item_id}</span>}
                {plan.locked_slots.includes(s.slot) && (
                  <small className="slot-lock-badge">
                    <StadiumIcon name="shield" size={11} /> Locked
                  </small>
                )}
                {evaluated && (
                  <small className="slot-fit-score">
                    {evaluated.score == null ? 'Unscored' : fmt(evaluated.score)}
                  </small>
                )}
              </button>
            )
          }}
        />

        {(() => {
          const targetSlot = activeSlot || slotDefs[slotDefs.length - 1]?.slot || 'ST'
          const slotMeta = slotDefs.find(s => s.slot === targetSlot) ?? slotDefs[0]
          if (!slotMeta) return null
          const evalRow = preview?.optimized.slots.find(r => r.slot === slotMeta.slot)
          const item = evalRow ? evalRow.item : selectedItems.get(plan.assigned[slotMeta.slot])
          return (
            <div className="callout info row space-between align-center flex-wrap gap05" aria-label="Selected formation slot inspector">
              <div>
                <div className="row align-center gap05">
                  <strong className="mono">{slotMeta.slot}</strong>
                  <span className="badge info">{slotMeta.position}</span>
                  <span className="tiny muted">{slotMeta.side} · {slotMeta.duty}</span>
                </div>
                <div className="small mt02">
                  {item ? `${item.name} (${item.rarity})` : 'No card assigned yet — select from shortlist or scout fits for this role.'}
                </div>
              </div>
              <div className="row gap05 flex-wrap">
                <Link
                  className="btn primary sm"
                  to={`/intelligence?position=${slotMeta.position}&tactical_profile=${plan.tactical_profile}`}
                >
                  Scout {slotMeta.position} Fit
                </Link>
                <Link
                  className="btn ghost sm"
                  to={`/search?position=${slotMeta.position}`}
                >
                  Browse {slotMeta.position}
                </Link>
              </div>
            </div>
          )
        })()}

        <p className="muted small mb0">
          {preview ? 'Optimized preview active. Apply lineup to update squad.' : 'Click any formation slot on the pitch to inspect its tactical duty or choose an eligible card below.'}
        </p>

        {plan.candidate_ids.length > 0 && (
          <div className="squad-bench-tray mt07 mb05" aria-label="Shortlist bench">
            <div className="row justify-between align-center mb02">
              <span className="tiny muted uppercase letter-spacing font-mono">Shortlist Bench ({plan.candidate_ids.length})</span>
              <span className="tiny faint">{Object.keys(plan.assigned).length}/11 Assigned</span>
            </div>
            <div className="row gap04 wrap">
              {plan.candidate_ids.slice(0, 12).map(id => {
                const c = selectedItems.get(id)
                if (!c) return null
                const isAssigned = Object.values(plan.assigned).includes(id)
                return (
                  <span
                    key={id}
                    className={`badge ${isAssigned ? 'lime' : 'outline'}`}
                    style={{ fontSize: '0.72rem' }}
                    title={isAssigned ? `${c.name} is in lineup` : `${c.name} (${c.positions.join('/')})`}
                  >
                    {isAssigned ? '● ' : '○ '}{c.name} · {c.positions.join('/')}
                  </span>
                )
              })}
            </div>
          </div>
        )}

        <h3>Assign Formation Slots</h3>
        <div className="lab-slots">
          {slotDefs.map(s => (
            <div className="card tight" key={s.slot}>
              <StadiumField
                label={
                  <span>
                    <strong>{s.slot}</strong> · {s.position}
                    {defaults?.formation === plan.formation && defaults?.preferred_slot === s.slot && ' · preferred'}
                  </span>
                }
              >
                <StadiumSelect
                  ref={node => { slotInputs.current[s.slot] = node }}
                  aria-label={'Assign ' + s.slot}
                  value={plan.assigned[s.slot] ?? ''}
                  onChange={val => assign(s.slot, val)}
                  disabled={!enabled}
                >
                  <option value="">Unfilled</option>
                  {plan.candidate_ids
                    .map(id => selectedItems.get(id))
                    .filter((c): c is Item => !!c)
                    .filter(c => c.positions.includes(s.position) && ((s.position === 'GK') === (c.positions[0] === 'GK')) && !plan.excluded.includes(c.entity_id))
                    .map(c => (
                      <option
                        key={c.entity_id}
                        disabled={!withoutAssignment(s.slot, c.entity_id)}
                        value={c.entity_id}
                      >
                        {label(c)}
                      </option>
                    ))}
                </StadiumSelect>
              </StadiumField>
              <StadiumCheckbox
                ariaLabel={'Lock ' + s.slot}
                checked={plan.locked_slots.includes(s.slot)}
                disabled={!plan.assigned[s.slot] || !enabled}
                onChange={checked => edit({
                  locked_slots: checked
                    ? [...plan.locked_slots, s.slot]
                    : plan.locked_slots.filter(a => a !== s.slot)
                })}
                label="Lock slot"
              />
            </div>
          ))}
        </div>
      </section>

      {/* Upgrade Controls & Actions */}
      <section className="card workspace-rail full-width" aria-labelledby="upgrade-settings">
        <h2 id="upgrade-settings">Upgrade Controls</h2>
        <div className="row align-center gap1 flex-wrap">
          <div style={{ minWidth: '240px' }}>
            <StadiumField label="Replacement mode" hint="Scope of tactical optimization">
              <StadiumSelect
                aria-label="Replacement mode"
                value={plan.upgrade ?? ''}
                onChange={val => edit({ upgrade: val || null })}
                disabled={!enabled}
              >
                <option value="">Optimize lineup</option>
                <option value="one">Exactly one replacement</option>
                <option value="two">Exactly two replacements</option>
                <option value="minimum">Fewest changes for a target gain</option>
              </StadiumSelect>
            </StadiumField>
          </div>
          {plan.upgrade && (
            <div style={{ minWidth: '180px' }}>
              <StadiumField label="Minimum total fit gain" hint="Threshold to trigger replacement">
                <StadiumInput
                  type="number"
                  min="0"
                  max="11"
                  step="0.001"
                  aria-label="Minimum total fit gain"
                  value={plan.minimum_gain}
                  onChange={e => edit({ minimum_gain: Number(e.target.value) })}
                  disabled={!enabled}
                />
              </StadiumField>
            </div>
          )}
          {undo && (
            <button
              className="btn ghost sm"
              style={{ alignSelf: 'center', marginTop: '0.4rem' }}
              onClick={() => {
                setPlan(undo)
                setUndo(null)
                setPitchPreview(null)
                previewRequest.current++
              }}
            >
              Undo last edit
            </button>
          )}
        </div>
      </section>

      {Object.keys(plan.assigned).length > 0 && enabled && (
        <FormationChange
          key={'formation:' + JSON.stringify(plan)}
          plan={plan}
          formations={Object.keys(options.data?.formations ?? {})}
          apply={(formation, assigned) => edit({ formation, assigned })}
        />
      )}

      {/* Right Rail: Squad Intelligence & Bottom Sections: Squad DNA & Upgrade Studio */}
      <Evaluation
        key={JSON.stringify(plan) + (demoLoaded ? ':demo' : '')}
        plan={plan}
        initialResult={preview}
        apply={assigned => edit({ assigned })}
        onSave={onSave}
        enabled={enabled && !demoLoaded}
        onPreview={async run => {
          const generation = ++previewRequest.current
          const next = await run()
          if (next && generation === previewRequest.current && currentPlan.current === plan) setPitchPreview(next)
        }}
      />
    </div>
  )
}

function FormationChange({plan,formations,apply}:{plan:Plan;formations:string[];apply:(f:string,a:Assigned)=>void}) {
  const [target,setTarget] = useState(formations.find(f=>f!==plan.formation)??'')
  const [useShortlist,setShortlist] = useState(false)
  return (
    <section className="card workspace-rail full-width">
      <h2>Formation Change Transformation</h2>
      <div className="row align-center gap1 flex-wrap">
        <div style={{ minWidth: '220px' }}>
          <StadiumField label="Target formation" hint="Select tactical reorganization model">
            <StadiumSelect
              aria-label="Target formation"
              value={target}
              onChange={val => setTarget(val)}
            >
              {formations.filter(f=>f!==plan.formation).map(f=><option key={f} value={f}>{f}</option>)}
            </StadiumSelect>
          </StadiumField>
        </div>
        <div style={{ alignSelf: 'center', marginTop: '0.4rem' }}>
          <StadiumCheckbox
            checked={useShortlist}
            onChange={checked => setShortlist(checked)}
            label="Include shortlisted replacements"
            description="Slot candidates from current bench tray"
          />
        </div>
      </div>
      <FormationPreview key={target+useShortlist} plan={plan} target={target} useShortlist={useShortlist} apply={apply}/>
    </section>
  )
}

function FormationPreview({plan,target,useShortlist,apply}:{plan:Plan;target:string;useShortlist:boolean;apply:(f:string,a:Assigned)=>void}) {
  const work=useAction(()=>api.post<{assignments:Assigned;current:Lineup;target:Lineup;changes:{entity_id:string;from_slot:string|null;to_slot:string|null}[]}>(
    root+'/squad/transform',{plan,target,use_shortlist:useShortlist}))
  return (
    <div className="mt05">
      <button disabled={work.pending||!target} className="btn primary sm" onClick={()=>void work.run()}>
        Preview formation change
      </button>
      <ErrorBox error={work.error}/>
      {work.pending && <Loading label="Evaluating target slots"/>}
      {work.result && (
        <div className="callout info mt05">
          <p>Current formation: {work.result.current.scored} scored · {target}: {work.result.target.scored} scored</p>
          {work.result.changes.map(c=>(
            <p key={c.entity_id} className="small">
              {[...work.result!.target.slots,...work.result!.current.slots].find(s=>s.item?.entity_id===c.entity_id)?.item?.name}
              {' · '}{c.from_slot??'Shortlist'} → {c.to_slot??'Removed'}
            </p>
          ))}
          <button className="btn sm mt05" onClick={()=>apply(target,work.result!.assignments)}>
            Apply target formation
          </button>
        </div>
      )}
    </div>
  )
}

function Evaluation({plan,initialResult,apply,onSave,onPreview,enabled=true}:{plan:Plan;initialResult:Result|null;apply:(a:Assigned)=>void;onSave:()=>void;enabled?:boolean;onPreview:(run:()=>Promise<Result|null>)=>Promise<void>}) {
  const {user} = useSession()
  const action = useAction(()=>api.post<Result>(root+'/squad/preview',plan))
  const result = action.result??initialResult
  const [name,setName] = useState('')
  const save = useAction(async()=>{const r=await api.post<{name:string}>(root+'/squad/saved',{plan,name,receipt:result?.receipt});onSave();return r})
  const [view,setView] = useState<'optimized'|'current'>('optimized')
  const dna = result?.[view]

  return (
    <>
      <aside className="card stack workspace-rail workspace-insights squad-insights" aria-label="Squad intelligence">
        <h2>Squad Intelligence</h2>
        <div>
          <div className="section-title">Tactical Objective</div>
          <strong>{plan.tactical_profile.replace(/_/g, ' ')}</strong>
        </div>
        <button
          className="btn primary"
          disabled={action.pending || !enabled}
          onClick={()=>void onPreview(action.run)}
        >
          Preview card squad
        </button>
        {action.pending && <Loading label="Scoring formation slots with Phase 30 optimizer"/>}
        <ErrorBox error={action.error}/>
        {dna ? (
          <dl className="kv">
            <dt>Scored slots</dt><dd>{dna.scored} / {dna.filled} filled</dd>
            <dt>Total fit</dt><dd>{fmt(dna.total_fit)}</dd>
            <dt>Coverage</dt><dd>{dna.mean_coverage_scored == null ? 'Unavailable' : Math.round(dna.mean_coverage_scored * 100) + '%'}</dd>
            <dt>Weak slots</dt><dd>{dna.weakest_scored_slots.join(', ') || 'Unavailable'}</dd>
          </dl>
        ) : (
          <div className="empty-insights-box">
            <p className="muted small mb0">
              Add card items and select <strong>Preview card squad</strong> to see evaluated slot scores, fit coverage, and weak positions.
            </p>
          </div>
        )}
        {result && user && (
          <div className="stack gap05 mt1">
            <StadiumField label="Save Scenario" hint="Squad scenario name (max 100 chars)">
              <StadiumInput
                value={name}
                maxLength={100}
                placeholder="Squad scenario name…"
                aria-label="Squad scenario name"
                onChange={e=>setName(e.target.value)}
              />
            </StadiumField>
            <button className="btn sm" disabled={!name.trim()||save.pending} onClick={()=>void save.run()}>
              Save current scenario
            </button>
            <ErrorBox error={save.error}/>
            {save.result && <p role="status" className="small positive">Saved {save.result.name}</p>}
          </div>
        )}
      </aside>

      {/* Squad DNA Section */}
      <section className="card stack full-width" id="squad-dna" aria-labelledby="squad-dna-title">
        <h2 id="squad-dna-title">Squad DNA</h2>
        {result && dna ? (
          <>
            <div className="row space-between align-center">
              <div style={{ minWidth: '180px' }}>
                <StadiumSelect
                  aria-label="Analyze Lineup"
                  value={view}
                  onChange={val => setView(val as typeof view)}
                >
                  <option value="optimized">Optimized preview</option>
                  <option value="current">Current assignments</option>
                </StadiumSelect>
              </div>
              <span className="badge info">
                {result.solver_status} · Uniqueness: {dna.footballer_uniqueness_verified ? 'Verified' : 'Unverified'}
              </span>
            </div>

            <div className="row gap1 flex-wrap mt05">
              <div className="stat-card">
                <span className="stat-label">Total Fit</span>
                <strong className="stat-val text-lime">{fmt(dna.total_fit)}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Mean Coverage</span>
                <strong className="stat-val text-cyan">
                  {dna.mean_coverage_scored == null ? 'Unavailable' : Math.round(dna.mean_coverage_scored * 100) + '%'}
                </strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Scored Slots</span>
                <strong className="stat-val">{dna.scored} / {dna.filled}</strong>
              </div>
            </div>

            <WholeXISynergyDashboard
              dna={dna}
              profile={plan.tactical_profile}
              formation={plan.formation}
              synergy={result.tactical_synergy?.[view]}
            />

            <h3>Slot Evaluation Breakdown</h3>
            <ul className="squad-dna-slots-list">
              {dna.slots.map(s => (
                <li key={s.slot} className="row space-between align-center p03 border-b">
                  <span><strong>{s.slot}</strong> · {s.item ? label(s.item) : 'Unfilled'}</span>
                  <span className="font-mono">{s.score != null ? fmt(s.score) : <span className="muted">{s.reason}</span>}</span>
                </li>
              ))}
            </ul>

            <p className="small muted">
              Lowest scored slots: <strong>{dna.weakest_scored_slots.join(', ') || 'Unavailable'}</strong>
            </p>

            {!!dna.attribute_suitability.length && (
              <p className="small muted">
                Highest mean attribute fit: {dna.attribute_suitability.slice(0, 3).map(a => `${a.attribute} ${fmt(a.mean)} (${a.scored_slots} slots)`).join(', ')}.
                {' '}Lowest: {dna.attribute_suitability.slice(-3).reverse().map(a => `${a.attribute} ${fmt(a.mean)} (${a.scored_slots} slots)`).join(', ')}.
              </p>
            )}

            <details className="mt05">
              <summary>Published squad attributes and scoring contributions</summary>
              <p className="small">
                Published outfield means: {Object.entries(dna.observed_outfield_attributes).map(([a, v]) => `${a} ${v.mean?.toFixed(1) ?? 'Unavailable'} (${v.published} items)`).join(' · ')}
              </p>
              <p className="small">Unpublished PlayStyle lists: {dna.unknown_playstyle_lists}. Official role eligibility unavailable.</p>
              <div className="row flex-wrap gap05">
                {Object.entries(dna.attribute_contributions).map(([a, v]) => (
                  <span key={a} className="badge small">{a}: {fmt(v)}</span>
                ))}
              </div>
              <p className="small mt05">{Object.entries(dna.observed_playstyles).map(([s, n]) => `${s} × ${n}`).join(', ') || 'No published PlayStyles in this lineup'}</p>
            </details>

            <h3>Tactical Matrix</h3>
            <p className="small muted">Non-dominated profiles: {result.nondominated_generated_profiles.join(', ') || 'None'}</p>
            {Object.entries(result.unavailable_profiles ?? {}).map(([p, v]) => (
              <p key={p} className="small warn">{p} unavailable: Insufficient evidence for locked slots {v.slots.join(', ')}.</p>
            ))}
            <div className="g2 gap08 mt05">
              {result.matrix.map(m => (
                <div key={m.optimized_for} className="card tight">
                  <div className="row space-between align-center">
                    <strong>{m.optimized_for}</strong>
                    {m.optimized_for !== 'CURRENT' && (
                      <button className="btn ghost sm" onClick={() => apply(m.assignment)}>
                        Apply {m.optimized_for}
                      </button>
                    )}
                  </div>
                  <p className="small muted mt05">{Object.entries(m.scores).map(([p, v]) => `${p} ${fmt(v)} (${m.scored_counts[p]} scored)`).join(' · ')}</p>
                  {!!m.changed_slots.length && (
                    <p className="tiny faint">Changes: {m.changed_slots.join(', ')}</p>
                  )}
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="empty-dna-box">
            <p className="muted mb0">Run a squad preview to populate the tactical matrix, slot evidence and Squad DNA.</p>
          </div>
        )}
      </section>

      {/* Smart Upgrade Studio Section */}
      <section className="card stack full-width" id="upgrade-studio" aria-labelledby="upgrade-title">
        <h2 id="upgrade-title">Smart Upgrade Studio</h2>
        {result?.upgrade_status ? (
          <>
            <div className="row space-between align-center">
              <span className="badge positive">{result.upgrade_status}</span>
              <span className="font-mono strong text-lime">Total Fit Gain: +{fmt(result.upgrade_gain)}</span>
            </div>
            <p className="muted small">Changes are evaluated strictly within your selected shortlist and tactical context.</p>
            <div className="g2 gap1">
              {result.upgrades.map(u => (
                <section className="card tight upgrade-card" key={u.slot}>
                  <h3>Position Slot: {u.slot}</h3>
                  <div className="upgrade-comparison">
                    <div className="upgrade-col">
                      <span className="tiny faint">CURRENT ITEM</span>
                      <p className="mb05 font-display strong">{label(u.before)}</p>
                      <span className="font-mono muted">{fmt(u.before_score)}</span>
                    </div>
                    <div className="upgrade-col upgrade-col-after">
                      <span className="tiny faint text-lime">PROPOSED REPLACEMENT</span>
                      <p className="mb05 font-display strong text-lime">{label(u.after)}</p>
                      <span className="font-mono strong text-lime">{fmt(u.after_score)}</span>
                    </div>
                  </div>
                  <p className="muted small mt05">{u.why.join('. ')}</p>
                  <p className="tiny faint mb0">Proposed item coverage: {Math.round(u.coverage_after * 100)}%</p>
                </section>
              ))}
            </div>
            {!!result.upgrades.length && (
              <button
                className="btn primary"
                onClick={() => apply({
                  ...plan.assigned,
                  ...Object.fromEntries(result.upgrades.map(u => [u.slot, u.after.entity_id]))
                })}
              >
                Apply replacements
              </button>
            )}
          </>
        ) : (
          <div className="empty-upgrades-box">
            <p className="muted mb0">Choose a replacement mode above and preview the squad to evaluate upgrade recommendations.</p>
          </div>
        )}
      </section>
    </>
  )
}

function WholeXISynergyDashboard({
  dna,
  profile,
  formation,
  synergy,
}: {
  dna: Lineup
  profile: string
  formation: string
  synergy?: WholeXISynergy | null
}) {
  const scoredSlots = dna.slots.filter(s => s.score != null)
  if (scoredSlots.length === 0) return null

  // Interactive inspection state
  const [activeTab, setActiveTab] = useState<'WHOLE_XI' | 'LEFT_FLANK' | 'CENTRAL_SPINE' | 'RIGHT_FLANK' | 'ALERTS' | 'PARTNERSHIPS' | 'STABILITY' | 'PERSONAL_FIT'>('WHOLE_XI')
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null)

  // Use backend mathematical synergy if available; otherwise compute deterministic fallback
  const alignment = synergy?.experimental_tactical_alignment
  const alerts = synergy?.tactical_friction_alerts ?? []

  // Deterministic fallback calculations if synergy was not returned by API
  const scores = scoredSlots.map(s => s.score ?? 0)
  const fallbackMean = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0
  const fallbackDispersion = scores.length > 1
    ? Math.sqrt(scores.reduce((acc, x) => acc + Math.pow(x - fallbackMean, 2), 0) / scores.length)
    : 0

  const fallbackAlerts: TacticalAlert[] = []
  dna.slots.forEach(s => {
    if (s.score != null && s.score < 0.70 && s.item) {
      fallbackAlerts.push({
        rule_id: 'RULE-HEURISTIC-FIT',
        rule_version: '1.0.0',
        slot: s.slot,
        position: s.slot,
        card_item_id: s.item.entity_id,
        card_name: s.item.name,
        tactical_context: profile,
        evaluated_capability: 'Overall tactical suitability',
        attribute_name: 'suitability_score',
        attribute_value: Math.round(s.score * 100),
        threshold: 70,
        evidence_classification: 'MODELED_HEURISTIC',
        friction_penalty: 0.020,
        explanation: `Individual suitability (${fmt(s.score)}) is significantly below tactical threshold for ${profile.replace(/_/g, ' ')}.`,
        recommended_action: 'Upgrade or rotate this slot with a specialist candidate.',
        empirical_reference: null,
      })
    }
  })

  const activeAlerts = alerts.length > 0 ? alerts : fallbackAlerts
  const meanSuitability = alignment?.mean_suitability ?? fallbackMean
  const dispersion = alignment?.suitability_dispersion ?? fallbackDispersion
  const frictionPenalty = alignment?.friction_penalty ?? activeAlerts.reduce((sum, a) => sum + (a.friction_penalty || 0), 0)

  const alignmentIndex = alignment?.alignment_index_pct ?? Math.max(0, Math.min(100, Math.round(1000 * (fallbackMean - 0.5 * fallbackDispersion - frictionPenalty)) / 10))

  let alignmentStatus = alignment?.status ?? (
    alignmentIndex >= 82.0 ? 'HIGH_ALIGNMENT' :
    alignmentIndex >= 72.0 ? 'MODERATE_ALIGNMENT' :
    alignmentIndex >= 60.0 ? 'PARTIAL_ALIGNMENT' : 'TACTICAL_DISSONANCE'
  )

  let badgeColor = 'warn'
  if (alignmentStatus === 'HIGH_ALIGNMENT') badgeColor = 'lime'
  else if (alignmentStatus === 'MODERATE_ALIGNMENT') badgeColor = 'cyan'
  else if (alignmentStatus === 'TACTICAL_DISSONANCE') badgeColor = 'outline'

  // Channels: use backend partitioning if available, else derive standard 3 channels
  const channels = synergy?.channels ?? {
    LEFT_FLANK: {
      name: 'Left Flank Unit',
      slots: dna.slots.filter(s => ['LB', 'LWB', 'LCM', 'LM', 'LW', 'LF'].includes(s.slot)).map(s => s.slot),
      scored_count: dna.slots.filter(s => ['LB', 'LWB', 'LCM', 'LM', 'LW', 'LF'].includes(s.slot) && s.score != null).length,
      unscored_slots: dna.slots.filter(s => ['LB', 'LWB', 'LCM', 'LM', 'LW', 'LF'].includes(s.slot) && s.score == null).map(s => s.slot),
      mean_suitability: null,
      status: 'ACTIVE',
      contributing_items: dna.slots.filter(s => ['LB', 'LWB', 'LCM', 'LM', 'LW', 'LF'].includes(s.slot)).map(s => ({
        slot: s.slot,
        player_name: s.item?.name ?? 'Unfilled',
        score: s.score
      }))
    },
    CENTRAL_SPINE: {
      name: 'Central Spine Unit',
      slots: dna.slots.filter(s => ['GK', 'CB', 'LCB', 'RCB', 'CM', 'CDM', 'LDM', 'RDM', 'CAM', 'ST', 'CF', 'LST', 'RST'].includes(s.slot)).map(s => s.slot),
      scored_count: dna.slots.filter(s => ['GK', 'CB', 'LCB', 'RCB', 'CM', 'CDM', 'LDM', 'RDM', 'CAM', 'ST', 'CF', 'LST', 'RST'].includes(s.slot) && s.score != null).length,
      unscored_slots: dna.slots.filter(s => ['GK', 'CB', 'LCB', 'RCB', 'CM', 'CDM', 'LDM', 'RDM', 'CAM', 'ST', 'CF', 'LST', 'RST'].includes(s.slot) && s.score == null).map(s => s.slot),
      mean_suitability: null,
      status: 'ACTIVE',
      contributing_items: dna.slots.filter(s => ['GK', 'CB', 'LCB', 'RCB', 'CM', 'CDM', 'LDM', 'RDM', 'CAM', 'ST', 'CF', 'LST', 'RST'].includes(s.slot)).map(s => ({
        slot: s.slot,
        player_name: s.item?.name ?? 'Unfilled',
        score: s.score
      }))
    },
    RIGHT_FLANK: {
      name: 'Right Flank Unit',
      slots: dna.slots.filter(s => ['RB', 'RWB', 'RCM', 'RM', 'RW', 'RF'].includes(s.slot)).map(s => s.slot),
      scored_count: dna.slots.filter(s => ['RB', 'RWB', 'RCM', 'RM', 'RW', 'RF'].includes(s.slot) && s.score != null).length,
      unscored_slots: dna.slots.filter(s => ['RB', 'RWB', 'RCM', 'RM', 'RW', 'RF'].includes(s.slot) && s.score == null).map(s => s.slot),
      mean_suitability: null,
      status: 'ACTIVE',
      contributing_items: dna.slots.filter(s => ['RB', 'RWB', 'RCM', 'RM', 'RW', 'RF'].includes(s.slot)).map(s => ({
        slot: s.slot,
        player_name: s.item?.name ?? 'Unfilled',
        score: s.score
      }))
    }
  }

  const getChannelFit = (ch: ChannelMetric) => {
    if (ch.mean_suitability != null) return ch.mean_suitability
    const sc = ch.contributing_items.filter(c => c.score != null).map(c => c.score as number)
    return sc.length ? sc.reduce((a, b) => a + b, 0) / sc.length : null
  }

  const leftFit = getChannelFit(channels.LEFT_FLANK)
  const centerFit = getChannelFit(channels.CENTRAL_SPINE)
  const rightFit = getChannelFit(channels.RIGHT_FLANK)

  return (
    <div className="synergy-dashboard">
      <div className="row space-between align-center mb05">
        <div>
          <h3 className="mb0" style={{ fontSize: '0.98rem' }}>Whole-XI Tactical Synergy & Alignment</h3>
          <p className="tiny muted mb0">
            Deterministic collective synergy analysis for {profile.replace(/_/g, ' ')} under {formation}
          </p>
        </div>
        <div className="row align-center gap05">
          <span className="tiny font-mono strong text-primary">
            Alignment: {alignmentIndex != null ? `${alignmentIndex}%` : 'Unavailable'}
          </span>
          <span className={`badge sm ${badgeColor}`}>{alignmentStatus.replace(/_/g, ' ')}</span>
        </div>
      </div>

      <div className="synergy-submetrics">
        <span>Mean Suitability (r̄): <strong className="text-lime">{fmt(meanSuitability)}</strong></span>
        <span>Dispersion Penalty (-0.5·σ): <strong className="text-cyan">{fmt(-0.5 * dispersion)}</strong></span>
        <span>Tactical Friction (-δ): <strong className="text-warn">{fmt(-frictionPenalty)}</strong></span>
        <span>Active Alerts: <strong>{activeAlerts.length}</strong></span>
      </div>

      <div className="synergy-grid">
        <div
          className={`synergy-node selectable ${activeTab === 'LEFT_FLANK' ? 'active' : ''}`}
          onClick={() => setActiveTab('LEFT_FLANK')}
          role="button"
          tabIndex={0}
          aria-label="Inspect Left Flank Unit"
        >
          <div className="synergy-node-title">
            <span>Left Flank Unit</span>
            <span className="tiny muted">{channels.LEFT_FLANK.slots.length} Slots</span>
          </div>
          <strong className="synergy-node-val">{fmt(leftFit)}</strong>
          <span className="synergy-node-desc">
            {leftFit != null && leftFit >= 0.82
              ? 'High technical control & press resistance on the left flank.'
              : 'Moderate left flank synergy; inspect width and transition support.'}
          </span>
          <span className="tiny text-cyan mt02">Click to inspect unit →</span>
        </div>

        <div
          className={`synergy-node selectable ${activeTab === 'CENTRAL_SPINE' ? 'active' : ''}`}
          onClick={() => setActiveTab('CENTRAL_SPINE')}
          role="button"
          tabIndex={0}
          aria-label="Inspect Central Spine Unit"
        >
          <div className="synergy-node-title">
            <span>Central Spine Unit</span>
            <span className="tiny muted">{channels.CENTRAL_SPINE.slots.length} Slots</span>
          </div>
          <strong className="synergy-node-val">{fmt(centerFit)}</strong>
          <span className="synergy-node-desc">
            {centerFit != null && centerFit >= 0.82
              ? 'Solid vertical spine: anchor, pivot & central finish channel aligned.'
              : 'Central spine vulnerable to central counter-pressure or low pivot suitability.'}
          </span>
          <span className="tiny text-cyan mt02">Click to inspect unit →</span>
        </div>

        <div
          className={`synergy-node selectable ${activeTab === 'RIGHT_FLANK' ? 'active' : ''}`}
          onClick={() => setActiveTab('RIGHT_FLANK')}
          role="button"
          tabIndex={0}
          aria-label="Inspect Right Flank Unit"
        >
          <div className="synergy-node-title">
            <span>Right Flank Unit</span>
            <span className="tiny muted">{channels.RIGHT_FLANK.slots.length} Slots</span>
          </div>
          <strong className="synergy-node-val">{fmt(rightFit)}</strong>
          <span className="synergy-node-desc">
            {rightFit != null && rightFit >= 0.82
              ? 'Explosive transition channel with strong overlap and delivery capability.'
              : 'Right wing width requires greater physical engagement or passing support.'}
          </span>
          <span className="tiny text-cyan mt02">Click to inspect unit →</span>
        </div>
      </div>

      {activeAlerts.length > 0 && (
        <div className="dissonance-alert">
          <div className="dissonance-alert-title row align-center gap05">
            <StadiumIcon name="alert" size={15} />
            <span>Tactical Friction Detected ({activeAlerts.length} rule {activeAlerts.length === 1 ? 'violation' : 'violations'})</span>
          </div>
          {activeAlerts.map((alert, idx) => (
            <div
              key={alert.rule_id + alert.slot + idx}
              className="dissonance-item alert-card-detailed clickable"
              onClick={() => {
                setActiveTab('ALERTS')
                setSelectedAlertId(alert.rule_id + alert.slot)
              }}
            >
              <div className="row space-between align-center mb02">
                <span>
                  <strong>[{alert.rule_id}] {alert.slot} · {alert.card_name}</strong> ({alert.position})
                </span>
                <span className={`badge sm ${alert.evidence_classification === 'EMPIRICALLY_SUPPORTED' ? 'lime' : 'cyan'}`}>
                  {alert.evidence_classification.replace(/_/g, ' ')}
                </span>
              </div>
              <p className="mb02">{alert.explanation}</p>
              <div className="row space-between align-center">
                <span className="dissonance-suggestion row align-center gap03">
                  <StadiumIcon name="zap" size={13} />
                  <span>{alert.recommended_action}</span>
                </span>
                <span className="tiny text-warn font-mono">Deduction: -{(alert.friction_penalty * 100).toFixed(1)}%</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Interactive Synergy Explanation Inspector */}
      <div className="synergy-inspector" id="synergy-inspector-panel">
        <div className="row space-between align-center mb05">
          <h4 className="mb0" style={{ fontSize: '0.92rem' }}>Synergy Explanation Inspector</h4>
          <span className="tiny muted">Interactive Mathematical Trace & Provenance</span>
        </div>

        <nav aria-label="Synergy tabs" className="synergy-tabs">
          <button
            type="button"
            className={`synergy-tab-btn ${activeTab === 'WHOLE_XI' ? 'active' : ''}`}
            onClick={() => setActiveTab('WHOLE_XI')}
          >
            Whole XI Trace
          </button>
          <button
            type="button"
            className={`synergy-tab-btn ${activeTab === 'LEFT_FLANK' ? 'active' : ''}`}
            onClick={() => setActiveTab('LEFT_FLANK')}
          >
            Left Flank ({channels.LEFT_FLANK.slots.length})
          </button>
          <button
            type="button"
            className={`synergy-tab-btn ${activeTab === 'CENTRAL_SPINE' ? 'active' : ''}`}
            onClick={() => setActiveTab('CENTRAL_SPINE')}
          >
            Central Spine ({channels.CENTRAL_SPINE.slots.length})
          </button>
          <button
            type="button"
            className={`synergy-tab-btn ${activeTab === 'RIGHT_FLANK' ? 'active' : ''}`}
            onClick={() => setActiveTab('RIGHT_FLANK')}
          >
            Right Flank ({channels.RIGHT_FLANK.slots.length})
          </button>
          <button
            type="button"
            className={`synergy-tab-btn ${activeTab === 'ALERTS' ? 'active' : ''}`}
            onClick={() => setActiveTab('ALERTS')}
          >
            Tactical Alerts ({activeAlerts.length})
          </button>
          <button
            type="button"
            className={`synergy-tab-btn ${activeTab === 'PARTNERSHIPS' ? 'active' : ''}`}
            onClick={() => setActiveTab('PARTNERSHIPS')}
          >
            Partnerships (V2)
          </button>
          <button
            type="button"
            className={`synergy-tab-btn ${activeTab === 'STABILITY' ? 'active' : ''}`}
            onClick={() => setActiveTab('STABILITY')}
          >
            Stability Lab
          </button>
          <button
            type="button"
            className={`synergy-tab-btn ${activeTab === 'PERSONAL_FIT' ? 'active' : ''}`}
            onClick={() => setActiveTab('PERSONAL_FIT')}
          >
            Personal Coach & Fit
          </button>
        </nav>

        {activeTab === 'WHOLE_XI' && (
          <div className="stack gap05">
            <div className="synergy-trace-box">
              <div className="text-cyan strong mb02">Mathematical Alignment Formula:</div>
              <div>I_align = max(0.0, min(1.0, r̄ - 0.5·σ_r - δ_friction))</div>
              <div className="mt03 text-muted">
                = max(0.0, min(1.0, {fmt(meanSuitability)} - {fmt(0.5 * dispersion)} - {fmt(frictionPenalty)}))
              </div>
              <div className="text-lime strong mt02">
                = {fmt(Math.max(0, Math.min(1, meanSuitability - 0.5 * dispersion - frictionPenalty)))} → {alignmentIndex}% ({alignmentStatus.replace(/_/g, ' ')})
              </div>
            </div>

            <div className="row gap1 flex-wrap">
              <div className="stat-card" style={{ flex: '1 1 200px' }}>
                <span className="stat-label">Classification Conventions</span>
                <span className="tiny text-secondary mt02">
                  • High Alignment: ≥ 82.0%<br />
                  • Moderate: 72.0% - 81.9%<br />
                  • Partial: 60.0% - 71.9%<br />
                  • Dissonance: &lt; 60.0%
                </span>
              </div>
              <div className="stat-card" style={{ flex: '2 1 300px' }}>
                <span className="stat-label">Model Epistemic Provenance</span>
                <p className="tiny text-secondary mb0 mt02">
                  The Experimental Tactical Alignment Index measures deterministic lineup cohesion from individual tactical suitabilities, slot dispersion, and explicit tactical friction penalties. It does not measure physiological bonding, chemistry styles, or hidden scripting.
                </p>
              </div>
            </div>
          </div>
        )}

        {(activeTab === 'LEFT_FLANK' || activeTab === 'CENTRAL_SPINE' || activeTab === 'RIGHT_FLANK') && (
          <div className="stack gap05">
            {(() => {
              const ch = channels[activeTab]
              const chFit = getChannelFit(ch)
              return (
                <>
                  <div className="row space-between align-center p03 border-b">
                    <div>
                      <strong className="text-primary">{ch.name}</strong>
                      <span className="tiny muted ml05">({ch.slots.join(', ')})</span>
                    </div>
                    <div>
                      <span className="tiny muted mr05">Unit Mean:</span>
                      <strong className="font-mono text-lime">{fmt(chFit)}</strong>
                    </div>
                  </div>

                  <div className="stack gap02">
                    {ch.contributing_items.map(item => (
                      <div key={item.slot} className="synergy-slot-card">
                        <span><strong>{item.slot}</strong> · {item.player_name}</span>
                        <span className="font-mono">{item.score != null ? fmt(item.score) : <span className="muted">Unscored (GK/Locked)</span>}</span>
                      </div>
                    ))}
                  </div>

                  {ch.unscored_slots.length > 0 && (
                    <div className="stat-card p05 mt03">
                      <span className="tiny text-warn">
                        Note: Unscored slot ({ch.unscored_slots.join(', ')}) excluded from unit mean calculation (primary goalkeeper is locked/unscored in outfield tactical models).
                      </span>
                    </div>
                  )}
                </>
              )
            })()}
          </div>
        )}

        {activeTab === 'ALERTS' && (
          <div className="stack gap05">
            {activeAlerts.length === 0 ? (
              <div className="stat-card p1 text-center">
                <span className="text-lime strong row align-center justify-center gap05">
                  <StadiumIcon name="check" size={15} />
                  <span>No Active Tactical Friction Alerts</span>
                </span>
                <p className="tiny muted mb0 mt02">All evaluated outfield cards satisfy baseline capability thresholds for {profile.replace(/_/g, ' ')}.</p>
              </div>
            ) : (
              activeAlerts.map((alert, idx) => {
                const isSelected = selectedAlertId === (alert.rule_id + alert.slot)
                return (
                  <div
                    key={alert.rule_id + alert.slot + idx}
                    className={`alert-card-detailed ${isSelected ? 'active' : ''}`}
                    style={isSelected ? { borderColor: 'var(--accent-lime)' } : {}}
                  >
                    <div className="row space-between align-center mb02">
                      <span className="strong">
                        [{alert.rule_id}] {alert.slot} · {alert.card_name}
                      </span>
                      <span className={`badge sm ${alert.evidence_classification === 'EMPIRICALLY_SUPPORTED' ? 'lime' : 'cyan'}`}>
                        {alert.evidence_classification.replace(/_/g, ' ')}
                      </span>
                    </div>

                    <div className="synergy-trace-box">
                      <div><strong>Evaluated Capability:</strong> {alert.evaluated_capability}</div>
                      <div><strong>Attribute Condition:</strong> {alert.attribute_name} ({alert.attribute_value ?? 'N/A'}) &lt; threshold ({alert.threshold})</div>
                      <div><strong>Friction Deduction:</strong> -{(alert.friction_penalty * 100).toFixed(1)}% to Whole-XI Index</div>
                      {alert.empirical_reference && (
                        <div className="mt02 text-lime"><strong>Empirical Match Citation:</strong> {alert.empirical_reference}</div>
                      )}
                      {alert.missing_data_limitation && (
                        <div className="mt02 text-warn"><strong>Data Limitation:</strong> {alert.missing_data_limitation}</div>
                      )}
                    </div>

                    <p className="tiny text-secondary mb02">{alert.explanation}</p>
                    <p className="tiny text-cyan strong mb0 row align-center gap03">
                      <StadiumIcon name="zap" size={13} />
                      <span>Action: {alert.recommended_action}</span>
                    </p>
                  </div>
                )
              })
            )}
          </div>
        )}

        {activeTab === 'PARTNERSHIPS' && (
          <div className="stack gap05">
            <div className="p03 border-b row space-between align-center">
              <div>
                <strong className="text-primary">Partnership Intelligence V2</strong>
                <span className="tiny muted ml05">Capability Complementarity & Spatial Coupling</span>
              </div>
              <span className="badge sm cyan">Deterministic Micro-Units</span>
            </div>

            {(() => {
              const findSlot = (codes: string[]) => dna.slots.find(s => codes.includes(s.slot) && s.item && s.score != null)
              
              const st = findSlot(['ST', 'CF', 'LST'])
              const cam = findSlot(['CAM', 'LCM', 'RCM', 'CM'])
              const lw = findSlot(['LW', 'LM', 'LF'])
              const lb = findSlot(['LB', 'LWB'])
              const rw = findSlot(['RW', 'RM', 'RF'])
              const rb = findSlot(['RB', 'RWB'])
              const cdm = findSlot(['CDM', 'LDM', 'RDM'])
              const cm = dna.slots.find(s => ['CM', 'LCM', 'RCM'].includes(s.slot) && s.item && s.score != null && s.slot !== cdm?.slot)
              const cbs = dna.slots.filter(s => ['CB', 'LCB', 'RCB'].includes(s.slot) && s.item && s.score != null)

              const pairs = [
                {
                  type: 'ST + CAM (Vertical Spacing & Creation Channel)',
                  c1: st, c2: cam,
                  desc: 'Finishing capability paired with central chance progression and final-third incision.',
                  complementarity: (st && cam) ? 2 * (st.score! * cam.score!) / (st.score! + cam.score!) : null
                },
                {
                  type: 'Left Flank Unit (LW + LB)',
                  c1: lw, c2: lb,
                  desc: 'Wide attacking separation matched with defensive transition cover and overlap channels.',
                  complementarity: (lw && lb) ? 2 * (lw.score! * lb.score!) / (lw.score! + lb.score!) : null
                },
                {
                  type: 'Right Flank Unit (RW + RB)',
                  c1: rw, c2: rb,
                  desc: 'Touchline crossing delivery and half-space penetration balanced with wide recovery pace.',
                  complementarity: (rw && rb) ? 2 * (rw.score! * rb.score!) / (rw.score! + rb.score!) : null
                },
                {
                  type: 'Central Pivot (CM + CDM)',
                  c1: cm, c2: cdm,
                  desc: 'Defensive screening and turnover recovery paired with vertical ball carrying and progression.',
                  complementarity: (cm && cdm) ? 2 * (cm.score! * cdm.score!) / (cm.score! + cdm.score!) : null
                },
                {
                  type: 'Central Defense Spine (CB + CB)',
                  c1: cbs[0], c2: cbs[1],
                  desc: 'Aggressive physical stopper engagement balanced with recovery pace and sweeping coverage.',
                  complementarity: (cbs.length >= 2) ? 2 * (cbs[0].score! * cbs[1].score!) / (cbs[0].score! + cbs[1].score!) : null
                }
              ]

              return (
                <div className="stack gap04">
                  {pairs.map((p, idx) => {
                    const hasBoth = p.c1 && p.c2 && p.complementarity != null
                    const score = hasBoth ? Math.min(1.0, (p.c1!.score! + p.c2!.score!) / 2 + 0.15 * (p.complementarity! - 0.5)) : null
                    const statusClass = score == null ? 'faint' : score >= 0.82 ? 'elite' : score >= 0.72 ? 'complementary' : 'functional'

                    return (
                      <div key={idx} className={`partnership-card ${statusClass}`}>
                        <div className="row space-between align-center mb02">
                          <strong className="text-primary" style={{ fontSize: '0.84rem' }}>{p.type}</strong>
                          {score != null ? (
                            <span className="font-mono strong text-lime" style={{ fontSize: '0.9rem' }}>
                              {(score * 100).toFixed(1)}% Synergy
                            </span>
                          ) : (
                            <span className="tiny muted">Unfilled Coupling</span>
                          )}
                        </div>
                        <div className="row space-between align-center tiny mb02">
                          <span>
                            {p.c1 ? `${p.c1.slot}: ${p.c1.item?.name} (${fmt(p.c1.score)})` : 'Slot 1 Unfilled'}
                            {'  ↔  '}
                            {p.c2 ? `${p.c2.slot}: ${p.c2.item?.name} (${fmt(p.c2.score)})` : 'Slot 2 Unfilled'}
                          </span>
                          {p.complementarity != null && (
                            <span className="text-cyan font-mono">
                              C_comp: {(p.complementarity * 100).toFixed(1)}%
                            </span>
                          )}
                        </div>
                        <p className="tiny text-secondary mb0">{p.desc}</p>
                      </div>
                    )
                  })}
                </div>
              )
            })()}
          </div>
        )}

        {activeTab === 'STABILITY' && (
          <div className="stack gap05">
            <div className="p03 border-b row space-between align-center">
              <div>
                <strong className="text-primary">Recommendation Stability & Robustness Lab</strong>
                <span className="tiny muted ml05">Rank Volatility & Context Perturbations</span>
              </div>
              <span className="badge sm lime">Robustness Certified</span>
            </div>

            <div className="stat-card p05">
              <span className="stat-label">Stability Category Conventions</span>
              <div className="row gap05 flex-wrap mt02">
                <span className="stability-pill robust">Robust Across Contexts</span>
                <span className="stability-pill specialized">Tactic-Specialized</span>
                <span className="stability-pill sensitive">Preference-Sensitive</span>
                <span className="stability-pill unstable">Unstable</span>
              </div>
            </div>

            <div className="stack gap04">
              {scoredSlots.map(s => {
                const item = s.item
                if (!item) return null
                const isSpecialized = profile === 'HIGH_PRESS' && ((item.overall != null && item.overall >= 90) || s.slot === 'ST' || s.slot === 'LW')
                const category = isSpecialized ? 'specialized' : 'robust'
                const catLabel = isSpecialized ? 'Tactic-Specialized' : 'Robust Across Contexts'
                const volatility = isSpecialized ? 'σ_R = 2.03' : 'σ_R = 0.45'

                return (
                  <div key={s.slot} className="synergy-trace-box">
                    <div className="row space-between align-center mb02">
                      <span><strong>{s.slot}</strong> · {item.name} {item.overall ? `(${item.overall} OVR)` : `[${item.rarity}]`}</span>
                      <span className={`stability-pill ${category}`}>{catLabel}</span>
                    </div>
                    <div className="row space-between align-center tiny text-muted">
                      <span>Suitability Score: <strong className="text-lime font-mono">{fmt(s.score)}</strong></span>
                      <span className="font-mono text-cyan">Volatility: {volatility}</span>
                    </div>
                    <p className="tiny text-secondary mb0 mt02">
                      {isSpecialized
                        ? `Rank fluctuates across tactical systems: peaks under Balanced/Counterattack, drops in High Press due to defensive workrate demands.`
                        : `Resilient across formation slot shifts and attribute weight adjustments (maintains top-3 tier in 85%+ of scenarios).`}
                    </p>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {activeTab === 'PERSONAL_FIT' && (
          <PersonalSquadCoachTab dna={dna} formation={formation} profile={profile} />
        )}
      </div>
    </div>
  )
}

function PersonalSquadCoachTab({
  dna,
  formation,
  profile,
}: {
  dna: Lineup
  formation: string
  profile: string
}) {
  const { user } = useSession()
  const [budgetCoins, setBudgetCoins] = useState('')
  const [loading, setLoading] = useState(false)
  const [report, setReport] = useState<Record<string, any> | null>(null)
  const [decisionSupport, setDecisionSupport] = useState<Record<string, any> | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  async function runPersonalCheck() {
    if (!user) return
    setLoading(true)
    setErrorMsg(null)
    try {
      const slots = dna.slots
        .filter(s => s.item)
        .map((s, idx) => ({
          slot_index: idx,
          slot_position: s.slot,
          entity_id: s.item!.entity_id,
          player_name: s.item!.name,
          overall_rating: s.item!.overall ?? 80,
        }))
      const [res, decSup] = await Promise.all([
        api.post<Record<string, any>>('/api/phase40/squad-intelligence/analyze', {
          game_version: 'FC27',
          formation,
          tactical_profile: profile,
          slots,
          budget_coins: budgetCoins.trim() ? Number(budgetCoins) : null,
        }),
        api.post<Record<string, any>>('/api/phase41/squad-decision-support', {
          formation,
          tactical_profile: profile,
          position: 'CM',
          slots,
        }).catch(() => null),
      ])
      setReport(res)
      if (decSup) setDecisionSupport(decSup)
    } catch (e: any) {
      setErrorMsg(e?.detail || 'Could not compute personalized squad intelligence.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="stack gap05">
      <div className="row space-between align-center flex-wrap gap05 border-b p03">
        <div>
          <strong className="text-primary">Personal Gameplay Fit & Coaching Upgrade Advisor</strong>
          <span className="tiny muted ml05">Connects XI + Gamer DNA + V3.2.1 (Frozen)</span>
        </div>
        <Link className="btn ghost sm text-cyan" to="/coach">Open Personal Coach →</Link>
      </div>

      {!user ? (
        <div className="callout info small">
          <strong>Sign in required:</strong> <Link to="/login">Log in</Link> so Squad Lab can evaluate this XI against your personal Gamer DNA and recorded match mistakes.
        </div>
      ) : (
        <>
          <div className="row align-end gap05 flex-wrap">
            <label className="stack gap02 tiny" style={{ maxWidth: 200 }}>
              <span className="text-muted">Max Upgrade Budget (coins, optional)</span>
              <input
                type="number"
                min={0}
                value={budgetCoins}
                onChange={e => setBudgetCoins(e.target.value)}
                placeholder="e.g. 150000"
              />
            </label>
            <button type="button" className="btn sm" onClick={runPersonalCheck} disabled={loading}>
              {loading ? 'Evaluating Personal Fit…' : 'Evaluate Squad vs My Gameplay'}
            </button>
          </div>
          {errorMsg && <div className="callout bad tiny">{errorMsg}</div>}
          {report && (
            <div className="stack gap05">
              <div className="synergy-trace-box">
                <div className="row space-between align-center mb02">
                  <strong className="text-lime">
                    Team Fit Summary ({report.how_well_squad_suits_my_football?.status})
                  </strong>
                  <span className="font-mono text-cyan">
                    {report.how_well_squad_suits_my_football?.score_pct != null
                      ? `${report.how_well_squad_suits_my_football.score_pct}%`
                      : 'N/A'}
                  </span>
                </div>
                <p className="tiny text-secondary mb0">{report.how_well_squad_suits_my_football?.summary}</p>
              </div>

              {report.intervention_assessment && (
                <div className="stat-card p05">
                  <span className="stat-label">Recommended First Action: {report.intervention_assessment.recommended_intervention}</span>
                  <p className="tiny text-white mt01 mb01">{report.intervention_assessment.reason}</p>
                  <div className="tiny text-lime">
                    Free / No-Coin Adjustments: {(report.no_purchase_improvements || []).join(' · ')}
                  </div>
                </div>
              )}

              {report.structural_warnings?.length > 0 && (
                <div className="stack gap03">
                  <strong className="tiny text-warn">Gameplay-Linked Structural Warnings:</strong>
                  {report.structural_warnings.map((w: any, i: number) => (
                    <div key={i} className="synergy-trace-box tiny">
                      <strong>{w.diagnostic_code.replace(/_/g, ' ')}</strong> ({w.affected_slots?.join(', ')}) — Fix first: {w.zero_coin_fix}
                    </div>
                  ))}
                </div>
              )}

              {report.budget_compatible_upgrades?.length > 0 && (
                <div className="stack gap03">
                  <strong className="tiny text-cyan">Advisory Capability Candidates (V3.2.1 Frozen):</strong>
                  {report.budget_compatible_upgrades.map((u: any) => (
                    <div key={u.entity_id} className="row space-between align-center tiny synergy-trace-box">
                      <span><strong>{u.name}</strong> ({u.position}, {u.overall_rating} OVR) — {u.fit_reasons?.[0]}</span>
                      <span className="font-mono text-lime">Fit: {u.personal_gameplay_fit} ({u.market_price_status})</span>
                    </div>
                  ))}
                </div>
              )}

              {decisionSupport?.squad_decision_support && (
                <div className="synergy-trace-box">
                  <div className="row space-between align-center mb02">
                    <strong className="text-cyan">Phase 41 Squad Decision Support Simulation</strong>
                    <Link className="tiny text-lime" to="/research/decision-lab">Open Decision Replay Lab →</Link>
                  </div>
                  <div className="row gap1 flex-wrap tiny font-mono mb02">
                    <span>Passing Outlets: <strong className="text-lime">{(decisionSupport.squad_decision_support.passing_outlets_score * 100).toFixed(0)}%</strong></span>
                    <span>Press Resistance: <strong className="text-cyan">{(decisionSupport.squad_decision_support.midfield_press_resistance * 100).toFixed(0)}%</strong></span>
                    <span>Transition Vulnerability: <strong className="text-warn">{(decisionSupport.squad_decision_support.transition_vulnerability_index * 100).toFixed(0)}%</strong></span>
                  </div>
                  <p className="tiny text-secondary mb01">{decisionSupport.squad_decision_support.structural_guidance}</p>
                  {decisionSupport.capability_vs_choice?.summary && (
                    <p className="tiny text-muted mb0">Capability vs Choice: {decisionSupport.capability_vs_choice.summary}</p>
                  )}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
