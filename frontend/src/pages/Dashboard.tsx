import { Link } from 'react-router-dom'
import { ReleaseSummary } from '../components/Availability'
import { useSession } from '../state/session'
import { useApi } from '../lib/useApi'
import type { SquadSummary } from '../api/types'
import { ErrorBox, Loading } from '../components/common'
import { StadiumPitch } from '../components/StadiumPitch'
import { StadiumIcon, type StadiumIconName } from '../components/StadiumIcons'
import { EpistemicChip } from '../components/ui/StadiumPrimitives'
import { recentAnalyses } from '../lib/recentAnalyses'
import type { RecommendationOptions, StatedFootballStyle } from '../intelligence/types'

const modules: { title: string; detail: string; to: string; icon: StadiumIconName; badge: string }[] = [
  { title: 'Discover players', detail: 'Search the verified player and card catalogues with 6-facet attributes and PlayStyles.', to: '/search', icon: 'search', badge: 'Scouting' },
  { title: 'Tactical intelligence', detail: 'Find eligible players ranked deterministically for your formation and tactical profile.', to: '/intelligence', icon: 'intelligence', badge: 'Suitability' },
  { title: 'Optimize my squad', detail: 'Test full 11-player lineups, smart slot upgrades, and tactical pitch replacements.', to: '/cards/squad-lab', icon: 'squad', badge: 'Squad Lab' },
  { title: 'Compare card versions', detail: 'Inspect radar facet polygons, attribute delta matrices, and evidence coverage.', to: '/compare?scope=cards', icon: 'compare', badge: 'Head-to-Head' },
  { title: 'Personal AI coach', detail: 'Ask evidence-grounded tactical questions, view Gamer DNA, and follow structured drills.', to: '/coach', icon: 'coach', badge: 'Coach & DNA' },
  { title: 'Tactical Experiment Lab', detail: 'Run Bayesian single-variable experiments, inspect formation shape deltas, and triage roles.', to: '/tactical-lab', icon: 'sliders', badge: 'Experiments' },
  { title: 'Gameplay Studio', detail: 'Process recorded FC26/FC27 matches, inspect 2D radar replay, and calibrate parameters.', to: '/research/gameplay-studio', icon: 'video', badge: 'Match Vision' },
  { title: 'Decision Replay Lab', detail: 'Review key pre-action frames, blind tactical quizzes, and counterfactual Football IQ alternatives.', to: '/research/decision-lab', icon: 'decision', badge: 'Football IQ' },
]

const QUICK_ARCHETYPES = [
  { label: 'Direct Attacking', profile: 'DIRECT_ATTACKING' },
  { label: 'High Pressing', profile: 'HIGH_PRESSING' },
  { label: 'Possession Buildup', profile: 'POSSESSION' },
  { label: 'Wing Play', profile: 'WING_PLAY' },
  { label: 'Low Block Counter', profile: 'LOW_BLOCK_COUNTER' },
]

