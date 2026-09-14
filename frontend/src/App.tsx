import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { Nav, Toasts } from './components/Nav'
import { useSession } from './state/session'
import { Empty, Loading } from './components/common'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Dashboard from './pages/Dashboard'
import Search from './pages/Search'
import PlayerPage from './pages/PlayerPage'
import Cards from './pages/Cards'
import CardPage from './pages/CardPage'
import Recommend from './pages/Recommend'
import Compare from './pages/Compare'
import Squads from './pages/Squads'
import SquadDetail from './pages/SquadDetail'
import Saved from './pages/Saved'
import Profile from './pages/Profile'
import NotFound from './pages/NotFound'

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, ready } = useSession()
  const loc = useLocation()
  if (!ready) return <Loading label="Restoring session" />
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />
  return <>{children}</>
}

export default function App() {
  const { ready } = useSession()
  return (
    <div className="app">
      <Nav />
      <main className="shell" id="main">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
          <Route path="/search" element={<Search />} />
          <Route path="/players/:id" element={<PlayerPage />} />
          <Route path="/cards" element={<Cards />} />
          <Route path="/cards/:id" element={<CardPage />} />
          <Route path="/recommend" element={<Recommend />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/squads" element={<RequireAuth><Squads /></RequireAuth>} />
          <Route path="/squads/:id" element={<RequireAuth><SquadDetail /></RequireAuth>} />
          <Route path="/saved" element={<RequireAuth><Saved /></RequireAuth>} />
          <Route path="/profile" element={<RequireAuth><Profile /></RequireAuth>} />
          <Route path="/404" element={<NotFound />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Routes>
      </main>
      <footer className="shell" style={{ paddingTop: 0, flex: 'none' }}>
        <hr className="divider" />
        <div className="row tiny faint" style={{ justifyContent: 'space-between' }}>
          <span>
            Data honesty: UNKNOWN means UNKNOWN. Missing prices, PlayStyles, Roles and
            chemistry are never rendered as zero.
          </span>
          <span className="nowrap">Community sources are REFERENCE_ONLY · no fabricated EA FC data</span>
        </div>
      </footer>
      <Toasts />
      {!ready && (
        <div style={{ position: 'fixed', inset: 0, display: 'grid', placeItems: 'center',
                      background: 'var(--bg)', zIndex: 90 }}>
          <Empty title="Starting up" hint="Loading version metadata from the API." />
        </div>
      )}
    </div>
  )
}
