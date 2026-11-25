import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import App from '../App'
import { SessionProvider } from '../state/session'

afterEach(() => vi.restoreAllMocks())

it('the /intelligence route renders the page, and the nav links to it', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: any) =>
    String(input).includes('/api/auth/me')
      ? new Response(JSON.stringify({ detail: 'Unauthorized' }), { status: 401, headers: { 'Content-Type': 'application/json' } })
      : new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }))
  render(<MemoryRouter initialEntries={['/intelligence']}><SessionProvider><App /></SessionProvider></MemoryRouter>)
  expect(await screen.findByRole('heading', { level: 1, name: /player intelligence/i }, { timeout: 5000 })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Intelligence' })).toHaveAttribute('href', '/intelligence')
  expect(screen.getAllByRole('main')).toHaveLength(1)   // the page must not nest a second <main>
})
