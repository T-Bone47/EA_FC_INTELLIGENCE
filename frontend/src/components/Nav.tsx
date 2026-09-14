import { NavLink, useNavigate } from 'react-router-dom'
import { useSession } from '../state/session'
import type { GameVersion } from '../api/types'

export function VersionSwitch() {
  const { gameVersion, setGameVersion, versions } = useSession()
  const list = versions.length ? versions : [{ code: 'FC26' }, { code: 'FC27' }]
  return (
    <div className="chips" role="group" aria-label="Game version">
      {list.map((v) => {
        const on = v.code === gameVersion
        const noData = (v as any).status === 'NO_DATA'
        return (
          <button key={v.code} type="button"
                  className={`chip ${on ? 'on' : ''}`}
                  title={noData ? `${v.code}: architecture ready, NO data ingested — nothing is fabricated` : v.code}
                  onClick={() => setGameVersion(v.code as GameVersion)}>
            {v.code}{noData && <span className="faint"> · no data</span>}
          </button>
        )
      })}
    </div>
  )
}

export function Nav() {
  const { user, logout } = useSession()
  const nav = useNavigate()
  return (
    <header className="topbar">
      <NavLink to="/" className="brand">
        <span className="brand-mark" aria-hidden="true">PI</span>
        <span>
          EA FC Player Intelligence
          <small>suitability ≠ quality</small>
        </span>
      </NavLink>
      <nav className="nav" aria-label="Main">
        <NavLink to="/search" className={({isActive}) => isActive ? "active" : ""}>Search</NavLink>
        <NavLink to="/recommend" className={({isActive}) => isActive ? "active" : ""}>Recommend</NavLink>
        <NavLink to="/cards" className={({isActive}) => isActive ? "active" : ""}>Cards</NavLink>
        <NavLink to="/compare" className={({isActive}) => isActive ? "active" : ""}>Compare</NavLink>
        <NavLink to="/squads" className={({isActive}) => isActive ? "active" : ""}>Squads</NavLink>
        {user && <NavLink to="/saved" className={({isActive}) => isActive ? "active" : ""}>Saved</NavLink>}
      </nav>
      <div className="topbar-right">
        <VersionSwitch />
        {user ? (
          <>
            <NavLink to="/profile" className="btn ghost sm" title={user.email}>
              {user.display_name || user.email.split('@')[0]}
            </NavLink>
            <button type="button" className="btn ghost sm"
                    onClick={async () => { await logout(); nav('/') }}>
              Log out
            </button>
          </>
        ) : (
          <>
            <NavLink to="/login" className="btn ghost sm">Log in</NavLink>
            <NavLink to="/signup" className="btn primary sm">Sign up</NavLink>
          </>
        )}
      </div>
    </header>
  )
}

export function Toasts() {
  const { toasts, dismiss } = useSession()
  if (!toasts.length) return null
  return (
    <div style={{ position: 'fixed', bottom: 16, right: 16, zIndex: 80,
                  display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 380 }}>
      {toasts.map((t) => (
        <div key={t.id} className={`callout ${t.kind === 'ok' ? 'ok' : t.kind === 'bad' ? 'bad' : 'info'}`}
             style={{ boxShadow: 'var(--shadow)', cursor: 'pointer' }} onClick={() => dismiss(t.id)}
             role="status">
          <div className="small">{t.text}</div>
          {t.rid && <div className="rid mono tiny">request_id: {t.rid}</div>}
        </div>
      ))}
    </div>
  )
}
