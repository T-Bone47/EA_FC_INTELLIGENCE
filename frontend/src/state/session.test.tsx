import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { SessionProvider, useSession } from './session'

// The provider boots by fetching /api/meta/game-versions + /api/auth/me, so
// fetch is stubbed per-test to control the /me status code.
function mountProvider() {
  return renderHook(() => useSession(), {
    wrapper: ({ children }: { children: ReactNode }) => (
      <SessionProvider>{children}</SessionProvider>
    ),
  })
}

function stubFetch(meStatus: number) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: any) => {
    const url = String(input)
    if (url.includes('/api/auth/me')) {
      return new Response(
        meStatus === 200
          ? JSON.stringify({ id: 'u1', email: 'a@b.c', display_name: null, role: 'USER',
                             preferred_game_version: null, preferences: null })
          : JSON.stringify({ detail: meStatus === 429 ? 'Too many requests' : 'Unauthorized' }),
        { status: meStatus, headers: { 'Content-Type': 'application/json' } },
      )
    }
    if (url.includes('/api/meta/game-versions')) {
      return new Response(JSON.stringify([{ code: 'FC26' }, { code: 'FC27' }]),
        { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } })
  })
}

describe('session refreshUser token handling', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('regression: a 429 on /me must NOT destroy a valid stored token', async () => {
    localStorage.setItem('eafc.token', 'still-valid-token')
    stubFetch(429)
    const { result } = mountProvider()
    await waitFor(() => expect(result.current.ready).toBe(true))
    await act(async () => { await result.current.refreshUser() })
    expect(localStorage.getItem('eafc.token')).toBe('still-valid-token')
  })

  it('a 500 on /me must NOT destroy a valid stored token either', async () => {
    localStorage.setItem('eafc.token', 'still-valid-token')
    stubFetch(500)
    const { result } = mountProvider()
    await waitFor(() => expect(result.current.ready).toBe(true))
    await act(async () => { await result.current.refreshUser() })
    expect(localStorage.getItem('eafc.token')).toBe('still-valid-token')
  })

  it('a 401 on /me DOES clear the token (session genuinely invalid)', async () => {
    localStorage.setItem('eafc.token', 'expired-token')
    stubFetch(401)
    const { result } = mountProvider()
    await waitFor(() => expect(result.current.ready).toBe(true))
    await act(async () => { await result.current.refreshUser() })
    expect(localStorage.getItem('eafc.token')).toBeNull()
  })

  it('a 200 on /me populates the user', async () => {
    localStorage.setItem('eafc.token', 'good-token')
    stubFetch(200)
    const { result } = mountProvider()
    await waitFor(() => expect(result.current.user?.email).toBe('a@b.c'))
    expect(localStorage.getItem('eafc.token')).toBe('good-token')
  })
})
