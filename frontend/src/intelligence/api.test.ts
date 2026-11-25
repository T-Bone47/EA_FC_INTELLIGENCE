import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { recommend } from './api'
import rec from './fixtures/recommend.fc26.cm.json'

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const REQ = { game_version: 'FC26', position: 'CM', tactical_profile: 'BALANCED', limit: 5 } as const

async function failure(p: Promise<unknown>): Promise<any> {
  try { await p } catch (e) { return e }
  throw new Error('expected the request to fail')
}

describe('v3 api wrappers', () => {
  afterEach(() => vi.restoreAllMocks())

  it('posts the request unchanged and returns the response untouched', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, rec))
    const out = await recommend({ ...REQ })
    const [url, init] = spy.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/v3/recommendations')
    expect(JSON.parse(init.body as string)).toEqual(REQ)
    expect(out).toEqual(rec)
  })

  it('a 503 research opt-in error exposes the server message, code and requires', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(503, { detail: {
      error: 'REFERENCE_DISTRIBUTION_UNAVAILABLE', detail: 'FC27 is research-only. Set include_research_data=true.',
      requires: 'include_research_data' } }))
    const err = await failure(recommend({ ...REQ, game_version: 'FC27' }))
    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toContain('research-only')
    expect(err.code).toBe('REFERENCE_DISTRIBUTION_UNAVAILABLE')
    expect(err.requires).toBe('include_research_data')
  })

  it('a 422 DIVISION_NOT_APPLICABLE error passes the server text through', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(422, { detail: {
      error: 'DIVISION_NOT_APPLICABLE', detail: 'FC26 data carries no division label; omit division.' } }))
    const err = await failure(recommend({ ...REQ, division: "Men's Football" }))
    expect(err.message).toBe('FC26 data carries no division label; omit division.')
    expect(err.code).toBe('DIVISION_NOT_APPLICABLE')
    expect(err.requires).toBeUndefined()
  })
})
