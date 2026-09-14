import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../api/client'

export interface ApiState<T> {
  data: T | null
  loading: boolean
  error: ApiError | null
  reload: () => void
}

/** Declarative GET with race protection. `key` changes trigger refetch;
 *  pass null key to skip (e.g. until an id exists). */
export function useApi<T>(path: string | null, deps: unknown[] = []): ApiState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(!!path)
  const [error, setError] = useState<ApiError | null>(null)
  const [tick, setTick] = useState(0)
  const seq = useRef(0)

  useEffect(() => {
    if (!path) { setData(null); setLoading(false); setError(null); return }
    const my = ++seq.current
    setLoading(true)
    setError(null)
    api.get<T>(path).then(
      (d) => { if (seq.current === my) { setData(d); setLoading(false) } },
      (e) => { if (seq.current === my) { setError(e as ApiError); setLoading(false) } },
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, ...deps])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, loading, error, reload }
}

/** Imperative action runner (POST/PUT/PATCH/DELETE) with pending + error + last result.
 *  The latest callback is kept in a ref: `run` must always execute with CURRENT
 *  component state (a stale closure here would e.g. submit an old game_version). */
export function useAction<A extends unknown[], T>(
  fn: (...args: A) => Promise<T>,
): { run: (...args: A) => Promise<T | null>; pending: boolean; error: ApiError | null; result: T | null; clear: () => void } {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [result, setResult] = useState<T | null>(null)
  const mounted = useRef(true)
  const fnRef = useRef(fn)
  fnRef.current = fn
  // StrictMode-safe: the effect body must RE-ASSERT mounted=true because dev-mode
  // StrictMode runs effect -> cleanup -> effect on the same instance.
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  const run = useCallback(async (...args: A) => {
    setPending(true)
    setError(null)
    try {
      const out = await fnRef.current(...args)
      if (mounted.current) setResult(out)
      return out
    } catch (e) {
      if (mounted.current) setError(e as ApiError)
      return null
    } finally {
      if (mounted.current) setPending(false)
    }
  }, [])

  const clear = useCallback(() => { setError(null); setResult(null) }, [])
  return { run, pending, error, result, clear }
}
