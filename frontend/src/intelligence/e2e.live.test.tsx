/**
 * Live end-to-end: real FastAPI + real Postgres + the real UI code (jsdom, not a browser).
 * Skipped unless E2E_API_URL is set:  E2E_API_URL=http://127.0.0.1:8011 npx vitest run src/intelligence/e2e.live.test.tsx
 */
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Intelligence } from './Intelligence'

const BASE = (globalThis as any).process?.env?.E2E_API_URL as string | undefined
const REQ = { game_version: 'FC26', position: 'CM', tactical_profile: 'BALANCED', limit: 10 }
const post = async (path: string, body: unknown) =>
  (await fetch(new URL(path, BASE), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })).json()

describe.skipIf(!BASE)('live API <-> UI', () => {
  afterEach(() => vi.restoreAllMocks())
  async function search() {
    const realFetch = globalThis.fetch
    vi.spyOn(globalThis, 'fetch').mockImplementation((input: any, init?: any) => realFetch(new URL(String(input), BASE), init))
    const truth = await post('/api/v3/recommendations', REQ)
    const u = userEvent.setup(); render(<Intelligence />)
    await u.click(screen.getByLabelText('FC26')); await u.click(screen.getByRole('button', { name: /find players/i }))
    const cards = await screen.findAllByTestId('ix-card', {}, { timeout: 30000 })
    return { u, truth, cards }
  }

  it('the ladder shows exactly the backend ranking: order, names, scores and tie notes', async () => {
    const { truth, cards } = await search()
    expect(cards.map(c => within(c).getByRole('heading', { level: 3 }).textContent)).toEqual(truth.ranked.map((r: any) => r.name))
    expect(cards.map(c => within(c).getByLabelText(/^Intelligence Score/).textContent)).toEqual(truth.ranked.map((r: any) => r.score.toFixed(4)))
    expect(cards.map(c => !!within(c).queryByTestId('near-tie-note'))).toEqual(truth.ranked.map((r: any) => !!r.near_tie_with_next))
  }, 90000)

  it('compare shows the backend pairwise explanations for the same players', async () => {
    const { u, truth } = await search()
    const ids = truth.ranked.slice(0, 2).map((r: any) => r.entity_id)
    const boxes = await screen.findAllByRole('checkbox', { name: /^Compare / })
    await u.click(boxes[0]); await u.click(boxes[1])
    await u.click(screen.getByRole('button', { name: /compare 2 players/i }))
    const panel = await screen.findByLabelText('Comparison', {}, { timeout: 30000 })
    const cmp = await post('/api/v3/compare', { request: REQ, entity_ids: ids })
    for (const p of cmp.pairwise) for (const w of p.why) expect(panel.textContent).toContain(w)
  }, 90000)

  it('what-if rows equal the backend what-if for the same variant', async () => {
    const { u } = await search()
    await u.click(await screen.findByRole('button', { name: 'High press' }))
    const panel = within(screen.getByRole('region', { name: 'What if' }))
    const rows = (await panel.findAllByRole('listitem', {}, { timeout: 30000 })).map(r => r.textContent ?? '')
    const wi = await post('/api/v3/what-if', { base: REQ, track_top: 10, variants: [{ label: 'High press', tactical_profile: 'HIGH_PRESS' }] })
    for (const t of wi.variants[0].tracked_from_base)
      expect(rows.some(r => r.includes(`${t.name}: #${t.base_rank} → ${t.new_rank === null ? 'outside' : '#' + t.new_rank}`))).toBe(true)
  }, 90000)
})
