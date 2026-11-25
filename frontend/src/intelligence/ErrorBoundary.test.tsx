import { render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { ErrorBoundary } from './ErrorBoundary'

function Boom(): never { throw new Error('render crash') }

it('shows a message instead of unmounting the whole app when a child throws', () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  render(<><h1>still here</h1><ErrorBoundary><Boom /></ErrorBoundary></>)
  expect(screen.getByRole('alert')).toHaveTextContent(/something went wrong/i)
  expect(screen.getByRole('heading', { name: 'still here' })).toBeInTheDocument()
})

it('renders its children when nothing throws', () => {
  render(<ErrorBoundary><p>fine</p></ErrorBoundary>)
  expect(screen.getByText('fine')).toBeInTheDocument()
})