export default function Dashboard() {
  const { user, gameVersion, availability, availabilityLoading, refreshAvailability } = useSession()
  const options = useApi<RecommendationOptions>('/api/v3/options')
  const squads = useApi<SquadSummary[]>(user ? '/api/squads' : null)
  const saved = useApi<{ total: number }>(user ? '/api/saved-players' : null)
  const style = user?.preferences?.football_style as StatedFootballStyle | undefined
  const analyses = recentAnalyses(user?.id ?? 'guest')

  return (
    <div className="stack" style={{ gap: '1.75rem' }}>
      {/* Command Center Hero */}
      <section className="card overview-hero" style={{ position: 'relative', overflow: 'hidden' }}>
        <div>
          <div className="row align-center gap05 mb1">
            <EpistemicChip kind="frozen" label="STADIUM 3.0 · V3.2.1 ENGINE" />
            <span className="badge info">{gameVersion} Workspace</span>
          </div>
          <h1>Build a smarter squad. Play your football.</h1>
          <p className="muted" style={{ fontSize: '0.98rem', lineHeight: 1.55, maxWidth: '64ch' }}>
            Identify players built for your tactical setup and verify the real ratings, PlayStyles, and empirical match evidence behind every ranking.
          </p>
          <div className="row mt2" style={{ gap: '0.75rem', flexWrap: 'wrap' }}>
            <Link className="btn primary" to="/intelligence">Find my best fit</Link>
            <Link className="btn ghost" to="/cards/squad-lab">Open Squad Lab</Link>
            <Link className="btn ghost" to="/search">Browse Catalogue</Link>
            <Link className="btn ghost" to="/coach">Ask Personal Coach</Link>
          </div>

          {/* Quick-Start Tactical Archetypes */}
          <div className="mt2" style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '0.85rem' }}>
            <span className="tiny faint" style={{ textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: '0.4rem' }}>
              Quick-Launch Tactical Archetypes
            </span>
            <div className="chips">
              {QUICK_ARCHETYPES.map((arc) => (
                <Link
                  key={arc.profile}
                  to={`/intelligence?tactical_profile=${arc.profile}`}
                  className="chip archetype-quick-chip"
                  title={`Launch Intelligence Studio with ${arc.label}`}
                >
                  <StadiumIcon name="zap" size={12} />
                  <span>{arc.label}</span>
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Formation Preview Visual */}
        <div aria-label="4-3-3 formation preview" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <p className="section-title mb0">4-3-3 formation preview</p>
            <span className="tiny faint mono">Tactical Cockpit</span>
          </div>
          <StadiumPitch
            slots={options.data?.formations?.['4-3-3'] ?? []}
            render={slot => <span className="pitch-preview-slot">{slot.slot}</span>}
          />
        </div>
      </section>

      {/* Primary Workflows Pipeline */}
      <section>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '0.85rem' }}>
          <div>
            <h2 className="mb0">Primary workflows</h2>
            <span className="small muted">Core football intelligence stages across squad building, gameplay vision, and coaching.</span>
          </div>
        </div>
        <div className="overview-modules" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 16rem), 1fr))' }}>
          {modules.map(item => (
            <Link className="card overview-module hover-elevate" key={item.to} to={item.to} style={{ textDecoration: 'none' }}>
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                <span className="module-mark" aria-hidden="true">
                  <StadiumIcon name={item.icon} size={16} />
                </span>
                <span className="badge" style={{ fontSize: '0.72rem', fontFamily: 'var(--mono)' }}>{item.badge}</span>
              </div>
              <h3 className="mb0" style={{ fontSize: '1.05rem', color: 'var(--text-primary)' }}>{item.title}</h3>
              <span className="muted small" style={{ lineHeight: 1.45 }}>{item.detail}</span>
              <span className="tiny font-semibold mt1 row align-center gap03" style={{ color: 'var(--accent-lime)' }}>
                <span>Open workflow</span>
                <StadiumIcon name="arrowRight" size={12} />
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* Operational Cockpit & Recent Workspace */}
      <div className="overview-detail">
        <div className="stack" style={{ gap: '1.25rem' }}>
          {/* Recent Analyses Block */}
          <section className="card">
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <h2 className="mb0" style={{ fontSize: '1.15rem' }}>Recent analyses</h2>
              <span className="tiny faint mono">{analyses.length} cached</span>
            </div>
            {analyses.length ? (
              <ul className="overview-history">
                {analyses.map((entry, i) => (
                  <li key={entry.completed + '-' + i} style={{ alignItems: 'center' }}>
                    <div>
                      <Link to={`/intelligence?position=${entry.position}&tactical_profile=${entry.tactic}&game_version=${entry.version}`}>
                        <strong>{entry.position} · {entry.tactic.replace(/_/g, ' ')}</strong>
                      </Link>
                      <div className="muted tiny">{[entry.version, entry.formation, entry.slot].filter(Boolean).join(' · ')}</div>
                    </div>
                    <Link
                      to={`/intelligence?position=${entry.position}&tactical_profile=${entry.tactic}&game_version=${entry.version}`}
                      className="btn ghost sm"
                    >
                      Re-run
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small mb0">Completed recommendations from this browser session appear here.</p>
            )}
          </section>

          {/* Saved Squads Block */}
          <section className="card">
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <h2 className="mb0" style={{ fontSize: '1.15rem' }}>Saved squads</h2>
              {user && <Link to="/squads" className="tiny faint">Manage all ({squads.data?.length ?? 0})</Link>}
            </div>
            {user ? (
              <>
                <ErrorBox error={squads.error} onRetry={squads.reload} />
                {squads.loading ? (
                  <Loading label="Loading your squads" />
                ) : squads.data?.length ? (
                  <ul className="overview-history">
                    {squads.data.slice(0, 4).map(squad => (
                      <li key={squad.id} style={{ alignItems: 'center' }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <Link to={`/squads/${squad.id}`}><strong>{squad.name}</strong></Link>
                          <div className="muted tiny">{squad.game_version} · {squad.formation} · {squad.filled_slots}/11 filled</div>
                          <div className="bar mt1" style={{ maxWidth: 160, height: 4 }}>
                            <span style={{ width: `${(squad.filled_slots / 11) * 100}%` }} />
                          </div>
                        </div>
                        <Link to={`/squads/${squad.id}`} className="btn ghost sm">
                          Open
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : !squads.error && (
                  <div className="empty tight" style={{ padding: '1.25rem 0.5rem' }}>
                    <p className="muted small mb1">Create a squad to assign formation slots and test tactical fit.</p>
                    <Link to="/squads" className="btn ghost sm">+ Create first squad</Link>
                  </div>
                )}
                <div className="row mt2" style={{ gap: '0.5rem' }}>
                  <Link className="btn ghost sm" to="/squads">Manage squads</Link>
                  <Link className="btn ghost sm" to="/saved">Saved players{saved.data ? ` (${saved.data.total})` : ''}</Link>
                </div>
              </>
            ) : (
              <div className="empty tight" style={{ padding: '1.5rem 0.5rem' }}>
                <p className="muted small mb1">Sign in to save squads, track shortlists, and store tactical preferences.</p>
                <div className="row gap05" style={{ justifyContent: 'center' }}>
                  <Link className="btn primary sm" to="/login" state={{ from: '/' }}>Sign in</Link>
                  <Link className="btn ghost sm" to="/signup" state={{ from: '/' }}>Create account</Link>
                </div>
              </div>
            )}
          </section>
        </div>

        <div className="stack" style={{ gap: '1.25rem' }}>
          {/* Research Data Availability Block */}
          <section className="card stack">
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 className="mb0" style={{ fontSize: '1.15rem' }}>Research data availability</h2>
              <span className={`badge ${availability?.database_status === 'CONNECTED' ? 'ok' : 'warn'}`}>
                {availability?.database_status ?? 'DISCONNECTED'}
              </span>
            </div>
            {availabilityLoading && <Loading label="Checking data releases" />}
            {availability?.database_status === 'CONNECTED' ? (
              <div className="col gap05">
                {Object.entries(availability.versions).map(([version, scopes]) => (
                  <div key={version} className="st3-inset-panel">
                    <div className="row" style={{ justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                      <strong className="mono" style={{ color: 'var(--accent-cyan)' }}>{version}</strong>
                      <span className="tiny faint">{version === 'FC26' ? 'Production Canonical' : 'Research Cohort'}</span>
                    </div>
                    <div className="small faint">Players · <ReleaseSummary release={scopes.game_player.research ?? scopes.game_player.local ?? scopes.game_player.production} /></div>
                    <div className="small faint mt05">Cards · <ReleaseSummary release={scopes.ut_card.research ?? scopes.ut_card.local ?? scopes.ut_card.production} /></div>
                  </div>
                ))}
              </div>
            ) : !availabilityLoading && (
              <p className="muted small">{availability ? 'Database not connected.' : 'Availability check unavailable.'}</p>
            )}
            <div className="row mt1" style={{ gap: '0.5rem' }}>
              <button className="btn ghost sm" type="button" onClick={refreshAvailability}>Refresh release status</button>
              <Link to="/cards/performance" className="btn ghost sm">Open Evidence Lab</Link>
            </div>
          </section>

          {/* Saved Tactical Preferences */}
          <section className="card">
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.65rem' }}>
              <h2 className="mb0" style={{ fontSize: '1.15rem' }}>Tactical preferences</h2>
              <Link to="/profile" className="tiny faint">Edit</Link>
            </div>
            {style && (style.position || style.tactical_profile) ? (
              <div className="st3-inset-panel">
                <div className="row align-center gap05">
                  <span className="badge accent">{style.position ?? 'Any'}</span>
                  <strong style={{ fontSize: '0.9rem' }}>{style.tactical_profile?.replace(/_/g, ' ')}</strong>
                </div>
                <div className="tiny faint mt1">Bound to {gameVersion} intelligence queries</div>
              </div>
            ) : (
              <p className="muted small">No saved tactical preferences configured for {gameVersion}. Set your preferred position and style in your profile.</p>
            )}
            <Link to="/profile" className="btn ghost sm mt1">Manage preferences</Link>
          </section>
        </div>
      </div>
    </div>
  )
}
