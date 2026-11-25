import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useSession } from '../state/session'
import { useAction } from '../lib/useApi'
import { AccountLayout } from '../components/AccountLayout'
import { ErrorBox, Field } from '../components/common'

export default function Login() {
  const { login } = useSession()
  const nav = useNavigate()
  const loc = useLocation() as { state?: { from?: string } }
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [recovery, showRecovery] = useState(false)
  const act = useAction(async () => {
    await login(email, password)
    nav(accountReturn(loc.state?.from), { replace: true })
  })

  return (
    <AccountLayout>
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
          <Link to="/signup" state={loc.state}>Create an account</Link>
          <button type="button" className="btn ghost sm" aria-expanded={recovery} onClick={() => showRecovery(!recovery)}>Forgot password?</button>
        </div>
      </form>
      {recovery && <p className="callout info mb0" role="status">Password reset is unavailable on this instance. Contact the instance operator for account recovery.</p>}
    </AccountLayout>
  )
}

export function accountReturn(value?: string): string {
  return value?.startsWith('/') && !value.startsWith('//') && !value.includes('\\') ? value : '/dashboard'
}
