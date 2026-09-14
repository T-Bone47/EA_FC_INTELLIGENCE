import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, getToken, qs, setToken } from './client'

function mockResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(typeof body === 'string' ? body : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
}

describe('api client', () => {
  beforeEach(() => { setToken(null); localStorage.clear() })
  afterEach(() => { vi.restoreAllMocks(); setToken(null) })

  it('builds query strings, skipping empty values', () => {
    expect(qs({ a: 1, b: '', c: null, d: undefined, e: 'x y' })).toBe('?a=1&e=x+y')
    expect(qs({})).toBe('')
  })

  it('stores and clears the token', () => {
    setToken('abc')
    expect(getToken()).toBe('abc')
    setToken(null)
    expect(getToken()).toBeNull()
  })

  it('sends the bearer token when present', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse(200, { ok: true }))
    setToken('tok-123')
    await api.get('/api/x')
    const init = spy.mock.calls[0][1] as RequestInit
    expect((init.headers as Record<string, string>)['Authorization']).toBe('Bearer tok-123')
  })

  it('uses relative URLs only (never a hardcoded origin)', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse(200, {}))
    await api.get('/api/players?q=mbappe')
    expect(String(spy.mock.calls[0][0])).toBe('/api/players?q=mbappe')
  })

  it('maps error detail and request_id onto ApiError', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      mockResponse(404, { detail: 'NO ingested production data', request_id: 'rid-1' },
                   { 'X-Request-ID': 'hdr-rid' }))
    const err = await api.get('/api/x').catch((e) => e) as ApiError
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(404)
    expect(err.detail).toBe('NO ingested production data')
    expect(err.requestId).toBe('rid-1')      // body wins over header
  })

  it('falls back to the X-Request-ID header', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      mockResponse(500, { detail: 'Internal server error.' }, { 'X-Request-ID': 'hdr-rid' }))
    const err = await api.get('/api/x').catch((e) => e) as ApiError
    expect(err.requestId).toBe('hdr-rid')
  })

  it('flattens FastAPI 422 validation arrays into one readable message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse(422, {
      detail: [{ loc: ['body', 'limit'], msg: 'ensure this value is <= 50' }],
    }))
    const err = await api.post('/api/x', {}).catch((e) => e) as ApiError
    expect(err.detail).toContain('limit')
    expect(err.detail).toContain('<= 50')
  })

  it('handles 204 with no body', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }))
    await expect(api.del('/api/x')).resolves.toBeUndefined()
  })

  it('surfaces rate-limit responses as ApiError(429)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      mockResponse(429, { detail: 'Rate limit exceeded. Retry in 12s.' }))
    const err = await api.post('/api/auth/login', {}).catch((e) => e) as ApiError
    expect(err.status).toBe(429)
    expect(err.detail).toMatch(/Rate limit/)
  })
})
