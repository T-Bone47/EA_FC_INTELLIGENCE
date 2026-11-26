import { Suspense, lazy } from 'react'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { ResearchControl, useRelease } from './components/Availability'
import { Nav, Toasts } from './components/Nav'
import { CoachCopilotDrawer } from './components/CoachCopilotDrawer'
import { CopilotProvider } from './state/copilot'
import { useSession } from './state/session'
import { Empty, Loading } from './components/common'

const Login = lazy(() => import('./pages/Login'))
const Signup = lazy(() => import('./pages/Signup'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Search = lazy(() => import('./pages/Search'))
const PlayerPage = lazy(() => import('./pages/PlayerPage'))
const Cards = lazy(() => import('./pages/Cards'))
const CardSquadLab = lazy(() => import('./pages/CardSquadLab'))
const PerformanceEvidenceLab = lazy(() => import('./pages/PerformanceEvidenceLab'))
const GameplayStudio = lazy(() => import('./pages/GameplayStudio'))
const PersonalCoach = lazy(() => import('./pages/PersonalCoach'))
const TacticalLab = lazy(() => import('./pages/TacticalLab'))
const GamerDNAStudio = lazy(() => import('./pages/GamerDNAStudio'))
const DecisionReplayLab = lazy(() => import('./pages/DecisionReplayLab'))
const CardPage = lazy(() => import('./pages/CardPage'))
const Compare = lazy(() => import('./pages/Compare'))
const Intelligence = lazy(() => import('./intelligence/Intelligence').then(m => ({ default: m.Intelligence })))
const Squads = lazy(() => import('./pages/Squads'))
const SquadDetail = lazy(() => import('./pages/SquadDetail'))
const Saved = lazy(() => import('./pages/Saved'))
const Profile = lazy(() => import('./pages/Profile'))
const NotFound = lazy(() => import('./pages/NotFound'))

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, ready } = useSession()
  const loc = useLocation()
  if (!ready) return <Loading label="Restoring session" />
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname + loc.search + loc.hash }} />
  return <>{children}</>
}

export default function App() {
  const { ready, gameVersion, setGameVersion, user, availabilityLoading } = useSession()
  const release = useRelease('game_player', gameVersion)
  const { pathname, search } = useLocation()
  const position = new URLSearchParams(search).get('position') ?? undefined
  const account = pathname === '/login' || pathname === '/signup'
  return (
    <CopilotProvider>
      <div className={account ? "app stadium-app auth-app" : "app stadium-app"}>
      {account ? (
        <header className="auth-header">
          <a className="skip-link" href="#main">Skip to content</a>
          <Link to="/" className="brand" style={{ textDecoration: 'none' }}>
            <span className="brand-mark">FC</span>
            <span>EA FC Intelligence</span>
          </Link>
        </header>
      ) : <Nav />}
      <main className="shell stadium-main" id="main" tabIndex={-1}>
        {ready && <Suspense fallback={<div className="p2"><Loading label="Loading module" /></div>}><Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
          <Route path="/search" element={<Search />} />
          <Route path="/players/:id" element={<PlayerPage />} />
          <Route path="/cards" element={<Cards />} />
          <Route path="/cards/squad-lab" element={<CardSquadLab />} />
          <Route path="/cards/performance" element={<PerformanceEvidenceLab />} />
          <Route path="/research/gameplay-studio" element={<GameplayStudio />} />
          <Route path="/research/decision-lab" element={<DecisionReplayLab />} />
          <Route path="/gameplay-studio" element={<GameplayStudio />} />
          <Route path="/coach" element={<PersonalCoach />} />
          <Route path="/tactical-lab" element={<TacticalLab />} />
          <Route path="/gamer-dna" element={<GamerDNAStudio />} />
          <Route path="/cards/:id" element={<CardPage />} />
          <Route path="/intelligence" element={availabilityLoading ? <Loading label="Checking data releases" /> : <Intelligence key={`${gameVersion}:${release.active}:${release.canRecommend}:${position ?? ''}`}
            initialVersion={gameVersion} initialPosition={position} onVersionChange={setGameVersion}
            analysisScope={user?.id ?? 'guest'} researchEnabled={release.active}
            canRecommend={release.canRecommend} availabilityStatus={release.status}
            researchControl={<ResearchControl scope="game_player" label="Include FC27 research players" />} />} />
          <Route path="/recommend" element={<Navigate replace to={'/intelligence' + search} />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/squads" element={<RequireAuth><Squads /></RequireAuth>} />
          <Route path="/squads/:id" element={<RequireAuth><SquadDetail /></RequireAuth>} />
          <Route path="/saved" element={<RequireAuth><Saved /></RequireAuth>} />
          <Route path="/profile" element={<RequireAuth><Profile /></RequireAuth>} />
          <Route path="/404" element={<NotFound />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Routes></Suspense>}
      </main>
      {!account && <footer className="stadium-footer">EA FC Intelligence <span>Player, card and performance evidence</span></footer>}
      {!account && <CoachCopilotDrawer />}
      <Toasts />
      {!ready && (
        <div style={{ position: 'fixed', inset: 0, display: 'grid', placeItems: 'center',
                      background: 'var(--bg)', zIndex: 90 }}>
          <Empty title="Starting up" hint="Loading version metadata from the API." />
        </div>
      )}
      </div>
    </CopilotProvider>
  )
}
