import { describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { useAction } from './useApi'

describe('useAction', () => {
  it('always runs with CURRENT state (regression: stale closure sent old game_version)', async () => {
    const calls: string[] = []
    const { result } = renderHook(() => {
      const [version, setVersion] = useState('FC26')
      const action = useAction(async () => {
        calls.push(version)
        return version
      })
      return { version, setVersion, action }
    })

    await act(async () => { await result.current.action.run() })
    act(() => result.current.setVersion('FC27'))
    const out = await act(async () => await result.current.action.run())

    expect(calls).toEqual(['FC26', 'FC27'])   // second run sees the NEW state
    expect(out).toBe('FC27')
    expect(result.current.action.result).toBe('FC27')
  })

  it('captures errors and exposes clear()', async () => {
    const { result } = renderHook(() =>
      useAction(async () => { throw Object.assign(new Error('boom'), { status: 404, detail: 'gone' }) }))
    const out = await act(async () => await result.current.run())
    expect(out).toBeNull()
    await waitFor(() => expect(result.current.error).not.toBeNull())
    act(() => result.current.clear())
    expect(result.current.error).toBeNull()
    expect(result.current.result).toBeNull()
  })

  it('tracks pending state', async () => {
    let release: () => void = () => {}
    const gate = new Promise<void>((r) => { release = r })
    const { result } = renderHook(() => useAction(async () => { await gate; return 1 }))
    let p: Promise<number | null>
    act(() => { p = result.current.run() })
    await waitFor(() => expect(result.current.pending).toBe(true))
    release()
    await act(async () => { await p! })
    expect(result.current.pending).toBe(false)
    expect(result.current.result).toBe(1)
  })

  it('run is referentially stable across renders (safe in deps/onClick)', async () => {
    const spy = vi.fn(async () => 'x')
    const { result, rerender } = renderHook(() => useAction(spy))
    const first = result.current.run
    rerender()
    expect(result.current.run).toBe(first)
  })
})

// ---------------------------------------------------------------------------
it('regression: survives React StrictMode double effect cycle (dev servers)', async () => {
  const { renderHook, act, waitFor } = await import('@testing-library/react')
  const { StrictMode } = await import('react')
  const fn = vi.fn(async () => 'ok')
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <StrictMode>{children}</StrictMode>
  )
  const { result } = renderHook(() => useAction(fn), { wrapper })
  await act(async () => { await result.current.run() })
  await waitFor(() => expect(result.current.pending).toBe(false))
  expect(result.current.result).toBe('ok')   // setState must still fire under StrictMode
  expect(result.current.error).toBeNull()
})
