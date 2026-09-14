import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, ApiError, getToken, setToken } from '../api/client'
import type { GameVersion, VersionInfo } from '../api/types'

export interface SessionUser {
  id: string
  email: string
  display_name: string | null
  role: string
  preferred_game_version: string | null
  preferences: Record<string, unknown> | null
}

interface Toast {
  id: number
  kind: 'ok' | 'bad' | 'info'
  text: string
  rid?: string
}

interface SessionState {
  user: SessionUser | null
  ready: boolean
  versions: VersionInfo[]
  gameVersion: GameVersion
  setGameVersion: (v: GameVersion) => void
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string, displayName: string) => Promise<void>
  logout: (all?: boolean) => Promise<void>
  refreshUser: () => Promise<void>
  toasts: Toast[]
  notify: (kind: Toast['kind'], text: string, rid?: string) => void
  dismiss: (id: number) => void
}

const Ctx = createContext<SessionState | null>(null)
const VERSION_KEY = 'eafc.version'

function initialVersion(versions: VersionInfo[], user: SessionUser | null): GameVersion {
  const fromUser = user?.preferred_game_version
  const stored = (() => { try { return localStorage.getItem(VERSION_KEY) } catch { return null } })()
  const wanted = fromUser || stored || 'FC26'
  return versions.some((v) => v.code === wanted) ? (wanted as GameVersion) : 'FC26'
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null)
  const [versions, setVersions] = useState<VersionInfo[]>([])
  const [gameVersion, setVersion] = useState<GameVersion>('FC26')
  const [ready, setReady] = useState(false)
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id))
  }, [])

  const notify = useCallback((kind: Toast['kind'], text: string, rid?: string) => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t.slice(-3), { id, kind, text, rid }])
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 7000)
  }, [])

  const refreshUser = useCallback(async () => {
    if (!getToken()) { setUser(null); return }
    try {
      const me = await api.get<SessionUser>('/api/auth/me')
      setUser(me)
    } catch (e) {
      // Only a definitive 401 (invalid/expired/revoked token) may destroy the
      // session. Transient failures — 429 from the strict auth rate limiter,
      // 5xx, network blips — must never silently log the user out; the boot
      // /me call counts toward the 10/min auth budget, so a hard-reload burst
      // would otherwise nuke perfectly valid tokens.
      if (e instanceof ApiError && e.status === 401) {
        setToken(null)
        setUser(null)
      }
    }
  }, [])

  useEffect(() => {
    let alive = true
    ;(async () => {
      const [vs] = await Promise.all([
        api.get<VersionInfo[]>('/api/meta/game-versions').catch(() => [] as VersionInfo[]),
        refreshUser(),
      ])
      if (!alive) return
      setVersions(vs)
      setVersion((cur) => {
        const list = vs.length ? vs : [{ code: 'FC26' } as VersionInfo]
        return initialVersion(list, user) || cur
      })
      setReady(true)
    })()
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const setGameVersion = useCallback((v: GameVersion) => {
    setVersion(v)
    try { localStorage.setItem(VERSION_KEY, v) } catch { /* ignore */ }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const r = await api.post<{ access_token: string }>('/api/auth/login', { email, password })
    setToken(r.access_token)
    await refreshUser()
  }, [refreshUser])

  const signup = useCallback(async (email: string, password: string, displayName: string) => {
    const r = await api.post<{ access_token: string }>('/api/auth/signup', {
      email, password, display_name: displayName || null,
    })
    setToken(r.access_token)
    await refreshUser()
  }, [refreshUser])

  const logout = useCallback(async (all = false) => {
    try { await api.post(all ? '/api/auth/logout-all' : '/api/auth/logout') } catch { /* ignore */ }
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo<SessionState>(() => ({
    user, ready, versions, gameVersion, setGameVersion,
    login, signup, logout, refreshUser, toasts, notify, dismiss,
  }), [user, ready, versions, gameVersion, setGameVersion, login, signup,
       logout, refreshUser, toasts, notify, dismiss])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useSession(): SessionState {
  const v = useContext(Ctx)
  if (!v) throw new Error('useSession must be used inside <SessionProvider>')
  return v
}
