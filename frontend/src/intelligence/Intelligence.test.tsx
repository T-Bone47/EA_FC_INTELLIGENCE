import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, setToken } from '../api/client'
// plain stub (not vi.fn): vitest's spy bookkeeping leaks an unhandled rejection for rejecting async mocks
const h = vi.hoisted(() => ({ impl: null as null | ((r: unknown) => Promise<unknown>), calls: [] as unknown[],
  cmpImpl: null as null | ((r: unknown, ids: string[]) => Promise<unknown>), cmpCalls: [] as unknown[][],
  wiImpl: null as null | (() => Promise<unknown>), wiCalls: [] as unknown[][] }))
vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),   // keep the real toApiError; stub only the network
  savedFootballStyle: async () => ({ position: 'CB', tactical_profile: 'LOW_BLOCK' }),
  recommendationOptions: async () => ({ formations: {
    '4-3-3': [
      { slot: 'CDM', position: 'CM', side: 'C', duty: 'DEFEND' },
      { slot: 'RCM', position: 'CM', side: 'R', duty: 'ATTACK' },
    ],
  } }),
  recommend: (r: unknown) => { h.calls.push(r); return h.impl!(r) },
  compare: (r: unknown, ids: string[]) => { h.cmpCalls.push([r, ids]); return h.cmpImpl!(r, ids) },
  whatIf: (b: unknown, v: unknown, t: unknown) => { h.wiCalls.push([b, v, t]); return h.wiImpl!() },
}))
import { Intelligence, buildRequest, type FormState } from './Intelligence'
import rec from './fixtures/recommend.fc26.cm.json'
import cmpFx from './fixtures/compare.fc26.cm.json'
import wiFx from './fixtures/whatif.fc26.cm.json'

const S: FormState = { gameVersion: 'FC27', position: 'CM', division: null, tactical: 'BALANCED', secondary: '', lam: null }
const find = () => screen.getByRole('button', { name: /find players/i })

describe('buildRequest', () => {
  it('returns null for FC27 until a division is chosen (never picks one silently)', () => {
    expect(buildRequest(S)).toBeNull()
  })
  it('BOTH sends no division; MEN and WOMEN send the exact API labels', () => {
    expect(buildRequest({ ...S, division: 'BOTH' }, true)).toEqual(
      { game_version: 'FC27', position: 'CM', tactical_profile: 'BALANCED', limit: 10, include_research_data: true })
    expect(buildRequest({ ...S, division: 'MEN' })?.division).toBe("Men's Football")
    expect(buildRequest({ ...S, division: 'WOMEN' })?.division).toBe("Women's Football")
  })
  it('requires explicit research opt-in and passes V3 preferences', async () => {
    const u = userEvent.setup()
    render(<Intelligence />)
    await u.click(screen.getByLabelText("Men's Football"))
    expect(find()).toBeDisabled()
    expect(buildRequest({ ...S, division: 'BOTH', preferredAttribute: 'stamina', playstylePlus: 'Quick Step' }, true))
      .toMatchObject({ include_research_data: true, attribute_preferences: [{ attribute: 'stamina', weight: 2 }],
        desired_playstyles_plus: ['Quick Step'] })
    expect(buildRequest({ ...S, division: 'BOTH' })).not.toHaveProperty('include_research_data')
  })

  it('FC26 never sends a division or the research flag', () => {
    expect(buildRequest({ ...S, gameVersion: 'FC26', division: 'MEN' })).toEqual(
      { game_version: 'FC26', position: 'CM', tactical_profile: 'BALANCED', limit: 10 })
  })
  it('passes optional preferences through only when set', () => {
    const r = buildRequest({ ...S, division: 'BOTH', secondary: 'HIGH_PRESS', lam: 0.9 })!
    expect(r.secondary_tactical_profile).toBe('HIGH_PRESS'); expect(r.lam).toBe(0.9)
  })
})

