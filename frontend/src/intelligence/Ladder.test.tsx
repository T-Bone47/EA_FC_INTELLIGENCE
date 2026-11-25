import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Ladder } from './Ladder'
import rec from './fixtures/recommend.fc26.cm.json'
import type { Entry } from './types'

const base = (rec.ranked as unknown as Entry[])[0]
const TIE = { next_entity_id: 'x', score_gap: 0.001, within_noise_threshold: true, intervals_overlap: false, why_ahead: ['positioning'] }
const e = (id: string, score: number, tie?: Partial<typeof TIE>): Entry => ({
  ...base, entity_id: id, name: `Player ${id}`, score, near_tie_with_next: tie ? { ...TIE, ...tie } : undefined,
})
const names = () => screen.getAllByRole('heading', { level: 3 }).map(h => h.textContent)

describe('Ladder', () => {
  it('renders in server order even when scores are not monotonic', () => {
    render(<Ladder ranked={[e('a', 0.80), e('b', 0.90), e('c', 0.85)]} />)
    expect(names()).toEqual(['Player a', 'Player b', 'Player c'])
  })

  it('groups a run of noise-tied neighbours in one bracket', () => {
    render(<Ladder ranked={[e('a', 0.9, {}), e('b', 0.89, {}), e('c', 0.88), e('d', 0.8)]} />)
    const bracket = screen.getByLabelText('Effectively tied')
    expect(within(bracket).getAllByTestId('ix-card')).toHaveLength(3)
    expect(within(bracket).queryByText('Player d')).toBeNull()
    expect(names()).toEqual(['Player a', 'Player b', 'Player c', 'Player d'])
  })

  it('shows an overlap note, and no bracket, when only intervals overlap', () => {
    render(<Ladder ranked={[e('a', 0.9, { within_noise_threshold: false, intervals_overlap: true, score_gap: 0.02 }), e('b', 0.88)]} />)
    expect(screen.queryByLabelText('Effectively tied')).toBeNull()
    expect(screen.getByText(/intervals overlap/i)).toBeInTheDocument()
  })

  it('has no bracket when nothing is tied', () => {
    render(<Ladder ranked={[e('a', 0.9), e('b', 0.8)]} />)
    expect(screen.queryByLabelText('Effectively tied')).toBeNull()
  })

  it('exposes a tie bracket as a named group, not a landmark (axe: landmark-unique)', () => {
    render(<Ladder ranked={[e('a', 0.9, {}), e('b', 0.89), e('c', 0.8, {}), e('d', 0.79)]} />)
    expect(screen.getAllByRole('group', { name: 'Effectively tied' })).toHaveLength(2)
    expect(screen.queryAllByRole('region', { name: 'Effectively tied' })).toHaveLength(0)
  })
})
