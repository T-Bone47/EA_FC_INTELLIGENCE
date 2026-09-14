import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
  Bar, ConfidenceBadge, FacadeRadar, Facades, FitBadge, Ovr, Value,
} from './common'

describe('UNKNOWN rendering contract', () => {
  it('Ovr renders a dash + UNKNOWN title for null, the number for 0-like values', () => {
    const { rerender } = render(<Ovr value={null} />)
    expect(screen.getByTitle('UNKNOWN')).toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
    rerender(<Ovr value={60} />)
    expect(screen.getByText('60')).toBeInTheDocument()
  })

  it('Value never prints 0 for null but prints real zeros', () => {
    const { rerender } = render(<Value v={null} />)
    expect(screen.getByText('UNKNOWN')).toBeInTheDocument()
    rerender(<Value v={0} />)
    expect(screen.getByText('0')).toBeInTheDocument()
  })

  it('Bar labels null as UNKNOWN and uses the striped na style', () => {
    render(<Bar value={null} />)
    expect(screen.getByRole('img')).toHaveAccessibleName('UNKNOWN')
    const { container } = render(<Bar value={null} />)
    expect(container.querySelector('.bar.na')).toBeTruthy()
  })

  it('Facades shows – for missing facets', () => {
    render(<Facades f={{ pace: 90, shooting: null, passing: 80, dribbling: null, defending: 40, physicality: 70 }} />)
    expect(screen.getAllByText('–').length).toBe(2)
    expect(screen.getByTitle('shooting: UNKNOWN')).toBeInTheDocument()
  })

  it('FitBadge shows the status text, not a fake number, for UNKNOWN/INSUFFICIENT', () => {
    const { rerender } = render(
      <FitBadge fit={{ value: null, status: 'UNKNOWN', reason: 'r', evidence: [] }} />)
    expect(screen.getByText('UNKNOWN')).toBeInTheDocument()
    rerender(<FitBadge fit={{ value: null, status: 'INSUFFICIENT_EVIDENCE', reason: 'r', evidence: [] }} />)
    expect(screen.getByText('INSUFFICIENT EVIDENCE')).toBeInTheDocument()
    rerender(<FitBadge fit={{ value: 0.83, status: 'KNOWN', reason: null, evidence: [] }} />)
    expect(screen.getByText('0.83')).toBeInTheDocument()
  })

  it('ConfidenceBadge never invents a confidence', () => {
    render(<ConfidenceBadge score={null} />)
    expect(screen.getByText(/UNKNOWN/)).toBeInTheDocument()
  })

  it('FacadeRadar omits missing facets from the polygon and marks labels –', () => {
    render(<FacadeRadar values={{ pace: 90, shooting: null, passing: null,
                                  dribbling: 85, defending: null, physicality: 70 }} />)
    const svg = screen.getByRole('img')
    expect(svg).toHaveAccessibleName(/missing facets are omitted, never drawn as zero/)
    const polys = svg.querySelectorAll('polygon[fill^="rgba"]')
    expect(polys.length).toBe(1)
    const pts = polys[0].getAttribute('points')!.trim().split(/\s+/)
    expect(pts.length).toBe(3)   // exactly the three KNOWN facets
    expect(screen.getByText('SHO –')).toBeInTheDocument()
  })
})