describe('Intelligence page', () => {
  beforeEach(() => { h.calls.length = 0; h.cmpCalls.length = 0; h.wiCalls.length = 0; h.impl = async () => rec; h.cmpImpl = async () => cmpFx; h.wiImpl = async () => wiFx })

  it('keeps Find players disabled until the FC27 division is chosen', async () => {
    const u = userEvent.setup(); render(<Intelligence researchEnabled={true} />)
    expect(find()).toBeDisabled()
    await u.click(screen.getByLabelText("Men's Football"))
    expect(find()).toBeEnabled()
  })

  it('FC26 needs no division and says why', async () => {
    const u = userEvent.setup(); render(<Intelligence researchEnabled={true} />)
    await u.click(screen.getByLabelText('FC26'))
    expect(screen.getByText(/no division label/i)).toBeInTheDocument()
    expect(find()).toBeEnabled()
  })

  it('submitting calls recommend with exactly the built request', async () => {
    const u = userEvent.setup(); render(<Intelligence researchEnabled={true} />)
    await u.click(screen.getByLabelText('FC26')); await u.click(find())
    expect(h.calls).toEqual([{ game_version: 'FC26', position: 'CM', tactical_profile: 'BALANCED', limit: 10 }])
    expect(await screen.findAllByTestId('ix-card')).toHaveLength(3)
  })

  it('applies stated account preferences only after the user requests them', async () => {
    setToken('test-preference-session')
    try {
      const u = userEvent.setup()
      render(<Intelligence researchEnabled={true} />)
      await u.click(screen.getByLabelText('FC26'))
      expect(screen.getByLabelText('Position')).toHaveValue('CM')
      await u.click(screen.getByRole('button', { name: 'Use saved football preferences' }))
      expect(screen.getByLabelText('Position')).toHaveValue('CB')
      expect(screen.getByLabelText('Tactical style')).toHaveValue('LOW_BLOCK')
      await u.click(find())
      expect(h.calls[h.calls.length - 1]).toMatchObject({ position: 'CB', tactical_profile: 'LOW_BLOCK' })
    } finally {
      setToken(null)
    }
  })

  it('requires a slot, sends the assignment, and keeps it in the submitted summary', async () => {
    const u = userEvent.setup()
    render(<Intelligence researchEnabled={true} />)
    await u.click(screen.getByLabelText('FC26'))
    await u.selectOptions(await screen.findByLabelText('Formation'), '4-3-3')
    expect(find()).toBeDisabled()
    await u.selectOptions(screen.getByLabelText('Formation slot'), 'CDM')
    await u.click(find())
    expect(h.calls[h.calls.length - 1]).toMatchObject({ game_version: 'FC26', position: 'CM', formation: '4-3-3', slot: 'CDM' })
    expect(await screen.findByTestId('submitted-request')).toHaveTextContent('4-3-3 CDM')
    await u.click(screen.getByRole('button', { name: 'Try RCM' }))
    expect(h.wiCalls[h.wiCalls.length - 1]?.[1]).toEqual([{ label: 'Try RCM', slot: 'RCM' }])
  })

  it('states the mixed pool explicitly, from the backend candidate_counts', async () => {
    // synthetic counts on a recorded FC26 response: this test is about the banner, not about data
    const mixed = { ...rec, division: { requested: null, scope: 'ALL_DIVISIONS', candidate_counts: { "Men's Football": 120, "Women's Football": 8 } } }
    h.impl = async () => mixed
    const u = userEvent.setup(); render(<Intelligence researchEnabled={true} />)
    await u.click(screen.getByLabelText(/Both/)); await u.click(find())
    const banner = await screen.findByTestId('scope-banner')
    expect(banner.textContent).toMatch(/mixed pool/i)
    expect(banner.textContent).toContain("120 Men's Football"); expect(banner.textContent).toContain("8 Women's Football")
  })

  it('shows the server message when the request is refused', async () => {
    h.impl = async () => { throw new ApiError(503, 'FC27 is research-only. Set include_research_data=true.', 'rid',
      { code: 'REFERENCE_DISTRIBUTION_UNAVAILABLE', requires: 'include_research_data' }) }
    const u = userEvent.setup(); render(<Intelligence researchEnabled={true} />)
    await u.click(screen.getByLabelText("Men's Football")); await u.click(find())
    expect(await screen.findByText(/research-only/)).toBeInTheDocument()
  })

  it('caps the comparison selection at 3 and says so', async () => {
    const many = { ...rec, ranked: [0, 1, 2, 3, 4].map(i => ({ ...rec.ranked[i % 3], entity_id: `e${i}`, name: `P${i}`, rank: i + 1, near_tie_with_next: undefined })) }
    h.impl = async () => many
    const u = userEvent.setup(); render(<Intelligence researchEnabled={true} />)
    await u.click(screen.getByLabelText('FC26')); await u.click(find())
    for (const box of await screen.findAllByRole('checkbox', { name: /^Compare P/ })) await u.click(box)
    expect(screen.getAllByRole('checkbox', { name: /^Compare P/ }).filter(b => (b as HTMLInputElement).checked)).toHaveLength(3)
    expect(screen.getByText(/maximum reached/i)).toBeInTheDocument()
  })

  it('compares under the request the shown results came from, not the live form', async () => {
    const u = userEvent.setup(); render(<Intelligence researchEnabled={true} />)
    await u.click(screen.getByLabelText('FC26')); await u.click(find())
    await u.selectOptions(screen.getByLabelText('Tactical style'), 'HIGH_PRESS')   // form changes AFTER the search
    const boxes = await screen.findAllByRole('checkbox', { name: /^Compare / })
    await u.click(boxes[0]); await u.click(boxes[1])
    await u.click(screen.getByRole('button', { name: /compare 2 players/i }))
    expect(h.cmpCalls).toHaveLength(1)
    expect((h.cmpCalls[0][0] as { tactical_profile: string }).tactical_profile).toBe('BALANCED')
    expect(await screen.findByLabelText('Comparison')).toBeInTheDocument()
  })

  it('ignores an older recommendation when the user changes the form and resubmits', async () => {
    let resolveOld!: (value: unknown) => void
    h.impl = () => new Promise(resolve => { resolveOld = resolve })
    const u = userEvent.setup()
    render(<Intelligence researchEnabled={true} />)
    await u.click(screen.getByLabelText('FC26'))
    await u.click(find())
    await u.selectOptions(screen.getByLabelText('Tactical style'), 'LOW_BLOCK')
    expect(find()).toBeEnabled()
    h.impl = async () => rec
    await u.click(find())
    expect(await screen.findByTestId('submitted-request')).toHaveTextContent('low block')
    await act(async () => { resolveOld({ ranked: null, division: null }) })
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByTestId('submitted-request')).toHaveTextContent('low block')
  })

  it('ignores a what-if response from before a new recommendation', async () => {
    let finish!: (value: unknown) => void
    h.wiImpl = () => new Promise(resolve => { finish = resolve })
    const u = userEvent.setup()
    render(<Intelligence researchEnabled={true} />)
    await u.click(screen.getByLabelText('FC26'))
    await u.click(find())
    await u.click(await screen.findByRole('button', { name: 'High press' }))
    await u.selectOptions(screen.getByLabelText('Tactical style'), 'LOW_BLOCK')
    h.impl = async () => ({ ...rec, request_id: 'new-request' })
    await u.click(find())
    await screen.findByTestId('submitted-request')
    await act(async () => { finish(wiFx) })
    expect(screen.queryByText(/entered the top 10/i)).toBeNull()
    expect(screen.queryByRole('heading', { name: 'High press' })).toBeNull()
  })

  it('ignores a comparison response from before a new search', async () => {
    const u = userEvent.setup(); render(<Intelligence researchEnabled={true} />)
    await u.click(screen.getByLabelText('FC26')); await u.click(find())
    const boxes = await screen.findAllByRole('checkbox', { name: /^Compare / })
    await u.click(boxes[0]); await u.click(boxes[1])
    let finish!: (value: unknown) => void
    h.cmpImpl = () => new Promise(resolve => { finish = resolve })
    await u.click(screen.getByRole('button', { name: /compare 2 players/i }))
    await u.selectOptions(screen.getByLabelText('Tactical style'), 'HIGH_PRESS')
    await u.click(find())
    await screen.findAllByRole('checkbox', { name: /^Compare / })
    await act(async () => { finish(cmpFx) })
    expect(screen.queryByLabelText('Comparison')).toBeNull()
  })

  it('what-if runs against the request the shown results came from, not the live form', async () => {
    const u = userEvent.setup(); render(<Intelligence researchEnabled={true} />)
    await u.click(screen.getByLabelText('FC26')); await u.click(find())
    await u.selectOptions(screen.getByLabelText('Tactical style'), 'LOW_BLOCK')     // form changes AFTER the search
    await u.click(await screen.findByRole('button', { name: 'High press' }))
    expect(h.wiCalls).toHaveLength(1)
    expect((h.wiCalls[0][0] as { tactical_profile: string }).tactical_profile).toBe('BALANCED')
  })

  it('treats a malformed 200 as an error instead of blanking the page', async () => {
    h.impl = async () => ({ ranked: null, division: null })
    const u = userEvent.setup(); render(<Intelligence researchEnabled={true} />)
    await u.click(screen.getByLabelText('FC26')); await u.click(find())
    expect(await screen.findByRole('alert')).toHaveTextContent(/unexpected response/i)
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
  })

  it('says so, with the backend counts, when there are no eligible players', async () => {
    h.impl = async () => ({ ...rec, ranked: [], counts: { candidates: 120, excluded: 118, not_evaluable: 2, ranked_returned: 0 } })
    const u = userEvent.setup(); render(<Intelligence />)
    await u.click(screen.getByLabelText('FC26')); await u.click(find())
    const note = await screen.findByRole('status')
    expect(note).toHaveTextContent(/no eligible players/i); expect(note).toHaveTextContent('120'); expect(note).toHaveTextContent('118')
    expect(screen.queryByTestId('ix-card')).toBeNull()
  })
})
