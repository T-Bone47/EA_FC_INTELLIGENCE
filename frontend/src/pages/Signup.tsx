import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useSession } from '../state/session'
import { useAction } from '../lib/useApi'
import { ErrorBox, Field } from '../components/common'

export default function Signup() {
  const { signup } = useSession()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)
  const act = useAction(async () => {
    setLocalError(null)
    if (password !== confirm) { setLocalError('Passwords do not match.'); return }
    if (password.length < 8) { setLocalError('Password must be at least 8 characters.'); return }
    await signup(email, password, displayName)
    nav('/dashboard', { replace: true })
  })

  return (
    <div style={{ maxWidth: 440, margin: '3rem auto' }}>
      <h1>Create account</h1>
      <p className="muted small">
        Free, no email verification infrastructure is deployed — accounts are local to
        this instance. Nothing you enter is used to fabricate EA FC data.
      </p>
      <form className="stack" onSubmit={(e: FormEvent) => { e.preventDefault(); act.run() }}>
        <Field label="Email">
          <input className="input" type="email" autoComplete="email" required
                 value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Display name (optional)">
          <input className="input" maxLength={80} autoComplete="nickname"
                 value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </Field>
        <Field label="Password" hint="At least 8 characters. Stored as a bcrypt hash — never in plain text.">
          <input className="input" type="password" autoComplete="new-password" required
                 minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <Field label="Confirm password">
          <input className="input" type="password" autoComplete="new-password" required
                 value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </Field>
        {localError && <div className="error-box" role="alert"><div className="small">{localError}</div></div>}
        <ErrorBox error={act.error} />
        <button className="btn primary wide" type="submit" disabled={act.pending}>
          {act.pending ? <span className="spinner" aria-hidden /> : null}
          {act.pending ? 'Creating account…' : 'Sign up'}
        </button>
        <div className="tiny muted">
          Already registered? <Link to="/login">Log in</Link>
        </div>
      </form>
    </div>
  )
}
