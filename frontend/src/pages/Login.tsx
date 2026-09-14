import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useSession } from '../state/session'
import { useAction } from '../lib/useApi'
import { ErrorBox, Field } from '../components/common'

export default function Login() {
  const { login } = useSession()
  const nav = useNavigate()
  const loc = useLocation() as { state?: { from?: string } }
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const act = useAction(async () => {
    await login(email, password)
    nav(loc.state?.from || '/dashboard', { replace: true })
  })

  async function forgot() {
    // No password-reset email infrastructure is deployed; be honest instead of
    // pretending to send something.
    act.clear()
    alert('Password reset is not available in this deployment yet. ' +
          'Sessions can be revoked from the profile page; accounts are local to this instance.')
  }

  return (
    <div style={{ maxWidth: 420, margin: '3rem auto' }}>
      <h1>Log in</h1>
      <p className="muted small">
        Your account saves squads, saved players and recommendation feedback.
      </p>
      <form className="stack" onSubmit={(e: FormEvent) => { e.preventDefault(); act.run() }}>
        <Field label="Email">
          <input className="input" type="email" autoComplete="email" required
                 value={email} onChange={(e) => setEmail(e.target.value)}
                 placeholder="you@example.com" />
        </Field>
        <Field label="Password">
          <input className="input" type="password" autoComplete="current-password" required
                 value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <ErrorBox error={act.error} />
        <button className="btn primary wide" type="submit" disabled={act.pending}>
          {act.pending ? <span className="spinner" aria-hidden /> : null}
          {act.pending ? 'Logging in…' : 'Log in'}
        </button>
        <div className="row tiny" style={{ justifyContent: 'space-between' }}>
          <Link to="/signup">Create an account</Link>
          <button type="button" className="btn ghost sm" onClick={forgot}>Forgot password?</button>
        </div>
      </form>
      <hr className="divider" />
      <DemoHints />
    </div>
  )
}

/** Read-only demo of the public surface — no credentials needed. */
export function DemoHints() {
  return (
    <div className="callout info small">
      <div className="t">Just exploring?</div>
      Search, recommendations and comparisons work <strong>without an account</strong>.
      <div className="row mt1">
        <Link className="btn ghost sm" to="/search">Open search</Link>
        <Link className="btn ghost sm" to="/recommend">Open recommendations</Link>
      </div>
    </div>
  )
}

