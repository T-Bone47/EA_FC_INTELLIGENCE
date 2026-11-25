import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Card } from './Card'
import rec from './fixtures/recommend.fc26.cm.json'
import type { Entry } from './types'

const entries = rec.ranked as unknown as Entry[]
const tied = entries[0]    // recorded: rank 1 is within noise of rank 2
const clear = entries[2]   // recorded: rank 3 has no near tie

describe('Card', () => {
  it('labels EA OVR and Intelligence Score separately and never calls the score a rating', () => {
    render(<Card entry={tied} />)
    expect(screen.getByText('EA OVR')).toBeInTheDocument()
    expect(screen.getByText('Intelligence Score')).toBeInTheDocument()
    expect(screen.getByLabelText(`Intelligence Score ${tied.score.toFixed(4)}`)).toBeInTheDocument()
    expect(screen.queryByText(/intelligence rating/i)).toBeNull()
  })

  it('shows "Complete evidence" for a zero-width interval and a range for a partial one', () => {
    const { rerender } = render(<Card entry={tied} />)
    expect(screen.getByText(/complete evidence/i)).toBeInTheDocument()
    const partial: Entry = { ...tied, score_interval: { ...tied.score_interval, low: 0.8, high: 0.85 } }
    rerender(<Card entry={partial} />)
    expect(screen.queryByText(/complete evidence/i)).toBeNull()
    expect(screen.getByText('0.8000–0.8500')).toBeInTheDocument()
  })

  it('renders the backend explanation text verbatim', () => {
    render(<Card entry={tied} />)
    for (const r of tied.explanation.reasons) expect(screen.getAllByText(r).length).toBeGreaterThan(0)
  })

  it("shows the engine's confidence level as-is, not a label the UI invented", () => {
    render(<Card entry={tied} />)
    expect(screen.getByTitle(/reporting only/i).textContent).toBe(tied.confidence!.level)
  })

  it('near-tie note says the order is not meaningful and lists why_ahead when within noise', () => {
    render(<Card entry={tied} />)
    const note = screen.getByTestId('near-tie-note')
    expect(note.textContent).toMatch(/not a meaningful order/i)
    for (const w of tied.near_tie_with_next!.why_ahead) expect(note.textContent).toContain(w)
  })

  it('an entry without near_tie_with_next shows no tie note', () => {
    render(<Card entry={clear} />)
    expect(screen.queryByTestId('near-tie-note')).toBeNull()
  })
})
