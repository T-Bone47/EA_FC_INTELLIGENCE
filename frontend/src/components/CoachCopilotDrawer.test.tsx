import { MemoryRouter } from 'react-router-dom'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CopilotProvider, useCopilot } from '../state/copilot'
import { CoachCopilotDrawer } from './CoachCopilotDrawer'

vi.mock('../state/session', () => ({
  useSession: () => ({
    user: { id: 'u-42', email: 'copilot@example.com', display_name: 'CoPilotUser', role: 'user', preferred_game_version: 'FC27', preferences: null },
    gameVersion: 'FC27',
    notify: vi.fn(),
  }),
}))

function Opener() {
  const { openCopilot } = useCopilot()
  return (
    <button
      type="button"
      onClick={() => openCopilot({
        contextOverride: {
          route_name: 'SQUAD_LAB',
          game_version: 'FC27',
          squad_id: 'SQ-99',
          selected_card_ids: ['C-1', 'C-2'],
        },
      })}
    >
      Trigger Drawer
    </button>
  )
}

describe('CoachCopilotDrawer & ScreenshotRedactorModal (Phase 42E & 42G)', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url: RequestInfo | URL) => {
      const s = String(url)
      if (s.includes('/api/phase40/coach/preferences')) {
        return new Response(JSON.stringify({ preferred_provider: 'AUTO', consent_external_llm: true }), { status: 200 })
      }
      if (s.includes('/api/phase40/coach/ask')) {
        return new Response(
          JSON.stringify({
            session_id: 'S-COPILOT-1',
            message_id: 'M-COPILOT-1',
            provider: 'gemini',
            model: 'gemini-4-hydrogen',
            answer: 'Your Squad Lab XI needs a stronger ball-winning CDM in Slot CDM1.',
            ttft_ms: 420.5,
            latency_ms: 910.2,
            player_cards: [{ id: 'P-77', name: 'A. Tchouameni', position: 'CDM', ovr: 85, game_version: 'FC27', verdict_label: 'Upgrade' }],
            squad_proposal: { proposal_id: 'PROP-42', target_slot: 'CDM1', summary: 'Swap A. Tchouameni into CDM1' },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (s.includes('/api/phase40/squad-proposals/PROP-42/confirm')) {
        return new Response(JSON.stringify({ status: 'CONFIRMED_APPLIED' }), { status: 200 })
      }
      return new Response('{}', { status: 200 })
    })
  })

  it('opens with active route context, runs query, shows cards & confirm gate, and opens redaction modal', async () => {
    render(
      <MemoryRouter>
        <CopilotProvider>
          <Opener />
          <CoachCopilotDrawer />
        </CopilotProvider>
      </MemoryRouter>
    )

    fireEvent.click(screen.getByRole('button', { name: 'Trigger Drawer' }))
    await waitFor(() => expect(screen.getByRole('dialog', { name: /EA FC Intelligence Co-Pilot/i })).toBeInTheDocument())
    expect(screen.getByText('SQUAD_LAB')).toBeInTheDocument()
    expect(screen.getByText('Squad linked')).toBeInTheDocument()
    expect(screen.getByText('2 player(s)')).toBeInTheDocument()

    // Click route-specific quick prompt
    fireEvent.click(screen.getByRole('button', { name: /Audit this squad for weak slots/i }))
    await waitFor(() => expect(screen.getByText(/stronger ball-winning CDM/i)).toBeInTheDocument())
    expect(screen.getAllByText(/A\. Tchouameni/i).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/TTFT 421ms/i)).toBeInTheDocument()

    // Confirm squad proposal
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Confirmed' })).toBeDisabled())

    // Open Screenshot Redaction Modal and ensure Attach stays disabled until image + explicit consent
    fireEvent.click(screen.getByRole('button', { name: 'Attach Screenshot' }))
    const redactorDialog = await screen.findByRole('dialog', { name: /Screenshot Privacy Redaction Canvas/i })
    expect(redactorDialog).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Attach Redacted Screenshot' })).toBeDisabled()
  })
})
