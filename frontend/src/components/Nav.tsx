import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useSession } from '../state/session'
import { useCopilot } from '../state/copilot'
import { useRelease } from './Availability'
import { StadiumIcon, type StadiumIconName } from './StadiumIcons'
import type { GameVersion } from '../api/types'

export function VersionSwitch() {
  const { gameVersion, setGameVersion, versions } = useSession()
  const list = versions.length ? versions.map(v => v.code) : ['FC26', 'FC27']
  return (
    <div className="chips" role="group" aria-label="Game version">
      {list.map(v => (
        <button
          key={v}
          type="button"
          className={`chip ${v === gameVersion ? 'on' : ''}`}
          aria-pressed={v === gameVersion}
          onClick={() => setGameVersion(v as GameVersion)}
        >
          {v}
        </button>
      ))}
    </div>
  )
}

interface NavDestination {
  to: string
  title: string
  icon: StadiumIconName
  subtitle: string
  paths: string[]
  group: string
}

const navGroups: { label: string; items: NavDestination[] }[] = [
  {
    label: 'Overview',
    items: [
      { to: '/', title: 'Overview', icon: 'dashboard', subtitle: 'Performance summary', paths: ['/dashboard'], group: 'Overview' },
    ],
  },
  {
    label: 'Build',
    items: [
      { to: '/search', title: 'Discover', icon: 'search', subtitle: 'Scouting catalogue', paths: ['/search', '/players', '/cards'], group: 'Build' },
      { to: '/intelligence', title: 'Intelligence', icon: 'intelligence', subtitle: 'V3.2.1 player fit', paths: ['/intelligence', '/recommend'], group: 'Build' },
      { to: '/cards/squad-lab', title: 'Squad Lab', icon: 'squad', subtitle: 'Tactical pitch cockpit', paths: ['/cards/squad-lab', '/squads'], group: 'Build' },
      { to: '/compare', title: 'Compare', icon: 'compare', subtitle: 'Head-to-head metrics', paths: ['/compare'], group: 'Build' },
    ],
  },
  {
    label: 'Play & Improve',
    items: [
      { to: '/coach', title: 'Personal Coach', icon: 'coach', subtitle: 'AI coach & Gamer DNA', paths: ['/coach'], group: 'Play & Improve' },
      { to: '/research/gameplay-studio', title: 'Gameplay Studio', icon: 'video', subtitle: 'Match video & telemetry', paths: ['/research/gameplay-studio', '/gameplay-studio'], group: 'Play & Improve' },
      { to: '/research/decision-lab', title: 'Decision Lab', icon: 'decision', subtitle: 'Counterfactual & Football IQ', paths: ['/research/decision-lab'], group: 'Play & Improve' },
    ],
  },
  {
    label: 'Research',
    items: [
      { to: '/cards/performance', title: 'Evidence Lab', icon: 'evidence', subtitle: 'Empirical calibration', paths: ['/cards/performance'], group: 'Research' },
    ],
  },
  {
    label: 'Settings',
    items: [
      { to: '/profile', title: 'Profile', icon: 'user', subtitle: 'Account & preferences', paths: ['/profile', '/saved'], group: 'Settings' },
    ],
  },
]

const destinations = navGroups.flatMap(g => g.items)

