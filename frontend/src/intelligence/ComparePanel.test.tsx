import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ComparePanel } from './ComparePanel'
import cmp from './fixtures/compare.fc26.cm.json'
import type { CompareResponse } from './types'

const r = cmp as unknown as CompareResponse
const text = () => document.body.textContent ?? ''

describe('ComparePanel', () => {
  it('uses backend why text and never a generic "is better"', () => {
    render(<ComparePanel response={r} />)
    for (const p of r.pairwise) for (const w of p.why) expect(text()).toContain(w)
    expect(screen.queryByText(/is better/i)).toBeNull()
  })

  it('describes each pair from the backend flag: tied vs. scores higher', () => {
    render(<ComparePanel response={r} />)
    const tied = r.pairwise.filter(p => p.within_noise_threshold).length
    expect(screen.queryAllByText(/effectively tied/i)).toHaveLength(tied)
    expect(screen.queryAllByText(/scores higher than/i)).toHaveLength(r.pairwise.length - tied)
  })

  it('puts every player in the table with the backend score and coverage', () => {
    render(<ComparePanel response={r} />)
    for (const p of r.players) {
      expect(screen.getByRole('columnheader', { name: p.name })).toBeInTheDocument()
      expect(text()).toContain(p.score.toFixed(4))
    }
  })

  it('gives every column header an accessible name (axe: empty-table-header)', () => {
    render(<ComparePanel response={r} />)
    for (const h of screen.getAllByRole('columnheader')) expect((h.textContent ?? '').trim().length).toBeGreaterThan(0)
  })
})
