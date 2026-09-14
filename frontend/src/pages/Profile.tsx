import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useSession } from '../state/session'
import { useAction } from '../lib/useApi'
import { ErrorBox, Field } from '../components/common'
import { dateTime } from '../lib/format'

interface Me {
  id: string
  email: string
  display_name: string | null
  role: string
  preferred_game_version: string | null
  preferences: Record<string, unknown> | null
  created_at: string | null
  last_login_at: string | null
}

export default function Profile() {
  const { user, refreshUser, logout, versions, notify } = useSession()
  const nav = useNavigate()
  const [displayName, setDisplayName] = useState(user?.display_name ?? '')
  const [preferred, setPreferred] = useState(user?.preferred_game_version ?? '')
  const [favouritePosition, setFavouritePosition] = useState(
    String((user?.preferences as any)?.favourite_position ?? ''))

  const save = useAction(async () => {
    const me = await api.patch<Me>('/api/auth/me', {
      display_name: displayName.trim() || null,
      preferred_game_version: preferred || null,
      preferences: { ...(user?.preferences ?? {}),
                     favourite_position: favouritePosition || null },
    })
    await refreshUser()
    notify('ok', 'Profile updated.')
    return me
  })

  return (
    <div style={{ maxWidth: 640 }}>
      <div className="page-head">
        <div>
          <h1 className="mb0">Profile</h1>
          <div className="sub small">{user?.email}</div>
        </div>
      </div>

      <div className="card mb2">
        <div className="section-title">Account</div>
        <div className="col">
          <Field label="Display name">
            <input className="input" maxLength={80} value={displayName}
                   onChange={(e) => setDisplayName(e.target.value)} />
          </Field>
          <Field label="Preferred game version"
                 hint="Used as the default when you open the app. Versions are never mixed.">
            <select className="select" value={preferred} onChange={(e) => setPreferred(e.target.value)}>
              <option value="">— no preference —</option>
              {versions.map((v) => (
                <option key={v.code} value={v.code}>
                  {v.code}{v.status === 'NO_DATA' ? ' (NO_DATA — architecture only)' : ''}
                </option>))}
            </select>
          </Field>
          <Field label="Favourite position" hint="Stored as a free preference; the engine never infers facts from it.">
            <input className="input" maxLength={5} style={{ maxWidth: 120 }}
                   value={favouritePosition} placeholder="e.g. CM"
                   onChange={(e) => setFavouritePosition(e.target.value.toUpperCase())} />
          </Field>
          <ErrorBox error={save.error} />
          <div className="row">
            <button className="btn primary" disabled={save.pending} onClick={() => save.run()}>
              {save.pending ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </div>
      </div>

      <div className="card mb2">
        <div className="section-title">Session & security</div>
        <dl className="kv small">
          <dt>Role</dt><dd><span className="badge">{user?.role ?? 'user'}</span></dd>
          <dt>Member since</dt><dd>{dateTime((user as any)?.created_at)}</dd>
          <dt>Last login</dt><dd>{dateTime((user as any)?.last_login_at)}</dd>
        </dl>
        <div className="row mt2">
          <button className="btn ghost sm" onClick={async () => { await logout(false); nav('/') }}>
            Log out (this device)
          </button>
          <button className="btn ghost sm danger"
                  onClick={async () => {
                    if (!window.confirm('Revoke ALL active sessions for this account?')) return
                    await logout(true); nav('/')
                  }}>
            Log out everywhere
          </button>
        </div>
        <div className="tiny faint mt1">
          Passwords are stored as bcrypt hashes; sessions are server-side revocable JWTs.
          Password reset email is not deployed on this instance.
        </div>
      </div>

      <div className="card">
        <div className="section-title">Your data & feedback</div>
        <p className="small muted mb0">
          Recommendation feedback you record (👍/👎) is stored with the full request
          context. It is the future training signal for a learning-to-rank stage —
          which stays disabled until enough real labels exist. No ML model is trained
          on fabricated data.
        </p>
      </div>
    </div>
  )
}
