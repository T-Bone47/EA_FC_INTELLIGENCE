import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
const h = vi.hoisted(() => ({ calls: [] as unknown[][], impl: null as null | (() => Promise<unknown>) }))
vi.mock('./api', async (importOriginal) => ({ ...(await importOriginal<typeof import('./api')>()), whatIf: (b: unknown, v: unknown, t: unknown) => { h.calls.push([b, v, t]); return h.impl!() } }))
import { WhatIfPanel, presetsFor } from './WhatIfPanel'
import wi from './fixtures/whatif.fc26.cm.json'
import type { RecommendRequest } from './types'

const REQ: RecommendRequest = { game_version: 'FC26', position: 'CM', tactical_profile: 'BALANCED', limit: 10 }
const labels = (r: RecommendRequest) => presetsFor(r).map(p => p.label)

describe('presetsFor', () => {
  it('offers only presets that apply to the current request', () => {
    expect(labels(REQ)).toEqual(expect.arrayContaining(['High press', 'Low block', 'Possession', 'CM → CAM', 'λ 0.5', 'λ 0.9']))
    expect(labels({ ...REQ, tactical_profile: 'HIGH_PRESS' })).not.toContain('High press')
    expect(labels({ ...REQ, position: 'GK' })).not.toContain('CM → CAM')
    expect(labels({ ...REQ, position: 'CAM' })).toContain('CAM → CM')
    expect(labels(REQ).some(l => /Football/.test(l))).toBe(false)               // FC26 has no division
    const fc27 = { ...REQ, game_version: 'FC27' as const, division: "Men's Football" as const }
    expect(labels(fc27)).toContain("Women's Football only"); expect(labels(fc27)).not.toContain("Men's Football only")
  })
})

describe('WhatIfPanel', () => {
  beforeEach(() => { h.calls.length = 0; h.impl = async () => wi })

  it('a preset posts the right variant for the request it was given', async () => {
    const u = userEvent.setup(); render(<WhatIfPanel request={REQ} />)
    await u.click(screen.getByRole('button', { name: 'High press' }))
    expect(h.calls).toEqual([[REQ, [{ label: 'High press', tactical_profile: 'HIGH_PRESS' }], 10]])
  })

  it('renders the server ranks verbatim', async () => {
    const u = userEvent.setup(); render(<WhatIfPanel request={REQ} />)
    await u.click(screen.getByRole('button', { name: 'High press' }))
    const rows = await screen.findAllByRole('listitem')
    const tracked = (wi as any).variants[0].tracked_from_base
    expect(rows).toHaveLength(tracked.length)
    tracked.forEach((t: any, i: number) => {
      expect(rows[i].textContent).toContain(`${t.name}: #${t.base_rank} → ${t.new_rank === null ? 'outside' : '#' + t.new_rank}`)
    })
  })

  it('compares only tactical variations while keeping the submitted request fixed', async () => {
    h.impl = async () => ({ ...wi, variants: [
      { ...wi.variants[0], label: 'High press' },
      { ...wi.variants[0], label: 'Low block' },
    ] })
    render(<WhatIfPanel request={REQ} />)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Compare tactical styles' }))
    expect((h.calls[0][1] as unknown[])).toHaveLength(5)
    expect(h.calls[0][0]).toEqual(REQ)
    expect(await screen.findByRole('heading', { name: 'Tactical compatibility' })).toBeVisible()
  })

  it('shows the server message for a refused variant', async () => {
    h.impl = async () => ({ ...wi, variants: [{ label: 'x', changes: {}, error: 'DIVISION_NOT_APPLICABLE', detail: 'FC26 data carries no division label.' }] })
    const u = userEvent.setup(); render(<WhatIfPanel request={REQ} />)
    await u.click(screen.getByRole('button', { name: 'Low block' }))
    expect(await screen.findByText('FC26 data carries no division label.')).toBeInTheDocument()
  })
})
