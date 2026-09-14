import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { CardDataStatus } from '../api/types'
import { DataQualityPanel } from './DataQuality'

const status: CardDataStatus = {
  game_version: 'FC26',
  production_cards: 0,
  synthetic_cards_firewalled: 60,
  playstyle_published_cards: 0,
  identity_resolved_cards: 0,
  cards_with_price: 0,
  card_roles_rows: 0,
  verified_chemistry_rules: 0,
  evolution_rows: 0,
  quarantined_rows: 3,
  last_card_update: null,
  recent_ingestion_runs: [],
  availability: {
    card_attributes: 'NO_DATA',
    card_prices: 'NO_DATA',
    card_roles: 'NO_DATA',
    chemistry_rules: 'NO_VERIFIED_RULES',
    evolutions: 'NO_DATA',
  },
}

describe('DataQualityPanel (§44)', () => {
  it('renders NO_DATA honestly — never zeros dressed as data', () => {
    render(<DataQualityPanel status={status} />)
    expect(screen.getByTestId('data-quality')).toBeTruthy()
    expect(screen.getAllByText('NO DATA').length).toBeGreaterThanOrEqual(4)
    expect(screen.getByText('No verified rules')).toBeTruthy()
    // synthetic firewall is visible, not hidden
    expect(screen.getByText(/Synthetic test cards firewalled: 60/)).toBeTruthy()
    // explicit data-ready notice when nothing is ingested
    expect(screen.getByText(/No production UT card data is ingested/)).toBeTruthy()
    expect(screen.getByText(/nothing is fabricated/i)).toBeTruthy()
  })

  it('renders availability when data exists', () => {
    const withData: CardDataStatus = {
      ...status,
      production_cards: 1200,
      cards_with_price: 800,
      availability: { ...status.availability, card_attributes: 'AVAILABLE',
                      card_prices: 'PARTIAL' },
    }
    render(<DataQualityPanel status={withData} />)
    expect(screen.getByText('Available')).toBeTruthy()
    expect(screen.getByText('Partial')).toBeTruthy()
    expect(screen.queryByText(/No production UT card data/)).toBeNull()
  })

  it('renders nothing without status', () => {
    const { container } = render(<DataQualityPanel status={null} />)
    expect(container.textContent).toBe('')
  })
})
