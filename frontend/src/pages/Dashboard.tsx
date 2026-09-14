import { Link } from 'react-router-dom'
import { useSession } from '../state/session'
import { useApi } from '../lib/useApi'
import { qs } from '../api/client'
import type { ReferenceData, SquadSummary } from '../api/types'
import { ErrorBox, Loading } from '../components/common'
import { dateShort } from '../lib/format'

interface SavedList { items: unknown[]; total: number }

export default function Dashboard() {
  const { user, gameVersion, versions } = useSession()
  const ref = useApi<ReferenceData>(`/api/meta/reference${qs({ game_version: gameVersion })}`, [gameVersion])
  const squads = useApi<SquadSummary[]>('/api/squads')
  const saved = useApi<SavedList>('/api/saved-players')
  const active = versions.find((v) => v.code === gameVersion)

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="mb0">Dashboard</h1>
          <div className="sub small">
            Signed in as <strong>{user?.email}</strong> · viewing <strong>{gameVersion}</strong> data
          </div>
        </div>
      </div>

      <ErrorBox error={ref.error} onRetry={ref.reload} />

      <div className="grid g3 mb2">
        <div className="card">
          <div className="section-title">{gameVersion} status</div>
          {ref.loading ? <Loading label="Loading reference" /> : (
            <>
              <div className="row mb1">
                <span className={`badge ${ref.data?.status === 'ACTIVE' ? 'ok' : 'unknown'}`}>
                  {ref.data?.status ?? 'UNKNOWN'}
                </span>
                {active?.released_on && (
                  <span className="tiny faint">released {dateShort(active.released_on)}</span>
                )}
              </div>
              {ref.data?.status === 'ACTIVE' ? (
                <p className="small muted mb0">
                  {ref.data.positions.length} positions · {ref.data.playstyles.length} PlayStyles ·{' '}
                  {Object.keys(ref.data.formations).length} formations available for
                  recommendations and squad building.
                </p>
              ) : (
                <p className="small muted mb0">
                  NO_DATA: the architecture supports {gameVersion}, but zero production
                  records have been ingested. Nothing is fabricated — switch to FC26 or
                  wait for a legitimate data drop.
                </p>
              )}
            </>
          )}
        </div>

        <div className="card">
          <div className="section-title">Capability honesty flags</div>
          {ref.loading ? <Loading /> : (
            <ul className="reasons small muted mb0" style={{ listStyle: 'none', padding: 0 }}>
              {Object.entries(ref.data?.capabilities ?? {}).map(([k, v]) => (
                <li key={k} className="row" style={{ justifyContent: 'space-between', padding: '.15rem 0' }}>
                  <span>{k.replace(/_/g, ' ')}</span>
                  <span className={`badge ${v ? 'ok' : 'unknown'}`}>{v ? 'AVAILABLE' : 'NOT VERIFIED'}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card">
          <div className="section-title">Your library</div>
          <div className="kv">
            <dt>Squads</dt>
            <dd className="mono">{squads.loading ? '…' : squads.data?.length ?? '—'}</dd>
            <dt>Saved players</dt>
            <dd className="mono">{saved.loading ? '…' : saved.data?.total ?? '—'}</dd>
          </div>
          <div className="row mt2">
            <Link className="btn sm" to="/squads">Squad builder</Link>
            <Link className="btn sm ghost" to="/saved">Saved</Link>
            <Link className="btn sm ghost" to="/profile">Profile</Link>
          </div>
        </div>
      </div>

      <div className="grid g2">
        <div className="card">
          <div className="section-title">Start a recommendation</div>
          <p className="small muted">
            Tell the engine the position, formation and tactical profile — it scores
            every {gameVersion === 'FC26' ? 'FC26' : gameVersion} candidate deterministically and shows its evidence.
          </p>
          <div className="row">
            <Link className="btn primary" to="/recommend">Open workflow</Link>
            <Link className="btn ghost" to="/compare">Compare players</Link>
          </div>
        </div>
        <div className="card">
          <div className="section-title">Recent squads</div>
          {squads.loading ? <Loading /> : (squads.data?.length ?? 0) === 0 ? (
            <p className="small muted mb0">
              No squads yet. Create one to evaluate links and get slot-level
              replacement suggestions in squad context.
            </p>
          ) : (
            <div className="col">
              {squads.data!.slice(0, 4).map((s) => (
                <Link key={s.id} className="card tight hover" to={`/squads/${s.id}`}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <strong>{s.name}</strong>
                    <span className="tiny faint">{s.formation} · {s.game_version} · {s.filled_slots}/11 filled</span>
                  </div>
                </Link>
              ))}
            </div>
          )}
          <ErrorBox error={squads.error} />
        </div>
      </div>
    </div>
  )
}
