import { Link } from 'react-router-dom'
import { useSession } from '../state/session'
import { useApi } from '../lib/useApi'

interface Ready { game_players: number; playstyles: number; ut_cards: number; [k: string]: unknown }

export default function Landing() {
  const { versions, user } = useSession()
  const ready = useApi<Ready>('/api/health/ready')
  const fc26 = versions.find((v) => v.code === 'FC26')
  const fc27 = versions.find((v) => v.code === 'FC27')

  return (
    <div>
      <section className="hero">
        <div className="row mb2">
          <span className="badge ok">FC26 · {fc26?.status ?? 'ACTIVE'}</span>
          <span className="badge unknown">FC27 · {fc27?.status ?? 'NO_DATA'} — architecture ready, zero fabricated records</span>
        </div>
        <h1>Player quality is not <em>player suitability</em>.</h1>
        <p className="lede">
          A 91-rated striker can be the wrong signing for your 4-2-3-1 press.
          This platform scores every candidate against <strong>your</strong> position,
          tactics, attributes, PlayStyles, budget and squad links — deterministically,
          with the evidence for every score shown next to it.
        </p>
        <div className="row mt2">
          <Link className="btn primary" to="/recommend">Find my best-fit player</Link>
          <Link className="btn" to="/search">Browse {ready.data ? ready.data.game_players.toLocaleString() : '16,228+'} FC26 players</Link>
          {user && <Link className="btn ghost" to="/squads">Open squad builder</Link>}
        </div>
      </section>

      <section className="stat-strip mb2">
        <div className="stat">
          <div className="n">{ready.loading ? '…' : ready.data ? ready.data.game_players.toLocaleString() : '—'}</div>
          <div className="l">FC26 players ingested</div>
        </div>
        <div className="stat">
          <div className="n">{ready.data ? ready.data.playstyles.toLocaleString() : '—'}</div>
          <div className="l">PlayStyle links (real)</div>
        </div>
        <div className="stat">
          <div className="n">7</div>
          <div className="l">Scored fit components</div>
        </div>
        <div className="stat">
          <div className="n">0</div>
          <div className="l">Fabricated values — ever</div>
        </div>
      </section>

      <div className="grid g3">
        <div className="card">
          <div className="section-title">Explainable scoring</div>
          <p className="small muted mb0">
            Weighted components — attribute fit 30%, overall quality 15%, position 15%,
            tactics 15%, PlayStyles 15%, team fit 10% — every weight visible, every
            UNKNOWN component excluded from the score instead of penalizing the player.
            Same request → same ranking, always.
          </p>
        </div>
        <div className="card">
          <div className="section-title">Version-aware by design</div>
          <p className="small muted mb0">
            FC26 and FC27 never mix. FC27 currently has <strong>NO_DATA</strong>: the
            schema, ingestion pipeline and API paths are ready, and the UI says so
            explicitly instead of quietly showing you FC26 players.
          </p>
        </div>
        <div className="card">
          <div className="section-title">Honest about gaps</div>
          <p className="small muted mb0">
            Market prices, chemistry rules and Role data are not verified for this
            dataset, so they are surfaced as UNKNOWN — never invented. Provenance and
            the last observation date are shown on every player page.
          </p>
        </div>
      </div>

      <div className="card mt2">
        <div className="section-title">What you can do</div>
        <div className="grid g2">
          <ul className="reasons good small muted">
            <li><strong>Search</strong> 16k+ players with position, OVR, nation, league and PlayStyle filters.</li>
            <li><strong>Recommend</strong> the best-fit player for a position, formation and tactical profile — with reasons and concerns.</li>
            <li><strong>Compare</strong> up to four players side by side, ranked for your exact request.</li>
          </ul>
          <ul className="reasons good small muted">
            <li><strong>Squad builder</strong> with real link facts (club/league/nation) and slot-level replacement suggestions.</li>
            <li><strong>Save</strong> players and keep a profile with preferences.</li>
            <li><strong>Feedback</strong> buttons on every recommendation feed future learning-to-rank — labeled by real users only.</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