export function Nav() {
  const { user, logout, gameVersion, setGameVersion, researchOptIn, setResearchOptIn } = useSession()
  const players = useRelease('game_player', gameVersion)
  const cards = useRelease('ut_card', gameVersion)
  const navigate = useNavigate()
  const loc = useLocation()
  const [open, setOpen] = useState(false)
  const [compact, setCompact] = useState(false)
  const [query, setQuery] = useState('')
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [paletteQuery, setPaletteQuery] = useState('')
  const [paletteIdx, setPaletteIdx] = useState(0)
  const menu = useRef<HTMLButtonElement>(null)
  const navigation = useRef<HTMLElement>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)
  const paletteInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { setOpen(false); setPaletteOpen(false) }, [loc.pathname])
  useEffect(() => {
    if (open) navigation.current?.querySelector('a')?.focus()
  }, [open])
  useEffect(() => {
    if (paletteOpen) {
      setPaletteIdx(0)
      window.setTimeout(() => paletteInputRef.current?.focus(), 0)
    }
  }, [paletteOpen])

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setPaletteOpen(v => !v)
        return
      }
      if (e.key === '/' &&
          document.activeElement?.tagName !== 'INPUT' &&
          document.activeElement?.tagName !== 'TEXTAREA') {
        e.preventDefault()
        searchInputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const paletteCommands = (() => {
    const q = paletteQuery.trim().toLowerCase()
    const base: { id: string; title: string; subtitle: string; badge: string; run: () => void }[] = [
      ...destinations.map(d => ({
        id: `route-${d.to}`,
        title: d.title,
        subtitle: `${d.group} · ${d.subtitle}`,
        badge: 'Go',
        run: () => navigate(d.to),
      })),
      {
        id: 'switch-version',
        title: `Switch to ${gameVersion === 'FC26' ? 'FC27' : 'FC26'}`,
        subtitle: `Toggle dataset edition (currently ${gameVersion})`,
        badge: 'Edition',
        run: () => setGameVersion(gameVersion === 'FC26' ? 'FC27' : 'FC26'),
      },
    ]
    if (q) {
      base.unshift({
        id: 'search-player',
        title: `Search player "${paletteQuery.trim()}"`,
        subtitle: `Open Player Discovery for ${gameVersion}`,
        badge: 'Search',
        run: () => navigate({ pathname: '/search', search: '?' + new URLSearchParams({ q: paletteQuery.trim() }).toString() }),
      })
    }
    return q ? base.filter(c => c.id === 'search-player' || c.title.toLowerCase().includes(q) || c.subtitle.toLowerCase().includes(q)) : base
  })()

  const active = [...destinations].reverse().find(d => d.to === loc.pathname ||
    d.paths.some(p => loc.pathname === p || loc.pathname.startsWith(p + '/')))

  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <aside
        className={`stadium-sidebar${open ? ' menu-open' : ''}${compact ? ' compact' : ''}`}
        onKeyDown={e => {
          if (e.key === 'Escape' && open) {
            setOpen(false)
            menu.current?.focus()
          }
        }}
      >
        <Link to="/" className="brand" title="EA FC Intelligence" onClick={() => setOpen(false)}>
          <span className="brand-mark" aria-hidden="true">FC</span>
          <span className="brand-label">
            EA FC Intelligence
            <small>Stadium 3.0</small>
          </span>
        </Link>

        <nav className="stadium-nav" id="stadium-navigation" aria-label="Main" ref={navigation}>
          {navGroups.map(group => (
            <div className="st3-nav-group" key={group.label}>
              <div className="st3-nav-group-label">{group.label}</div>
              {group.items.map(d => (
                <Link
                  key={d.to}
                  to={d.to}
                  title={`${d.title} — ${d.subtitle}`}
                  onClick={() => setOpen(false)}
                  className={d === active ? 'active' : undefined}
                  aria-current={d === active ? 'page' : undefined}
                >
                  <span className="nav-mark" aria-hidden="true">
                    <StadiumIcon name={d.icon} size={16} />
                  </span>
                  <span>{d.title}</span>
                </Link>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <Link to="/profile#account-settings" className="sidebar-link" title="Settings" onClick={() => setOpen(false)}>
            <span className="nav-mark" aria-hidden="true">
              <StadiumIcon name="settings" size={16} />
            </span>
            <span>Settings</span>
          </Link>
          <button
            className="sidebar-link sidebar-collapse"
            type="button"
            aria-pressed={compact}
            aria-label={compact ? 'Expand sidebar' : 'Collapse sidebar'}
            onClick={() => setCompact(!compact)}
          >
            <span className="nav-mark" aria-hidden="true">
              <StadiumIcon name={compact ? 'chevronRight' : 'chevronLeft'} size={16} />
            </span>
            <span>{compact ? 'Expand sidebar' : 'Collapse sidebar'}</span>
          </button>
        </div>
      </aside>

      <header className="stadium-header">
        <button
          type="button"
          className="btn ghost mobile-menu"
          ref={menu}
          aria-expanded={open}
          aria-controls="stadium-navigation"
          onClick={() => setOpen(!open)}
        >
          <StadiumIcon name={open ? 'close' : 'menu'} size={15} />
          <span>{open ? 'Close' : 'Menu'}</span>
        </button>

        <div className="workspace-location">
          <span>{active?.group ?? 'Workspace'}</span>
          <strong>{active?.title ?? 'Account'}</strong>
        </div>

        <div className="workspace-data">
          <VersionSwitch />
          {gameVersion !== 'FC27' ? (
            <span className="dataset-status">{players.status}</span>
          ) : (
            <span className="badge warning font-mono tiny">Research Release</span>
          )}
        </div>

        <form
          className="workspace-search"
          role="search"
          onSubmit={e => {
            e.preventDefault()
            const name = query.trim()
            navigate(
              {
                pathname: '/search',
                search: name ? '?' + new URLSearchParams({ q: name }).toString() : '',
              },
              { state: { quickSearch: name } }
            )
          }}
        >
          <div className="workspace-search-field">
            <svg className="workspace-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.3-4.3" />
            </svg>
            <input
              ref={searchInputRef}
              aria-label="Quick player search"
              type="search"
              maxLength={80}
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search players…"
            />
            <button
              type="button"
              className="cmd-search-kbd"
              onClick={() => setPaletteOpen(true)}
              aria-label="Open command palette (Ctrl+K)"
              title="Command palette (Ctrl+K)"
              style={{ minHeight: 24, cursor: 'pointer', background: 'transparent', border: '1px solid var(--border-strong)', color: 'var(--text-secondary)', borderRadius: 4, padding: '0 0.35rem', fontSize: '0.72rem' }}
            >
              Ctrl+K
            </button>
          </div>
          <button className="btn ghost sm workspace-search-submit" type="submit">Search</button>
        </form>

        {paletteOpen && (
          <div
            className="st3-cmdk-backdrop"
            role="presentation"
            onClick={e => { if (e.target === e.currentTarget) setPaletteOpen(false) }}
          >
            <div
              className="st3-cmdk-dialog"
              role="dialog"
              aria-modal="true"
              aria-label="Command palette"
              onKeyDown={e => {
                if (e.key === 'Escape') {
                  e.preventDefault()
                  setPaletteOpen(false)
                } else if (e.key === 'ArrowDown') {
                  e.preventDefault()
                  setPaletteIdx(i => Math.min(paletteCommands.length - 1, i + 1))
                } else if (e.key === 'ArrowUp') {
                  e.preventDefault()
                  setPaletteIdx(i => Math.max(0, i - 1))
                } else if (e.key === 'Enter' && paletteCommands[paletteIdx]) {
                  e.preventDefault()
                  paletteCommands[paletteIdx].run()
                  setPaletteOpen(false)
                }
              }}
            >
              <div className="st3-cmdk-input-row">
                <StadiumIcon name="search" size={16} />
                <input
                  ref={paletteInputRef}
                  type="search"
                  value={paletteQuery}
                  onChange={e => { setPaletteQuery(e.target.value); setPaletteIdx(0) }}
                  placeholder="Jump to workspace, switch FC26/FC27, or search player…"
                  aria-label="Command palette search"
                />
                <button type="button" className="btn ghost sm" onClick={() => setPaletteOpen(false)}>Esc</button>
              </div>
              <div className="st3-cmdk-list" role="listbox" aria-label="Command results">
                {paletteCommands.map((cmd, idx) => (
                  <button
                    key={cmd.id}
                    type="button"
                    role="option"
                    aria-selected={idx === paletteIdx}
                    className={`st3-cmdk-item ${idx === paletteIdx ? 'is-active' : ''}`}
                    onClick={() => {
                      cmd.run()
                      setPaletteOpen(false)
                    }}
                  >
                    <div>
                      <div className="small strong">{cmd.title}</div>
                      <div className="tiny muted">{cmd.subtitle}</div>
                    </div>
                    <span className="badge sm outline font-mono">{cmd.badge}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        <div className="workspace-account">
          <CopilotHeaderTrigger />
          {user ? (
            <>
              <Link to="/profile" className="account-name" title={user.email}>
                {user.display_name || user.email.split('@')[0]}
              </Link>
              <button
                type="button"
                className="btn ghost sm"
                onClick={async () => {
                  await logout()
                  navigate('/')
                }}
              >
                Log out
              </button>
            </>
          ) : (
            <Link to="/login" state={{ from: loc.pathname + loc.search + loc.hash }} className="btn ghost sm">
              Log in
            </Link>
          )}
        </div>

        {gameVersion === 'FC27' && (
          <div className="workspace-releases">
            <div className="row align-center gap05" role="status" aria-label="FC27 data availability">
              <span className="badge info">Players · {players.status}</span>
              <span className="badge info">Cards · {cards.status}</span>
              {players.data?.production.status === 'PRODUCTION_NOT_APPROVED' &&
                cards.data?.production.status === 'PRODUCTION_NOT_APPROVED' && (
                  <span className="dataset-status">Production Data Unavailable</span>
                )}
            </div>
            {(players.canOptIn || cards.canOptIn || researchOptIn) && (
              <label className="checkbox tiny">
                <input
                  type="checkbox"
                  checked={researchOptIn}
                  onChange={e => setResearchOptIn(e.target.checked)}
                />
                <span>Enable FC27 local research</span>
              </label>
            )}
          </div>
        )}
      </header>
    </>
  )
}

export function CopilotHeaderTrigger() {
  const { isOpen, toggleCopilot } = useCopilot()
  return (
    <button
      type="button"
      className={`btn sm ${isOpen ? 'primary' : 'ghost'}`}
      onClick={toggleCopilot}
      aria-label="Open Tactical Co-Pilot (Ctrl+Shift+C)"
      aria-expanded={isOpen}
      title="Tactical Co-Pilot (Ctrl+Shift+C)"
    >
      <StadiumIcon name="coach" size={14} />
      <span>Co-Pilot</span>
    </button>
  )
}

export function Toasts() {
  const { toasts, dismiss } = useSession()
  if (!toasts.length) return null
  return (
    <div
      style={{
        position: 'fixed',
        bottom: 16,
        right: 16,
        zIndex: 80,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        maxWidth: 380,
      }}
    >
      {toasts.map(t => (
        <div
          key={t.id}
          className={`callout ${t.kind === 'ok' ? 'ok' : t.kind === 'bad' ? 'bad' : 'info'}`}
          style={{ boxShadow: 'var(--shadow)', cursor: 'pointer' }}
          onClick={() => dismiss(t.id)}
          role="status"
        >
          <div className="small">{t.text}</div>
          {t.rid && <div className="rid mono tiny">request_id: {t.rid}</div>}
        </div>
      ))}
    </div>
  )
}
